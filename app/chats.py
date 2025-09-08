from typing import Tuple, Optional, List, Set
import re, asyncio
from telethon.tl import functions

async def _safe_get_full_channel(client, c):
    try:
        GetFullChannel = getattr(functions.channels, 'GetFullChannel', None)
        if GetFullChannel:
            return await client(GetFullChannel(channel=c))
    except Exception:
        return None
    return None
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors import RPCError, UserAlreadyParticipantError
from . import db

def _query_variants(q: str) -> List[str]:
    q = (q or '').strip()
    if not q:
        return []
    tokens = [t for t in re.split(r'[\s,;/|]+', q) if t]
    base = set()
    # base forms
    base.add(q)
    if len(tokens) > 1:
        base.add(' '.join(tokens))
        base.add(' '.join(tokens[:2]))
    # single tokens and hashtagged
    for t in tokens:
        base.add(t)
        if len(t) >= 3:
            base.add(f'#{t}')
            base.add(f'{t} chat')
            base.add(f'{t} group')
            base.add(f'{t} community')
            base.add(f'{t} форум')
            base.add(f'{t} чат')
            base.add(f'{t} группа')
    # simple domain synonyms
    syn = {
        'crypto': ['крипто', 'bitcoin', 'btc', 'trading', 'trade'],
        'ai': ['искусственный интеллект', 'нейросеть', 'ml', 'machine learning'],
        'design': ['дизайн', 'ui', 'ux', 'web'],
        'music': ['музыка', 'audio', 'producers', 'beat'],
        'job': ['работа', 'vacancy', 'вакансии', 'freelance'],
        'gamedev': ['игры', 'unity', 'unreal', 'game dev'],
        'python': ['питон', 'backend', 'django', 'fastapi'],
    }
    lowers = [t.lower() for t in tokens]
    for k, vals in syn.items():
        if k in lowers or any(v in lowers for v in vals):
            for v in [k] + vals:
                base.add(v)
                base.add(f'{v} чат')
                base.add(f'{v} group')
    # de-duplicate while preserving a rough priority
    ordered = []
    seen = set()
    for item in [q] + list(base):
        if item and item not in seen:
            ordered.append(item)
            seen.add(item)
    # cap to avoid over-querying
    return ordered[:40]


async def search_public_chats(client, query: str, limit: int=20):
    try:
        res = await client(SearchRequest(q=query, limit=limit))
        return res.chats
    except RPCError as e:
        db.log("ERROR", "chats", f"Search failed: {e}")
        return []

async def search_public_chats_plus(client, query: str, per_query_limit: int=50):
    """Broader search: multiple variants + try to fetch participant counts for sorting."""
    seen: Set[int] = set()
    results = []
    for q in _query_variants(query):
        try:
            r = await client(SearchRequest(q=q, limit=per_query_limit))
            for c in r.chats:
                if c.id in seen: continue
                item = {"entity": c, "participants": None}
                # try to fetch full channel for participants count
                try:
                    if getattr(c, "megagroup", False) or getattr(c, "broadcast", False):
                        full = await _safe_get_full_channel(client, c)
                        if full is not None:
                            p = getattr(getattr(full, 'full_chat', None), 'participants_count', None)
                            item['participants'] = p
                except RPCError:
                    pass
                results.append(item)
                seen.add(c.id)
        except RPCError as e:
            db.log("ERROR", "chats", f"Search variant '{q}' failed: {e}")

    # sort: participants desc, then title match
    def sort_key(it):
        c = it["entity"]
        p = it.get("participants") or -1
        title = (getattr(c, "title", "") or getattr(c, "username", "") or "").lower()
        score = 0
        ql = query.lower()
        if ql in title: score += 1
        return (-p, -score)
    results.sort(key=sort_key)
    return [it["entity"] for it in results]

def parse_chat_line(line: str) -> Tuple[Optional[str], Optional[str]]:
    s = (line or "").strip()
    if not s: return None, None
    if s.startswith("@"): return s[1:], None
    m = re.match(r"https?://t\.me/\+([A-Za-z0-9_-]+)", s)
    if m: return None, m.group(1)
    m = re.match(r"tg://join\?invite=([A-Za-z0-9_-]+)", s)
    if m: return None, m.group(1)
    m = re.match(r"https?://t\.me/([A-Za-z0-9_]+)", s)
    if m: return m.group(1), None
    return s, None

async def join_chat_by_username(client, username: str) -> bool:
    if username.startswith("@"): username = username[1:]
    try:
        await client(JoinChannelRequest(username))
        return True
    except UserAlreadyParticipantError:
        return True
    except RPCError as e:
        db.log("ERROR", "join", f"Join by username failed @{username}: {e}")
        return False

async def join_by_invite(client, invite_hash: str) -> bool:
    try:
        await client(ImportChatInviteRequest(invite_hash))
        return True
    except UserAlreadyParticipantError:
        return True
    except RPCError as e:
        db.log("ERROR", "join", f"Join by invite failed +{invite_hash}: {e}")
        return False
