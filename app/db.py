
import os, sqlite3, threading, logging
from pathlib import Path
from .paths import db_path
from typing import Optional, Iterable
from datetime import datetime, timezone
MIGRATION_DONE = False

def _normalize_phone(p: str) -> str:
    p = (p or "").strip()
    if p and not p.startswith("+"):
        p = "+" + p
    return p

def _ensure_chat_state_columns(conn):
    try:
        cur = conn.execute("PRAGMA table_info(chat_state)")
        cols = {row[1] for row in cur.fetchall()}
        def _try(sql):
            try:
                conn.execute(sql)
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    pass
                else:
                    raise
        if "last_event_ts" not in cols:
            _try("ALTER TABLE chat_state ADD COLUMN last_event_ts TEXT")
        if "last_skip_reason" not in cols:
            _try("ALTER TABLE chat_state ADD COLUMN last_skip_reason TEXT")
        if "next_eligible_ts" not in cols:
            _try("ALTER TABLE chat_state ADD COLUMN next_eligible_ts TEXT")
        if "last_action" not in cols:
            _try("ALTER TABLE chat_state ADD COLUMN last_action TEXT DEFAULT 'skip'")
        conn.commit()
    except Exception:
        pass


DB_PATH = Path(__file__).resolve().parent.parent / "data" / "neurobot.db"

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS accounts (

    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT UNIQUE,
    session_path TEXT UNIQUE,
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_phone TEXT,
    chat_id INTEGER,
    chat_title TEXT,
    chat_username TEXT,
    active INTEGER DEFAULT 1,
    UNIQUE(account_phone, chat_id)
);

CREATE TABLE IF NOT EXISTS triggers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_phone TEXT,
    chat_id INTEGER,
    phrase TEXT,
    UNIQUE(account_phone, chat_id, phrase)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS chat_state (
    account_phone TEXT,
    chat_id INTEGER,
    last_reply_ts TEXT,
    PRIMARY KEY(account_phone, chat_id)
);

CREATE TABLE IF NOT EXISTS message_hashes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_phone TEXT,
    chat_id INTEGER,
    hash TEXT,
    UNIQUE(account_phone, chat_id, hash)
);

CREATE TABLE IF NOT EXISTS join_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT,
    username TEXT,
    invite_hash TEXT,
    status TEXT,
    last_error TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS account_limits (
    account_phone TEXT PRIMARY KEY,
    safe_mode INTEGER DEFAULT 1,
    min_gap_ms INTEGER DEFAULT 60000,
    per_chat_min_gap_ms INTEGER DEFAULT 180000,
    replies_per_hour INTEGER DEFAULT 8,
    jitter_ms INTEGER DEFAULT 8000,
    pause_on_flood_wait_min INTEGER DEFAULT 45,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS account_api (
    account_phone TEXT PRIMARY KEY,
    api_id INTEGER,
    api_hash TEXT
);

CREATE TABLE IF NOT EXISTS account_proxy (
    account_phone TEXT PRIMARY KEY,
    enabled INTEGER DEFAULT 0,
    type TEXT DEFAULT 'SOCKS5',
    host TEXT,
    port INTEGER,
    username TEXT,
    password TEXT
);

CREATE TABLE IF NOT EXISTS account_ai (
    account_phone TEXT PRIMARY KEY,
    style TEXT,
    custom_prompt TEXT,
    cta_enabled INTEGER DEFAULT 0,
    cta_text TEXT
);

CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT DEFAULT CURRENT_TIMESTAMP,
    level TEXT,
    source TEXT,
    payload TEXT,
    account_phone TEXT,
    chat_id INTEGER,
    chat_title TEXT
);
"""

DEFAULT_SETTINGS = {
    "logging_enabled": "1",
    "debug_enabled": "0",
    "autostart_accounts": "0",
    "auto_join_on_start": "0",

    "min_words": "3",
    "lang_ru_enabled": "1",
    "lang_en_enabled": "1",
    "anti_spam_enabled": "1",
    "timeout_sec_per_chat": "60",

    "mistral_api_key": "",
    "mistral_model": "mistral-large-latest",
    "global_prompt_style": "friendly",
    "global_custom_prompt": "",
    "global_cta_enabled": "0",
    "global_cta": "",

    "mistral_rpm": "10",
    "mistral_max_retries": "6",
    "mistral_retry_base_delay": "2",
    "mistral_retry_jitter_ms": "250",

# --- Humanized join delay (global) ---
    "join_delay_enabled": "1",
    "join_delay_min_sec": "2.0",
    "join_delay_max_sec": "5.0"
}

_conn_lock = threading.Lock()
_write_lock = threading.Lock()
_thread_local = threading.local()

def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    # Reasonable defaults
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
    except Exception:
        pass
    return conn


def get_conn() -> sqlite3.Connection:
    conn = getattr(_thread_local, "conn", None)
    if conn is None:
        with _conn_lock:
            conn = getattr(_thread_local, "conn", None)
            if conn is None:
                _thread_local.conn = conn = _connect()
    return conn

def _write(fn):
    conn = get_conn()
    with _write_lock:
        return fn(conn)

# Public helpers (оба для совместимости)
def init_db():
    create_schema()


    migrate_schema()
def create_schema():
    conn = get_conn()
    with _conn_lock:
        conn.executescript(SCHEMA)
        cur = conn.execute("SELECT key FROM settings")
        have = {r[0] for r in cur.fetchall()}
        for k, v in DEFAULT_SETTINGS.items():
            if k not in have:
                conn.execute("INSERT INTO settings(key, value) VALUES(?,?)", (k, v))
        conn.commit()


# ---------- Account API creds ----------
def set_account_api(account_phone: str, api_id: int, api_hash: str):
    def _ins(conn):
        conn.execute(
            "INSERT INTO account_api(account_phone, api_id, api_hash) VALUES(?,?,?) "
            "ON CONFLICT(account_phone) DO UPDATE SET api_id=excluded.api_id, api_hash=excluded.api_hash",
            (account_phone, int(api_id), str(api_hash))
        )
        conn.commit()
    _write(_ins)

def get_account_api(account_phone: str):
    with get_conn() as conn:
        # message_hashes: add created_at for TTL-based anti-spam
        try: _ensure_column(conn, "message_hashes", "created_at", "TEXT")
        except Exception: pass
        cur = conn.execute("SELECT api_id, api_hash FROM account_api WHERE account_phone=?", (account_phone,))
        row = cur.fetchone()
        if not row:
            return None, None
        try:
            return int(row[0]) if row[0] is not None else None, row[1]
        except Exception:
            return None, row[1]

# ---------- Settings ----------
def set_setting(key: str, value: str):
    def _ins(conn):
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value))
        )
        conn.commit()
    _write(_ins)

def get_acc_setting(phone: str, key: str, default=None):
    """Per-account override using settings keys acc:{phone}:{key}."""
    try:
        v = get_setting(f"acc:{phone}:{key}", None)
        if v is not None:
            return v
    except Exception:
        pass
    return get_setting(key, default)

def set_acc_setting(phone: str, key: str, value: str):
    try:
        set_setting(f"acc:{phone}:{key}", value)
    except Exception:
        set_setting(key, value)

def get_setting(key: str, default: Optional[str]=None) -> str:
    with get_conn() as conn:
        cur = conn.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cur.fetchone()
        return row[0] if row and row[0] is not None else default

# ---------- Accounts ----------
def add_account(phone: str, session_path: str):
    def _ins(conn):
        conn.execute(
            "INSERT OR REPLACE INTO accounts(phone, session_path, enabled) VALUES(?,?,1)",
            (phone, session_path)
        )
        conn.commit()
    _write(_ins)

def list_accounts():
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM accounts ORDER BY created_at DESC")
        return cur.fetchall()

def set_account_enabled(phone: str, enabled: bool):
    def _upd(conn):
        conn.execute("UPDATE accounts SET enabled=? WHERE phone=?",
                     (1 if enabled else 0, phone))
        conn.commit()
    _write(_upd)

def delete_account(phone: str):
    """Delete account and all related data (chats, triggers, states, hashes, queue, logs, settings rows).
    Also removes session file if exists.
    """
    def _del(conn):
        # dependent tables by account phone
        for tbl, where in [
            ("triggers", "account_phone=?"),
            ("chats", "account_phone=?"),
            ("chat_state", "account_phone=?"),
            ("message_hashes", "account_phone=?"),
            ("join_queue", "account_phone=?"),
            ("account_limits", "phone=?"),
            ("account_api", "phone=?"),
            ("account_proxy", "phone=?"),
            ("account_ai", "phone=?"),
            ("logs", "phone=?")
        ]:
            try:
                conn.execute(f"DELETE FROM {tbl} WHERE {where}", (phone,))
            except Exception:
                pass
        conn.execute("DELETE FROM accounts WHERE phone=?", (phone,))
        conn.commit()
    _write(_del)
    # remove session file on disk (best effort)
    try:
        from .paths import sessions_dir
        sess = sessions_dir() / f"{phone}.session"
        if sess.exists():
            sess.unlink()
    except Exception:
        pass

# ---------- Chats ----------
def upsert_chat(account_phone: str, chat_id: int, chat_title: str, chat_username: str):
    def _ins(conn):
        conn.execute(
            """
            INSERT INTO chats(account_phone, chat_id, chat_title, chat_username, active)
            VALUES(?,?,?,?,1)
            ON CONFLICT(account_phone, chat_id)
            DO UPDATE SET chat_title=excluded.chat_title, chat_username=excluded.chat_username
            """,
            (account_phone, chat_id, chat_title, chat_username)
        )
        conn.commit()
    _write(_ins)

def list_chats(account_phone: str | None = None):
    with get_conn() as conn:
        if account_phone:
            cur = conn.execute(
                "SELECT account_phone, chat_id, chat_title, chat_username, active "
                "FROM chats WHERE account_phone=? ORDER BY chat_title",
                (account_phone,)
            )
        else:
            cur = conn.execute(
                "SELECT account_phone, chat_id, chat_title, chat_username, active "
                "FROM chats ORDER BY account_phone, chat_title"
            )
        return cur.fetchall()

def set_chat_active(account_phone: str, chat_id: int, active: bool):
    def _upd(conn):
        conn.execute("UPDATE chats SET active=? WHERE account_phone=? AND chat_id=?",
                     (1 if active else 0, account_phone, chat_id))
        conn.commit()
    _write(_upd)

# ---------- Triggers ----------
def list_triggers(account_phone: str, chat_id: int) -> Iterable[str]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT phrase FROM triggers WHERE account_phone=? AND chat_id=?",
            (account_phone, chat_id)
        )
        return [r[0] for r in cur.fetchall()]

def add_trigger(account_phone: str, chat_id: int, phrase: str):
    phrase = (phrase or "").strip()
    if not phrase:
        return
    def _ins(conn):
        conn.execute(
            "INSERT OR IGNORE INTO triggers(account_phone, chat_id, phrase) VALUES(?,?,?)",
            (account_phone, chat_id, phrase)
        )
        conn.commit()
    _write(_ins)

def delete_trigger(account_phone: str, chat_id: int, phrase: str):
    def _del(conn):
        conn.execute(
            "DELETE FROM triggers WHERE account_phone=? AND chat_id=? AND phrase=?",
            (account_phone, chat_id, phrase)
        )
        conn.commit()
    _write(_del)

# ---------- Anti-spam ----------
def store_message_hash(account_phone: str, chat_id: int, h: str) -> bool:
    """Store message hash for anti-spam. Works on legacy/new schema."""
    try:
        # Cleanup by TTL only if 'created_at' exists
        try:
            ttl = int(get_setting("anti_spam_ttl_sec", "30") or "30")
        except Exception:
            ttl = 30
        if ttl > 0:
            def _cleanup(conn):
                try:
                    conn.execute("SELECT created_at FROM message_hashes LIMIT 1")
                    from datetime import datetime, timezone
                    cutoff = int(datetime.now(timezone.utc).timestamp()) - ttl
                    conn.execute(
                        "DELETE FROM message_hashes WHERE account_phone=? AND chat_id=? AND hash=? AND (created_at IS NULL OR strftime('%s', created_at) < ?)",
                        (account_phone, chat_id, h, cutoff)
                    )
                    conn.commit()
                except Exception:
                    pass
            _write(_cleanup)
        def _ins(conn):
            try:
                conn.execute(
                    "INSERT INTO message_hashes(account_phone, chat_id, hash, created_at) VALUES(?,?,?, datetime('now'))",
                    (account_phone, chat_id, h)
                )
            except Exception:
                conn.execute(
                    "INSERT INTO message_hashes(account_phone, chat_id, hash) VALUES(?,?,?)",
                    (account_phone, chat_id, h)
                )
            conn.commit()
        _write(_ins)
        return True
    except sqlite3.IntegrityError:
        return False

def set_last_reply(account_phone: str, chat_id: int, ts=None):
    ts = datetime.now(timezone.utc).isoformat()
    def _upd(conn):
        conn.execute(
            """
            INSERT INTO chat_state(account_phone, chat_id, last_reply_ts)
            VALUES(?,?,?)
            ON CONFLICT(account_phone, chat_id)
            DO UPDATE SET last_reply_ts=excluded.last_reply_ts
            """,
            (account_phone, chat_id, ts)
        )
        conn.commit()
    _write(_upd)

def set_chat_diag(account_phone: str, chat_id: int, reason: str | None = None, next_eligible_ts: str | None = None, last_action: str | None = 'skip'):
    """Store diagnostics for a chat: last_event_ts (now), last_skip_reason, next_eligible_ts, last_action."""
    ts = datetime.now(timezone.utc).isoformat()
    def _upd(conn):
        conn.execute(
            """
            INSERT INTO chat_state(account_phone, chat_id, last_reply_ts, last_event_ts, last_skip_reason, next_eligible_ts, last_action)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(account_phone, chat_id)
            DO UPDATE SET last_event_ts=excluded.last_event_ts,
                          last_skip_reason=excluded.last_skip_reason,
                          next_eligible_ts=excluded.next_eligible_ts,
                          last_action=excluded.last_action
            """,
            (account_phone, chat_id, None, ts, reason or '', next_eligible_ts or '', last_action or 'skip')
        )
        conn.commit()
    _write(_upd)


def get_chat_diag(account_phone: str, chat_id: int):
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT last_event_ts, last_skip_reason, next_eligible_ts, last_action FROM chat_state WHERE account_phone=? AND chat_id=?",
            (account_phone, chat_id)
        )
        row = cur.fetchone()
        if not row:
            return {"last_event_ts": None, "last_skip_reason": None, "next_eligible_ts": None, "last_action": None}
        return {"last_event_ts": row[0], "last_skip_reason": row[1], "next_eligible_ts": row[2], "last_action": row[3]}


def get_last_reply(account_phone: str, chat_id: int):
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT last_reply_ts FROM chat_state WHERE account_phone=? AND chat_id=?",
            (account_phone, chat_id)
        )
        row = cur.fetchone()
        if not row or not row[0]:
            return None
        try:
            return datetime.fromisoformat(row[0])
        except Exception:
            return None

# ---------- Join queue ----------
def add_join_source(source_line: str, username: Optional[str], invite_hash: Optional[str]):
    def _ins(conn):
        conn.execute(
            "INSERT INTO join_queue(source, username, invite_hash, status) VALUES(?,?,?,?)",
            (source_line, username, invite_hash, "queued")
        )
        conn.commit()
    _write(_ins)

def list_join_items(status: str=None, limit: int=200):
    with get_conn() as conn:
        if status:
            cur = conn.execute(
                "SELECT * FROM join_queue WHERE status=? ORDER BY id ASC LIMIT ?",
                (status, limit)
            )
        else:
            cur = conn.execute(
                "SELECT * FROM join_queue ORDER BY id ASC LIMIT ?",
                (limit,)
            )
        return cur.fetchall()

def set_join_status(item_id: int, status: str, err: str=None):
    def _upd(conn):
        conn.execute(
            "UPDATE join_queue SET status=?, last_error=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, err, item_id)
        )
        conn.commit()
    _write(_upd)

# ---------- Logging ----------
def log(level: str, source: str, payload: str,
        account_phone: Optional[str]=None, chat_id: Optional[int]=None, chat_title: Optional[str]=None):
    # DB
    if get_setting("logging_enabled", "1") == "1":
        def _ins(conn):
            conn.execute(
                "INSERT INTO logs(level, source, payload, account_phone, chat_id, chat_title) VALUES(?,?,?,?,?,?)",
                (level, source, payload, account_phone, chat_id, chat_title)
            )
            conn.commit()
        _write(_ins)
    # Console
    lvl = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARN": logging.WARNING, "ERROR": logging.ERROR}.get(level.upper(), logging.INFO)
    logging.getLogger("NeuroBot").log(lvl, f"{source}: {payload} | acc={account_phone} chat={chat_id} title={chat_title}")


def list_logs(limit: int = 200, level: str | None = None, source: str | None = None):
    """Возвращает последние логи как список dict."""
    q = "SELECT ts, level, source, account_phone, chat_id, chat_title, payload FROM logs"
    params = []
    where = []
    if level:
        where.append("level = ?"); params.append(level)
    if source:
        where.append("source = ?"); params.append(source)
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit or 200))
    with get_conn() as conn:
        cur = conn.execute(q, tuple(params))
        rows = cur.fetchall()
        # Преобразуем в list[dict]
        out = []
        for r in rows:
            out.append({
                "ts": r["ts"],
                "level": r["level"],
                "source": r["source"],
                "account_phone": r["account_phone"],
                "chat_id": r["chat_id"],
                "chat_title": r["chat_title"],
                "payload": r["payload"],
            })
        return out

def clear_logs():
    """Удалить все записи логов."""
    def _del(conn):
        conn.execute("DELETE FROM logs")
        conn.commit()
    _write(_del)


# ---------------- Schema migration ----------------
def _column_exists(conn, table: str, column: str) -> bool:
    try:
        cur = conn.execute(f"PRAGMA table_info({table})")
        for row in cur.fetchall():
            if row[1] == column:
                return True
    except Exception:
        return False
    return False

def _ensure_column(conn, table: str, column: str, add_sql: str):
    if not _column_exists(conn, table, column):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {add_sql}")
        conn.commit()

def migrate_schema():
    with get_conn() as conn:
        # chats extra columns
        try: _ensure_column(conn, "chats", "chat_username", "TEXT")
        except Exception: pass
        try: _ensure_column(conn, "chats", "chat_title", "TEXT")
        except Exception: pass
        # chat_state
        try: _ensure_column(conn, "chat_state", "last_reply_ts", "TEXT")
        except Exception: pass
        # diagnostics columns
        try: _ensure_column(conn, "chat_state", "last_event_ts", "TEXT")
        except Exception: pass
        try: _ensure_column(conn, "chat_state", "last_skip_reason", "TEXT")
        except Exception: pass
        try: _ensure_column(conn, "chat_state", "next_eligible_ts", "TEXT")
        except Exception: pass
        try: _ensure_column(conn, "chat_state", "last_action", "TEXT")
        except Exception: pass
        # account_limits/proxy
        try:
            conn.execute("""CREATE TABLE IF NOT EXISTS account_limits (
                account_phone TEXT PRIMARY KEY,
                safe_mode INTEGER DEFAULT 1,
                min_gap_ms INTEGER DEFAULT 60000,
                per_chat_min_gap_ms INTEGER DEFAULT 180000,
                replies_per_hour INTEGER DEFAULT 8,
                jitter_ms INTEGER DEFAULT 8000,
                pause_on_flood_wait_min INTEGER DEFAULT 45,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );""")
        except Exception: pass
        try:
            conn.execute("""CREATE TABLE IF NOT EXISTS account_api (
    account_phone TEXT PRIMARY KEY,
    api_id INTEGER,
    api_hash TEXT
);

CREATE TABLE IF NOT EXISTS account_proxy (
                account_phone TEXT PRIMARY KEY,
                enabled INTEGER DEFAULT 0,
                type TEXT DEFAULT 'SOCKS5',
                host TEXT,
                port INTEGER,
                username TEXT,
                password TEXT
            );""")
        except Exception: pass
        conn.commit()


# ---------- Account limits ----------
def set_account_limits(account_phone: str, *, safe_mode:int, min_gap_ms:int, per_chat_min_gap_ms:int, replies_per_hour:int, jitter_ms:int, pause_on_flood_wait_min:int):
    def _w(conn):
        conn.execute("INSERT INTO account_limits(account_phone,safe_mode,min_gap_ms,per_chat_min_gap_ms,replies_per_hour,jitter_ms,pause_on_flood_wait_min) VALUES(?,?,?,?,?,?,?) "
                     "ON CONFLICT(account_phone) DO UPDATE SET safe_mode=excluded.safe_mode,min_gap_ms=excluded.min_gap_ms,per_chat_min_gap_ms=excluded.per_chat_min_gap_ms,replies_per_hour=excluded.replies_per_hour,jitter_ms=excluded.jitter_ms,pause_on_flood_wait_min=excluded.pause_on_flood_wait_min,updated_at=CURRENT_TIMESTAMP",
                     (account_phone, int(safe_mode), int(min_gap_ms), int(per_chat_min_gap_ms), int(replies_per_hour), int(jitter_ms), int(pause_on_flood_wait_min)))
        conn.commit()
    _write(_w)
    try:
        log('INFO','proxy', f'Saved proxy for {phone}: enabled={int(enabled or 0)} host={host_s} port={port_i}', phone)
    except Exception:
        pass

def get_account_limits(account_phone: str) -> dict:
    with get_conn() as conn:
        cur = conn.execute("SELECT safe_mode,min_gap_ms,per_chat_min_gap_ms,replies_per_hour,jitter_ms,pause_on_flood_wait_min FROM account_limits WHERE account_phone=?", (account_phone,))
        r = cur.fetchone()
        if not r:
            return dict(safe_mode=0,min_gap_ms=60000,per_chat_min_gap_ms=180000,replies_per_hour=8,jitter_ms=8000,pause_on_flood_wait_min=45)
        return dict(safe_mode=r["safe_mode"], min_gap_ms=r["min_gap_ms"], per_chat_min_gap_ms=r["per_chat_min_gap_ms"], replies_per_hour=r["replies_per_hour"], jitter_ms=r["jitter_ms"], pause_on_flood_wait_min=r["pause_on_flood_wait_min"])

def count_replies_since(account_phone: str, since_iso: str) -> int:
    with get_conn() as conn:
        cur = conn.execute("SELECT COUNT(*) FROM logs WHERE account_phone=? AND source='bot' AND payload LIKE 'Replied:%' AND ts>=?", (account_phone, since_iso))
        row = cur.fetchone()
        return int(row[0]) if row else 0

# ---------- Account proxy ----------
def get_account_proxy(account_phone: str) -> dict:
    phone = _normalize_phone(account_phone)
    with get_conn() as conn:
        cur = conn.execute("SELECT enabled,type,host,port,username,password FROM account_proxy WHERE account_phone=?", (phone,))
        r = cur.fetchone()
        if not r:
            return dict(enabled=0, type="SOCKS5", host="", port=0, username="", password="")
        return dict(enabled=int(r["enabled"] or 0), type=(r["type"] or "SOCKS5"), host=(r["host"] or ""), port=int(r["port"] or 0), username=r["username"] or "", password=r["password"] or "")

def set_account_proxy(account_phone: str, enabled:int, type_:str, host:str, port:int, username:str, password:str):
    phone = _normalize_phone(account_phone)
    type_u = (type_ or "SOCKS5").upper()
    host_s = (host or "").strip()
    port_i = int(port or 0)
    user_s = (username or "").strip()
    pass_s = (password or "").strip()
    def _w(conn):
        conn.execute(
            "INSERT INTO account_proxy(account_phone,enabled,type,host,port,username,password) VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(account_phone) DO UPDATE SET enabled=excluded.enabled, type=excluded.type, host=excluded.host, port=excluded.port, username=excluded.username, password=excluded.password",
            (phone, int(enabled or 0), type_u, host_s, port_i, user_s, pass_s)
        )
        conn.commit()
    _write(_w)
    try:
        log('INFO','proxy', f'Saved proxy for {phone}: enabled={int(enabled or 0)} host={host_s} port={port_i}', phone)
    except Exception:
        pass


# ---------- Per-account AI prompts/CTA ----------
def set_account_prompt(account_phone: str, style: str, custom_prompt: str):
    def _w(conn):
        conn.execute(
            "INSERT INTO account_ai(account_phone,style,custom_prompt) VALUES(?,?,?) "
            "ON CONFLICT(account_phone) DO UPDATE SET style=excluded.style, custom_prompt=excluded.custom_prompt",
            (account_phone, style or "friendly", custom_prompt or ""))
        conn.commit()
    _write(_w)
    try:
        log('INFO','proxy', f'Saved proxy for {phone}: enabled={int(enabled or 0)} host={host_s} port={port_i}', phone)
    except Exception:
        pass

def get_account_prompt(account_phone: str):
    with get_conn() as conn:
        cur = conn.execute("SELECT style, custom_prompt FROM account_ai WHERE account_phone=?", (account_phone,))
        r = cur.fetchone()
        if not r:
            return None, None
        return r["style"] or "friendly", r["custom_prompt"] or ""

def set_account_cta(account_phone: str, enabled: bool, text: str):
    def _w(conn):
        conn.execute(
            "INSERT INTO account_ai(account_phone,cta_enabled,cta_text) VALUES(?,?,?) "
            "ON CONFLICT(account_phone) DO UPDATE SET cta_enabled=excluded.cta_enabled, cta_text=excluded.cta_text",
            (account_phone, 1 if enabled else 0, text or ""))
        conn.commit()
    _write(_w)
    try:
        log('INFO','proxy', f'Saved proxy for {phone}: enabled={int(enabled or 0)} host={host_s} port={port_i}', phone)
    except Exception:
        pass

def get_account_cta(account_phone: str):
    with get_conn() as conn:
        cur = conn.execute("SELECT cta_enabled, cta_text FROM account_ai WHERE account_phone=?", (account_phone,))
        r = cur.fetchone()
        if not r:
            return 0, ""
        return int(r["cta_enabled"] or 0), r["cta_text"] or ""

def migrate_chat_state():
    """Ensure chat_state has new diagnostic columns."""
    cols = set()
    with get_conn() as conn:
        cur = conn.execute("PRAGMA table_info(chat_state)")
        for row in cur.fetchall():
            cols.add(row[1])
        def _try(sql):
            try:
                conn.execute(sql)
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    pass
                else:
                    raise
        if "last_event_ts" not in cols:
            _try("ALTER TABLE chat_state ADD COLUMN last_event_ts TEXT")
        if "last_skip_reason" not in cols:
            _try("ALTER TABLE chat_state ADD COLUMN last_skip_reason TEXT")
        if "next_eligible_ts" not in cols:
            _try("ALTER TABLE chat_state ADD COLUMN next_eligible_ts TEXT")
        if "last_action" not in cols:
            _try("ALTER TABLE chat_state ADD COLUMN last_action TEXT DEFAULT 'skip'")
        conn.commit()

# call on import
try:
    migrate_chat_state()
except Exception:
    pass


# Backward-compatible alias
def remove_account(phone: str):
    return delete_account(phone)


# Ensure schema is up to date on import (safe)
try:
    migrate_schema()
except Exception:
    pass




def _rebuild_chat_state(conn):
    """Recreate chat_state with correct columns if the table is corrupt (e.g., a column literally named 'TEXT')."""
    cur = conn.execute("PRAGMA table_info(chat_state)")
    cols = {row[1] for row in cur.fetchall()}
    wanted = ["account_phone","chat_id","last_event_ts","last_reply_ts","next_eligible_ts","last_skip_reason","last_action"]
    if "TEXT" in cols or not set(["last_event_ts","last_reply_ts","next_eligible_ts","last_skip_reason"]).issubset(cols):
        # keep existing data best-effort
        try:
            conn.execute("""CREATE TABLE IF NOT EXISTS chat_state_new(
                account_phone TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                last_event_ts INTEGER DEFAULT 0,
                last_reply_ts INTEGER DEFAULT 0,
                next_eligible_ts INTEGER DEFAULT 0,
                last_skip_reason TEXT DEFAULT '',
                last_action TEXT DEFAULT '',
                PRIMARY KEY(account_phone, chat_id)
            )""")
            # copy over anything we have
            existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(chat_state)").fetchall()]
            copy_cols = [c for c in wanted if c in existing_cols]
            if copy_cols:
                cols_sql = ",".join(copy_cols)
                conn.execute(f"INSERT OR REPLACE INTO chat_state_new({cols_sql}) SELECT {cols_sql} FROM chat_state")
            conn.execute("DROP TABLE chat_state")
            conn.execute("ALTER TABLE chat_state_new RENAME TO chat_state")
        except Exception:
            pass

def migrate_schema():
    global MIGRATION_DONE
    if MIGRATION_DONE: 
        return
    with get_conn() as conn:
        # base tables
        conn.execute("CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT UNIQUE, session_path TEXT, enabled INTEGER DEFAULT 0, created_at TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS account_proxy(account_phone TEXT PRIMARY KEY, enabled INTEGER, type TEXT, host TEXT, port INTEGER, username TEXT, password TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS chat_state(account_phone TEXT, chat_id INTEGER, last_reply_ts INTEGER DEFAULT 0, last_event_ts INTEGER DEFAULT 0, last_skip_reason TEXT DEFAULT '', next_eligible_ts INTEGER DEFAULT 0, last_action TEXT DEFAULT '')")
        # Add missing columns (safe)
        _ensure_chat_state_columns(conn)
        # Rebuild if broken
        _rebuild_chat_state(conn)
    MIGRATION_DONE = True
