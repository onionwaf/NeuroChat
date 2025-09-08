import os, requests, time, threading, random
from collections import deque
from typing import Optional, List, Dict
from . import db
try:
    from mistralai import Mistral
except Exception:
    Mistral = None

DEFAULT_MODEL = "mistral-large-latest"
MISTRAL_BASE = os.environ.get("MISTRAL_BASE", "https://api.mistral.ai")
DELIM = "\n\n===USER_MESSAGE===\n"

class _RateLimiter:
    def __init__(self):
        self.lock = threading.Lock()
        self.window = 60.0
        self.ts = deque()

    def acquire(self, rpm: int):
        rpm = max(1, int(rpm or 1))
        while True:
            with self.lock:
                now = time.time()
                while self.ts and now - self.ts[0] >= self.window:
                    self.ts.popleft()
                if len(self.ts) < rpm:
                    self.ts.append(now)
                    return
                wait = self.window - (now - self.ts[0]) + 0.01
            time.sleep(max(0.05, wait))

RATE = _RateLimiter()

def _sleep_with_jitter(base: float, jitter_ms: int):
    j = (random.random() - 0.5) * 2 * (jitter_ms/1000.0)
    time.sleep(max(0.0, base + j))

def _build_messages_from_prompt(prompt: str) -> List[Dict[str,str]]:
    if DELIM in prompt:
        sys_txt, user_txt = prompt.split(DELIM, 1)
        sys_txt = (sys_txt or "").strip()
        user_txt = (user_txt or "").strip()
        msgs = []
        if sys_txt:
            msgs.append({"role":"system","content":sys_txt})
        msgs.append({"role":"user","content":user_txt})
        return msgs
    return [{"role":"user","content":prompt}]

def ask_mistral(prompt: str, api_key: Optional[str]=None, model: Optional[str]=None, max_tokens: int=500) -> str:
    api_key = api_key or db.get_setting("mistral_api_key", "")
    model = model or db.get_setting("mistral_model", DEFAULT_MODEL)
    if not api_key:
        raise RuntimeError("Mistral API key is not set.")

    rpm = int(db.get_setting("mistral_rpm", "10"))
    max_retries = int(db.get_setting("mistral_retries", db.get_setting("mistral_max_retries", "6")))
    base_delay = int(db.get_setting("mistral_retry_base_delay", "2"))
    jitter_ms = int(db.get_setting("mistral_retry_jitter_ms", "250"))

    RATE.acquire(rpm)
    messages = _build_messages_from_prompt(prompt)
    last_err = None

    for attempt in range(max_retries + 1):
        try:
            if Mistral:
                client = Mistral(api_key=api_key)
                resp = client.chat.complete(model=model, messages=messages, max_tokens=max_tokens)
                if hasattr(resp, "choices") and resp.choices:
                    return resp.choices[0].message.content
        except Exception as e:
            last_err = e
            db.log("WARN","mistral_api",f"SDK attempt {attempt+1} failed: {e}")

        try:
            url = f"{MISTRAL_BASE}/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            temperature = float(db.get_setting("mistral_temp","0.6"))
            timeout_sec = int(db.get_setting("mistral_timeout","30"))
            payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
            import requests
            r = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)
            if r.status_code == 429:
                ra = r.headers.get("Retry-After")
                delay = float(ra) if ra and ra.isdigit() else base_delay
                db.log("WARN","mistral_api",f"429 Too Many Requests → wait {delay}s (attempt {attempt+1}/{max_retries})")
                _sleep_with_jitter(delay, jitter_ms); continue
            if 500 <= r.status_code < 600:
                delay = base_delay * (2 ** attempt)
                db.log("WARN","mistral_api",f"{r.status_code} server error → backoff {delay}s (attempt {attempt+1}/{max_retries})")
                _sleep_with_jitter(delay, jitter_ms); continue
            r.raise_for_status()
            j = r.json()
            return j["choices"][0]["message"]["content"]
        except Exception as e:
            last_err = e
            delay = base_delay * (2 ** attempt)
            db.log("WARN","mistral_api",f"HTTP {type(e).__name__}: {e} → backoff {delay}s (attempt {attempt+1}/{max_retries})")
            _sleep_with_jitter(delay, jitter_ms)

    if last_err:
        raise last_err
    raise RuntimeError("Mistral request failed")
