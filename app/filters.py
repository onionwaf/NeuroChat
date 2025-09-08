from langdetect import detect, LangDetectException
import hashlib
import re
from . import db

_CYR = re.compile('[\u0400-\u04FF]')
_LAT = re.compile('[A-Za-z]')

def words_count_ok(text: str, min_words: int) -> bool:
    return len(text.split()) >= max(1, min_words)

def language_ok(text: str, allow_ru: bool, allow_en: bool) -> bool:
    """Robust language gate with Cyrillic family and fallbacks."""
    has_cyr = bool(_CYR.search(text))
    has_lat = bool(_LAT.search(text))
    try:
        code = (detect(text) or '').lower()
    except LangDetectException:
        return (has_cyr and allow_ru) or (has_lat and allow_en) or (allow_ru or allow_en)
    if code in {'ru','uk','bg','sr','mk','kk','be'}:
        return bool(allow_ru)
    if code in {'en','und'}:
        return bool(allow_en)
    return (has_cyr and allow_ru) or (has_lat and allow_en) or (allow_ru or allow_en)

def unique_ok(account_phone: str, chat_id: int, text: str) -> bool:
    h = hashlib.sha256(text.strip().lower().encode('utf-8')).hexdigest()
    return db.store_message_hash(account_phone, chat_id, h)

def should_accept(text: str, account_phone: str, chat_id: int, min_words: int, allow_ru: bool, allow_en: bool, anti_spam_enabled: bool) -> bool:
    if not words_count_ok(text, min_words): return False
    if not language_ok(text, allow_ru, allow_en): return False
    if anti_spam_enabled and not unique_ok(account_phone, chat_id, text): return False
    return True
