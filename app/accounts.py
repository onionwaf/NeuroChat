import logging
import contextlib
import asyncio
import re
import random
import time
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient, events
import socks
from telethon.errors import SessionPasswordNeededError
from . import db, filters, triggers as triggers_mod, prompts as prompts_mod
from .mistral_api import ask_mistral
from .chats import join_chat_by_username, join_by_invite

# ---- Hard global defaults to prevent NameError even before settings are loaded ----
try:
    from app import db as _db__for_defaults
    try:
        human_jitter_pct = int(float(_db__for_defaults.get_setting("human_jitter_pct","12") or "12"))
    except Exception:
        human_jitter_pct = 12
    try:
        human_think_ms = int(float(_db__for_defaults.get_setting("human_think_ms","600") or "600"))
    except Exception:
        human_think_ms = 600
except Exception:
    human_jitter_pct = 12
    human_think_ms = 600
# ----------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SESSIONS_DIR = DATA_DIR / "sessions"


def _build_proxy_for_phone(phone: str):
    """
    Build telethon proxy tuple from per-account settings.
    Returns None when proxy disabled/invalid.
    """
    try:
        px = db.get_account_proxy(phone) or {}
        enabled = int(px.get("enabled", 0) or 0)
        ptype = (px.get("type") or "SOCKS5").upper()
        host = (px.get("host") or "").strip()
        port = int(str(px.get("port") or "0"))
        user = px.get("username") or None
        pwd = px.get("password") or None
    except Exception:
        enabled, ptype, host, port, user, pwd = 0, "SOCKS5", "", 0, None, None

    if not enabled or not host or not port:
        try:
            db.log("WARN", "proxy", f"Proxy disabled or invalid for {phone}: host={host!r} port={port!r}", phone)
        except Exception:
            pass
        return None

    try:
        import socks
        pmap = {"SOCKS5": socks.SOCKS5, "SOCKS4": socks.SOCKS4, "HTTP": socks.HTTP}
        ptype_val = pmap.get(ptype, socks.SOCKS5)
        db.log("INFO", "proxy", f"Using proxy for {phone}: type={ptype} host={host!r} port={port}", phone)
        return (ptype_val, host, int(port), user, pwd)
    except Exception as e:
        try:
            db.log("WARN", "proxy", f"Failed to build proxy for {phone}: {e}", phone)
        except Exception:
            pass
        return None


SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

class BotWorker:
    def __init__(self, phone: str, session_path: str):
        self.phone = phone
        self.session_path = session_path
        self.loop = asyncio.new_event_loop()
        self.thread = None
        self.client: Optional[TelegramClient] = None
        self.running = False
        self.messages_processed = 0
        self.starting = False

    async def _ensure_client(self):
        try:
            db.migrate_chat_state()
            db.migrate_schema()
        except Exception:
            pass
        api_id = int(db.get_setting("telegram_api_id", "0") or "0")
        api_hash = db.get_setting("telegram_api_hash", "")
        if api_id == 0 or not api_hash:
            raise RuntimeError("Set Telegram API ID and API Hash in Settings.")
        self.client = TelegramClient(str(self.session_path), api_id, api_hash, loop=self.loop, proxy=_build_proxy_for_phone(self.phone))
        await self.client.connect()
        if not await self.client.is_user_authorized():
            raise RuntimeError(f"Session {self.session_path} is not authorized. Use 'Add' to login via phone.")

    async def _handle_message(self, event):
        try:
            msg = event.message
            if not msg or not msg.message: return
            if msg.out: return  # don't reply to self
            chat = await event.get_chat()
            chat_id = event.chat_id
            chat_title = getattr(chat, "title", "") or getattr(chat, "username", "") or str(chat_id)
            db.upsert_chat(self.phone, chat_id, chat_title, getattr(chat, "username", None) or "")

            active_chats = {r["chat_id"]: r for r in db.list_chats(self.phone) if r["active"] == 1}
            if chat_id not in active_chats:
                db.set_chat_diag(self.phone, chat_id, 'chat_inactive')
                return
            
            # --- Humanization settings ---
            def _get_set(key, default):
                try:
                    v = db.get_setting(key, default)
                    return v if v is not None else default
                except Exception:
                    return default

            human_auto_enabled = int(db.get_acc_setting(self.phone, "human_auto_enabled", db.get_setting("human_auto_enabled", 1)) or "1")
            react_min = float(db.get_acc_setting(self.phone, "human_react_min_sec", db.get_setting("human_react_min_sec", 3.0)) or "3.0")
            react_max = float(db.get_acc_setting(self.phone, "human_react_max_sec", db.get_setting("human_react_max_sec", 4.0)) or "4.0")
            cps_min = float(db.get_acc_setting(self.phone, "human_typing_cps_min", db.get_setting("human_typing_cps_min", 3.2)) or "3.2")
            cps_max = float(db.get_acc_setting(self.phone, "human_typing_cps_max", db.get_setting("human_typing_cps_max", 6.8)) or "6.8")
            par_min = int(float(db.get_acc_setting(self.phone, "human_between_paragraph_min_ms", db.get_setting("human_between_paragraph_min_ms", 80)) or "80"))
            par_max = int(float(db.get_acc_setting(self.phone, "human_between_paragraph_max_ms", db.get_setting("human_between_paragraph_max_ms", 200)) or "200"))
            before_min = int(float(db.get_acc_setting(self.phone, "human_before_send_min_ms", db.get_setting("human_before_send_min_ms", 120)) or "120"))
            before_max = int(float(db.get_acc_setting(self.phone, "human_before_send_max_ms", db.get_setting("human_before_send_max_ms", 400)) or "400"))
            keep_typing_until_send = int(db.get_acc_setting(self.phone, "human_keep_typing_until_send", db.get_setting("human_keep_typing_until_send", 1)) or "1")

            human_mark_read_policy = (db.get_acc_setting(self.phone, "human_mark_read_policy", db.get_setting("human_mark_read_policy", "on_typing")) or "on_typing").strip()
            human_quiet_hours = (db.get_acc_setting(self.phone, "human_quiet_hours", db.get_setting("human_quiet_hours", )) or "").strip()
            human_limit_per_minute = int(float(db.get_acc_setting(self.phone, "human_limit_per_minute", db.get_setting("human_limit_per_minute", 0)) or "0"))

            def _rand_range(a, b):
                import random
                if a > b: a, b = b, a
                return random.uniform(a, b)

            reaction_delay_ms = int(_rand_range(react_min, react_max) * 1000) if human_auto_enabled else int(float(db.get_acc_setting(self.phone, "human_after_read_delay_ms", db.get_setting("human_after_read_delay_ms", 300)) or "300"))
            typing_cps = _rand_range(cps_min, cps_max) if human_auto_enabled else float(db.get_acc_setting(self.phone, "typing_cps", db.get_setting("typing_cps", 4.5)) or "4.5")
            between_par_ms = int(_rand_range(par_min, par_max)) if human_auto_enabled else int(float(db.get_acc_setting(self.phone, "between_par_ms", db.get_setting("between_par_ms", 120)) or "120"))
            before_send_ms = int(_rand_range(before_min, before_max)) if human_auto_enabled else int(float(db.get_acc_setting(self.phone, "before_send_ms", db.get_setting("before_send_ms", 250)) or "250"))
            def _in_quiet_hours(spec: str) -> bool:
                """Return True if current local time falls into any quiet-hours interval in spec.
                spec format: "HH:MM-HH:MM[, ...]". Empty -> False.
                """
                try:
                    from datetime import datetime, time
                    now = datetime.now().time()
                    items = [s.strip() for s in (spec or "").split(",") if s.strip()]
                    for it in items:
                        try:
                            a,b = it.split("-")
                            h1,m1 = [int(x) for x in a.split(":")]
                            h2,m2 = [int(x) for x in b.split(":")]
                            t1 = time(h1,m1); t2 = time(h2,m2)
                            if t1 <= t2:
                                if t1 <= now <= t2:
                                    return True
                            else:
                                if now >= t1 or now <= t2:
                                    return True
                        except Exception:
                            continue
                    return False
                except Exception:
                    return False


            if _in_quiet_hours(human_quiet_hours):
                db.set_chat_diag(self.phone, chat_id, 'quiet_hours')
                return


            text = msg.message.strip()

            trig = db.list_triggers(self.phone, chat_id)
            global_trig_raw = db.get_setting("global_triggers","") or ""
            global_triggers = triggers_mod.split_triggers(global_trig_raw)
            if not trig:
                trig = global_triggers
            db.log("DEBUG","filter",f"chat triggers={list(trig)} | global={global_triggers}", self.phone, chat_id, chat_title)
            if not triggers_mod.has_trigger(text, trig):
                db.log("DEBUG","filter",f"skip: no trigger | text={text[:60]!r}", self.phone, chat_id, chat_title)
                db.set_chat_diag(self.phone, chat_id, 'no_trigger')
                return

            min_words = int(db.get_acc_setting(self.phone, "min_words", "3"))
            allow_ru = db.get_acc_setting(self.phone, "lang_ru_enabled", db.get_setting("lang_ru_enabled","1")) == "1"
            allow_en = db.get_acc_setting(self.phone, "lang_en_enabled", db.get_setting("lang_en_enabled","1")) == "1"
            anti_spam = db.get_acc_setting(self.phone, "anti_spam_enabled", db.get_setting("anti_spam_enabled","1")) == "1"
            if not filters.words_count_ok(text, min_words):
                db.log("DEBUG","filter",f"skip: min_words", self.phone, chat_id, chat_title); db.set_chat_diag(self.phone, chat_id, 'min_words'); return
            if not filters.language_ok(text, allow_ru, allow_en):
                db.log("DEBUG","filter","skip: language not allowed", self.phone, chat_id, chat_title); db.set_chat_diag(self.phone, chat_id, 'lang_not_allowed'); return
            if anti_spam and not filters.unique_ok(self.phone, chat_id, text):
                db.log("DEBUG","filter","skip: duplicate (anti-spam)", self.phone, chat_id, chat_title); db.set_chat_diag(self.phone, chat_id, 'duplicate'); return

            timeout_sec = int(db.get_acc_setting(self.phone, "timeout_sec_per_chat", db.get_setting("timeout_sec_per_chat","60")))
            last = db.get_last_reply(self.phone, chat_id)
            if last and (datetime.now(timezone.utc) - last).total_seconds() < timeout_sec:
                remaining = int(timeout_sec - (datetime.now(timezone.utc) - last).total_seconds())
                next_ts = (datetime.now(timezone.utc) + timedelta(seconds=remaining)).isoformat()
                db.log("DEBUG","filter",f"skip: cooldown {timeout_sec}s", self.phone, chat_id, chat_title); db.set_chat_diag(self.phone, chat_id, f'cooldown_remaining={remaining}s', next_ts); return

            style_acc, custom_acc = db.get_account_prompt(self.phone)
            if style_acc or custom_acc:
                style, custom = style_acc or 'friendly', custom_acc or ''
            else:
                style, custom = prompts_mod.get_global_prompt()
            prompt = prompts_mod.build_prompt(style, custom, text)

            limits = db.get_account_limits(self.phone)
            if limits.get('safe_mode',1):
                db.log('INFO','safety', f'acc={self.phone} safe_mode=ON', self.phone, chat_id, chat_title)
                db.set_chat_diag(self.phone, chat_id, 'safe_mode=ON')
                return
            since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(sep=' ')
            if db.count_replies_since(self.phone, since) >= int(limits.get('replies_per_hour',8)):
                db.log('INFO','safety', f'acc={self.phone} hourly cap reached', self.phone, chat_id, chat_title)
                return
            last = db.get_last_reply(self.phone, chat_id)
            if last is not None:
                gap_ms = (datetime.now(timezone.utc)-last).total_seconds()*1000.0
                if gap_ms < float(limits.get('per_chat_min_gap_ms',180000)):
                    db.log('DEBUG','safety', f'acc={self.phone} chat gap {gap_ms:.0f}ms', self.phone, chat_id, chat_title)
                    return

            db.log("INFO", "bot", f"Ask Mistral: {text}", self.phone, chat_id, chat_title)
            
            async def _mark_read():
                try:
                    await self.client.send_read_acknowledge(chat, max_id=msg.id)
                except Exception:
                    pass

            async def _sleep_ms(ms):
                import asyncio, random
                if ms <= 0: 
                    return
                try:
                    jp = int(human_jitter_pct)
                except Exception:
                    jp = 12
                jitter = int(ms * (jp/100.0))
                ms2 = max(0, ms + random.randint(-jitter, jitter))
                await asyncio.sleep(ms2/1000.0)

            if human_mark_read_policy == "immediate":
                await _mark_read()

            await _sleep_ms(reaction_delay_ms)

            reply_text = None
            import asyncio
            async def _gen():
                nonlocal reply_text
                loop = asyncio.get_running_loop()
                reply_text = await loop.run_in_executor(None, lambda: ask_mistral(prompt))

            if keep_typing_until_send:
                async with self.client.action(chat, 'typing'):
                    if human_mark_read_policy == "on_typing":
                        await _mark_read()
                    await _sleep_ms(human_think_ms)
                    await _gen()
                    est_ms = int(max(0, len(reply_text)) / max(0.1, typing_cps) * 1000)
                    par_count = reply_text.count("\\n\\n")
                    est_ms += par_count * between_par_ms
                    await _sleep_ms(est_ms)
                    await _sleep_ms(before_send_ms)
            else:
                if human_mark_read_policy == "on_typing":
                    await _mark_read()
                await _sleep_ms(human_think_ms)
                await _gen()
                await _sleep_ms(before_send_ms)

            if human_mark_read_policy == "before_send":
                await _mark_read()

            reply = reply_text


            acc_cta_enabled, acc_cta_text = db.get_account_cta(self.phone)
            if acc_cta_enabled and (acc_cta_text or "").strip():
                reply = f"{reply}\n\n{acc_cta_text.strip()}"
            elif db.get_setting("global_cta_enabled","0") == "1":
                cta = db.get_setting("global_cta","").strip()
                if cta:
                    reply = f"{reply}\n\n{cta}"

            
            try:
                if human_limit_per_minute and human_limit_per_minute > 0:
                    since = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat(sep=' ')
                    cnt_min = db.count_replies_since(self.phone, since)
                    if cnt_min >= max(1, human_limit_per_minute):
                        db.log('INFO','safety', f'acc={self.phone} per-minute cap reached', self.phone, chat_id, chat_title)
                        return
            except Exception:
                pass

            await event.reply(reply)
            self.messages_processed += 1
            db.set_last_reply(self.phone, chat_id)
            try:
                limits = db.get_account_limits(self.phone)
                gap = int(limits.get('per_chat_min_gap_ms', 180000))/1000.0
            except Exception:
                gap = 180.0
            next_ts = (datetime.now(timezone.utc) + timedelta(seconds=gap)).isoformat()
            db.set_chat_diag(self.phone, chat_id, reason='replied', next_eligible_ts=next_ts, last_action='reply')
            db.log("INFO", "bot", f"Replied: {reply[:200]}...", self.phone, chat_id, chat_title)

        except Exception as e:
            db.log("ERROR", "bot", f"{type(e).__name__}: {e}", self.phone)

    async def _start(self):
        await self._ensure_client()
        self.client.add_event_handler(self._handle_message, events.NewMessage())
        self.running = True
        self.starting = False
        db.log("INFO", "runner", f"Started account {self.phone}")
        try:
            await self.client.run_until_disconnected()
        finally:
            self.running = False
            db.log("INFO", "runner", f"Stopped account {self.phone}")

    def start(self):
        if self.running or self.starting or (self.thread and getattr(self.thread, 'is_alive', lambda: False)()):
            return
        if not self.loop or self.loop.is_closed():
            self.loop = asyncio.new_event_loop()
        self.starting = True
        import threading
        def run():
            asyncio.set_event_loop(self.loop)
            self.loop.create_task(self._start())
            try:
                self.loop.run_forever()
            except Exception:
                logging.exception('worker loop crashed')
            finally:
                for t in asyncio.all_tasks(self.loop):
                    t.cancel()
                with contextlib.suppress(Exception):
                    self.loop.run_until_complete(self.loop.shutdown_asyncgens())
                self.loop.close()
                self.loop = None
        self.thread = threading.Thread(target=run, daemon=False)
        self.thread.start()


    def stop(self):
        if not (self.running or self.starting):
            return
        async def _stop():
            try:
                if self.client:
                    await self.client.disconnect()
            except Exception:
                pass
        if self.loop and self.loop.is_running():
            fut = asyncio.run_coroutine_threadsafe(_stop(), self.loop)
            try:
                fut.result(timeout=10)
            except Exception as e:
                logging.debug('disconnect wait failed: %s', e)
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.thread:
            try:
                self.thread.join(timeout=15)
            except Exception:
                pass
        self.starting = False
class AccountsManager:
    def __init__(self):
        self.workers: Dict[str, BotWorker] = {}

    def import_session_file(self, path: str) -> str:
        src = Path(path)
        if not src.exists(): raise FileNotFoundError(path)
        dst = SESSIONS_DIR / src.name
        if src.resolve() != dst.resolve():
            dst.write_bytes(src.read_bytes())
        phone_stub = src.stem
        db.add_account(phone_stub, str(dst))
        db.log("INFO", "accounts", f"Imported session: {dst.name}", phone_stub)
        return phone_stub

    async def login_by_phone_async(self, api_id: int, api_hash: str, phone: str,
                                   code_provider, pwd_provider) -> str:
        session_path = SESSIONS_DIR / f"{phone}.session"
        client = TelegramClient(str(session_path), api_id, api_hash, proxy=_build_proxy_for_phone(phone))
        await client.connect()
        if not await client.is_user_authorized():
            try:
                await client.send_code_request(phone)
                code = code_provider()
                await client.sign_in(phone=phone, code=code)
            except SessionPasswordNeededError:
                pwd = pwd_provider()
                await client.sign_in(password=pwd)
        await client.disconnect()
        db.add_account(phone, str(session_path))
        return str(session_path)

    def start_account(self, phone: str):
        accounts = {a["phone"]: a for a in db.list_accounts()}
        if phone not in accounts: raise RuntimeError(f"Unknown account {phone}")
        rec = accounts[phone]
        worker = self.workers.get(phone)
        if worker is None:
            worker = BotWorker(phone, rec["session_path"])
            self.workers[phone] = worker
        worker.start()
        db.set_account_enabled(phone, True)

    def stop_account(self, phone: str):
        worker = self.workers.get(phone)
        if worker: worker.stop()
        db.set_account_enabled(phone, False)

    def stop_all(self):
        for w in self.workers.values():
            try: w.stop()
            except Exception: pass

    def status(self):
        out = []
        for phone, w in self.workers.items():
            out.append({"phone": phone, "running": w.running, "messages_processed": w.messages_processed,
                        "active_chats": len([r for r in db.list_chats(phone) if r["active"] == 1])})
        return out

    def process_join_queue_once(self):
        items = list(db.list_join_items(status="queued", limit=200))
        if not items: return 0
        count = 0
        for it in items:
            db.set_join_status(it["id"], "running")
            username = it["username"]; invite = it["invite_hash"]
            ok_any = False
            for phone, w in list(self.workers.items()):
                if not w.running or not w.client: continue
                async def do_join():
                    if username: return await join_chat_by_username(w.client, username)
                    if invite: return await join_by_invite(w.client, invite)
                    return False
                
                try:
                    delay_enabled = db.get_setting("join_delay_enabled", "1") == "1"
                    dmin = float(db.get_setting("join_delay_min_sec", "2.0"))
                    dmax = float(db.get_setting("join_delay_max_sec", "5.0"))
                    if dmax < dmin:
                        dmin, dmax = dmax, dmin
                except Exception:
                    delay_enabled, dmin, dmax = True, 2.0, 5.0
                
                if delay_enabled:
                    wait = random.uniform(dmin, dmax)
                    db.log("INFO", "join", f"Humanized delay {wait:.1f}s before joining "
                                            f"{('invite='+invite) if invite else ('@'+username)}",
                           account_phone=phone)
                    time.sleep(wait)
                
                fut = asyncio.run_coroutine_threadsafe(do_join(), w.loop)
                try: ok = fut.result(timeout=60)
                except Exception: ok = False
                ok_any = ok_any or ok
            if ok_any:
                db.set_join_status(it["id"], "success"); count += 1
            else:
                db.set_join_status(it["id"], "error", "failed for all accounts")
        return count
    def stop_all_and_join(self):
        """Stop all workers and join their threads for graceful shutdown."""
        for w in list(self.workers.values()):
            try:
                w.stop()
            except Exception:
                pass
        for w in list(self.workers.values()):
            th = getattr(w, "thread", None)
            if th:
                try:
                    th.join(timeout=15)
                except Exception:
                    pass
ACCOUNTS = AccountsManager()
