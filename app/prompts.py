from typing import List, Dict

SYSTEM_TEMPLATES = {
    "friendly": "Ты дружелюбный помощник. Отвечай кратко, позитивно и на языке пользователя.",
    "expert": "Ты экспертный ассистент. Давай точные и практичные рекомендации.",
    "funny": "Ты остроумный ассистент. Допускается лёгкая ирония, но без токсичности."
}

DELIM = "\n\n===USER_MESSAGE===\n"

def build_prompt(style: str, custom_prompt: str, user_text: str) -> str:
    style = (style or "friendly").lower()
    sys_base = SYSTEM_TEMPLATES.get(style, SYSTEM_TEMPLATES["friendly"])
    sys_extra = (custom_prompt or "").strip()
    system = sys_base if not sys_extra else f"{sys_base}\n\nИнструкции:\n{sys_extra}"
    return f"{system}{DELIM}{user_text or ''}"


def get_global_prompt():
    """Read global prompt settings from DB; returns (style, custom_prompt)."""
    try:
        from . import db
    except Exception:
        # Fallback defaults if DB not ready at import time
        return "friendly", ""
    style = db.get_setting("global_prompt_style", "friendly")
    custom = db.get_setting("global_custom_prompt", "")
    return (style or "friendly"), (custom or "")
