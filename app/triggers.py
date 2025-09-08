
# Trigger utilities: normalization + matching + splitting
import re

_SPLIT_RE = re.compile(r"[,;\n]+")

def split_triggers(s: str):
    s = (s or "").strip()
    if not s:
        return []
    return [t.strip() for t in _SPLIT_RE.split(s) if t.strip()]

# --- Normalization helpers ---
# Unite different dashes, punctuation and whitespace, lowercase, 'ё'->'е'
_DASHES = "\u2010\u2011\u2012\u2013\u2014\u2212-"

def _build_punct_re():
    # IMPORTANT (Windows fix): escape '-' so the char class doesn't create a range like '−-'
    chars = r"\s" + re.escape(_DASHES) + r"\.,!?:;\[\](){}<>\"'`~@#$%^&*_+=/\\"
    return re.compile("[" + chars + "]+")

_PUNCT = _build_punct_re()

def _normalize(s: str) -> str:
    s = (s or "").lower().replace("ё", "е")
    s = _PUNCT.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def has_trigger(text: str, triggers):
    if not triggers:
        return False
    nt = _normalize(text)
    if not nt:
        return False
    for t in triggers:
        t = (t or "").strip()
        if not t:
            continue
        ntk = _normalize(t)
        if ntk and ntk in nt:
            return True
    return False


import re
_DASHES = "-‑–—"
_LATIN_EQUIV = {"а":"a","е":"e","о":"o","р":"p","с":"c","у":"y","х":"x","к":"k","м":"m","т":"t","в":"b","н":"h",
                "А":"A","Е":"E","О":"O","Р":"P","С":"C","У":"Y","Х":"X","К":"K","М":"M","Т":"T","В":"B","Н":"H"}

def _normalize(s: str) -> str:
    if not s: return ""
    s2 = s.strip().lower()
    s2 = _PUNCT_RE.sub(" ", s2)
    s2 = s2.replace("ё","е")
    s2 = "".join(_LATIN_EQUIV.get(ch, ch) for ch in s2)
    s2 = s2.replace("юсдт","usdt").replace("усдт","usdt")
    return s2

def has_trigger(text: str, triggers):
    nt = _normalize(text)
    for t in triggers or []:
        if _normalize(t) in nt:
            return True
    return False

_PUNCT_RE = re.compile(rf"[\s{re.escape(_DASHES)}]+")
