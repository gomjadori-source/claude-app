"""실행 간 상태 저장.

공개 저장소에 커밋되므로 가게명/날짜/시간은 전부 SHA-256 해시로만 기록한다.
구조:
{
  "open": {"<타겟+날짜 해시>": {"<슬롯 해시>": last_seen_ts}},
  "targets": {"<타겟 해시>": {"fail": n, "fail_alerted": bool, "debug_sent": bool, "last_ok": ts}},
  "_heartbeat": "YYYY-MM-DD"
}
"""
import hashlib
import json
import time
from pathlib import Path

STATE_PATH = Path(__file__).resolve().parent.parent / "state.json"
OPEN_TTL = 7 * 24 * 3600  # 지난 날짜 기록 자동 정리용


def h(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def load() -> dict:
    if STATE_PATH.exists():
        try:
            state = json.loads(STATE_PATH.read_text())
        except json.JSONDecodeError:
            state = {}
    else:
        state = {}
    state.setdefault("open", {})
    state.setdefault("targets", {})

    cutoff = time.time() - OPEN_TTL
    for group in list(state["open"]):
        slots = {k: ts for k, ts in state["open"][group].items() if ts >= cutoff}
        if slots:
            state["open"][group] = slots
        else:
            del state["open"][group]
    return state


def save(state: dict):
    STATE_PATH.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n")


def target_entry(state: dict, target_hash: str) -> dict:
    return state["targets"].setdefault(
        target_hash, {"fail": 0, "fail_alerted": False, "debug_sent": False, "last_ok": 0}
    )
