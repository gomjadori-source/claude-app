"""텔레그램 알림 전송. KST 01~07시에는 무음(진동/소리 없음)으로 보낸다."""
import io
import json
import os
from datetime import datetime, timedelta, timezone

import requests

KST = timezone(timedelta(hours=9))
QUIET_HOURS = range(1, 7)  # KST 01:00 ~ 06:59

_API = "https://api.telegram.org/bot{token}/{method}"


def _is_quiet_now() -> bool:
    return datetime.now(KST).hour in QUIET_HOURS


def _post(method: str, data: dict, files: dict | None = None):
    token = os.environ["TELEGRAM_TOKEN"]
    data = {"chat_id": os.environ["TELEGRAM_CHAT_ID"], **data}
    if _is_quiet_now():
        data["disable_notification"] = True
    r = requests.post(_API.format(token=token, method=method), data=data, files=files, timeout=20)
    if not r.ok:
        print(f"[텔레그램] 전송 실패 ({method}): HTTP {r.status_code}")
    return r.ok


def send_message(text: str, button_url: str | None = None, button_text: str = "🚀 예약 페이지 열기"):
    data = {"text": text, "parse_mode": "HTML"}
    if button_url:
        data["reply_markup"] = json.dumps(
            {"inline_keyboard": [[{"text": button_text, "url": button_url}]]}
        )
    return _post("sendMessage", data)


def send_photo(image_bytes: bytes, caption: str):
    return _post(
        "sendPhoto",
        {"caption": caption},
        files={"photo": ("screenshot.png", image_bytes, "image/png")},
    )


def send_document(filename: str, content: str, caption: str):
    return _post(
        "sendDocument",
        {"caption": caption},
        files={"document": (filename, io.BytesIO(content.encode()), "application/json")},
    )
