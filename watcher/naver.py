"""네이버 예약 페이지에서 특정 날짜의 예약 가능 시간대를 읽어온다.

방식: 페이지가 백그라운드로 받아오는 JSON 응답을 가로채 시간대/가능여부/잔여수를 추출한다.
신뢰할 수 있는 JSON을 못 읽으면 '자리 없음'이 아니라 '읽기 실패'로 처리한다.
(과거엔 화면 텍스트에서 HH:MM을 긁는 DOM 폴백이 있었으나, 네이버 CAPTCHA 화면의
글자를 실제 빈자리로 오인해 가짜 알림을 보냈기에 제거했다.)

ncpt.naver.com/wcpt 호출이 감지되면 네이버 봇 차단(CAPTCHA)에 막힌 것으로 본다.
"""
import json
import os
import re
import random
import time
from dataclasses import dataclass, field

DEBUG = bool(os.environ.get("DEBUG_CAPTURE"))

from playwright.sync_api import Browser

TIME_RE = re.compile(r"(?<![\d:])(\d{1,2}):(\d{2})(?!\d)")

TIME_KEYS = {"time", "starttime", "start_time", "begintime", "slottime", "timetext", "starttimetext"}
AVAIL_KEYS = {"isavailable", "available", "bookable", "isbookable", "selectable", "isselectable", "issoldout", "soldout"}
STOCK_KEYS = {"stock", "remain", "remaincount", "remainstock", "leftcount", "availablecount", "remainingcount", "capacity"}
MINUTE_KEYS = {"minute", "minutes", "startminute"}


@dataclass
class CheckResult:
    ok: bool = False
    method: str = ""            # "json" | "dom"
    slots: list = field(default_factory=list)  # [(time "HH:MM", stock int|None)]
    captured_json: list = field(default_factory=list)
    screenshot: bytes | None = None
    error: str = ""


def _norm_key(k: str) -> str:
    return k.replace("_", "").replace("-", "").lower()


def _to_time(value) -> str | None:
    if isinstance(value, str):
        m = TIME_RE.search(value)
        if m and int(m.group(1)) < 24 and int(m.group(2)) < 60:
            return f"{int(m.group(1)):02d}:{m.group(2)}"
        if value.isdigit():
            value = int(value)
    if isinstance(value, (int, float)) and 0 <= value < 1440 and value == int(value):
        return f"{int(value) // 60:02d}:{int(value) % 60:02d}"
    return None


def _extract_slots(node, out: list):
    """JSON 트리를 재귀 순회하며 (시간, 가능여부, 잔여수) 형태의 오브젝트를 찾는다."""
    if isinstance(node, list):
        for item in node:
            _extract_slots(item, out)
        return
    if not isinstance(node, dict):
        return

    time_val, avail_val, stock_val = None, None, None
    for k, v in node.items():
        nk = _norm_key(k)
        if time_val is None and (nk in TIME_KEYS or nk in MINUTE_KEYS):
            time_val = _to_time(v)
        elif nk in AVAIL_KEYS and isinstance(v, bool):
            avail_val = (not v) if "soldout" in nk else v
        elif stock_val is None and nk in STOCK_KEYS and isinstance(v, (int, float)):
            stock_val = int(v)

    if time_val is not None and (avail_val is not None or stock_val is not None):
        available = avail_val if avail_val is not None else (stock_val or 0) > 0
        if available:
            out.append((time_val, stock_val))
        return  # 슬롯 오브젝트로 확정되면 그 하위는 더 안 판다

    for v in node.values():
        _extract_slots(v, out)


def _looks_relevant(url: str, body: str) -> bool:
    if "booking" not in url and "naver" not in url:
        return False
    lowered = body[:20000].lower()
    return any(w in lowered for w in ("schedule", "slot", "time", "stock", "remain", "bizitem"))


def check_date(browser: Browser, base_url: str, date_str: str) -> CheckResult:
    result = CheckResult()
    captured: list[tuple[str, str]] = []
    flags = {"captcha": False}

    page = browser.new_page(
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
                   "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
        viewport={"width": 390, "height": 844},
    )

    def on_response(response):
        try:
            # 네이버 봇 차단(CAPTCHA) 엔드포인트가 호출되면 차단 상태로 표시
            if "ncpt.naver.com" in response.url or "/wcpt/" in response.url:
                flags["captcha"] = True
            ctype = response.headers.get("content-type", "")
            if "json" not in ctype:
                return
            body = response.text()
            # 진단 모드에서는 관련성 필터를 끄고 모든 JSON을 담아, 실제 스케줄
            # 엔드포인트가 필터에 걸러지고 있는 건 아닌지까지 확인할 수 있게 한다.
            if body and len(body) < 2_000_000 and (DEBUG or _looks_relevant(response.url, body)):
                captured.append((response.url, body))
        except Exception:
            pass

    page.on("response", on_response)

    sep = "&" if "?" in base_url else "?"
    url = f"{base_url}{sep}date={date_str}"

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_load_state("networkidle", timeout=15_000)
    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
        try:
            result.screenshot = page.screenshot(full_page=False)
        except Exception:
            pass
        page.close()
        return result

    time.sleep(random.uniform(0.5, 1.5))

    # 1차: 가로챈 JSON에서 슬롯 추출
    slots: list = []
    for resp_url, body in captured:
        try:
            _extract_slots(json.loads(body), slots)
        except (json.JSONDecodeError, RecursionError):
            continue
    if slots:
        seen = {}
        for t, stock in slots:
            if t not in seen or (stock is not None and (seen[t] is None or stock > seen[t])):
                seen[t] = stock
        result.ok, result.method = True, "json"
        result.slots = sorted(seen.items())
        # 진단용: 성공했을 때도 원본을 실어 보내 파서를 실제 구조에 맞게 보정한다.
        result.captured_json = [(u, b[:15000]) for u, b in captured[:8]]
        page.close()
        return result

    # JSON에서 슬롯을 못 찾음. 예전엔 화면(DOM)에서 HH:MM을 긁는 폴백이 있었으나,
    # 네이버 CAPTCHA 화면의 텍스트를 실제 빈자리로 오인해 '가짜 알림'을 보냈기에 제거했다.
    # 신뢰할 수 있는 JSON을 못 읽었으면 '자리 없음'이 아니라 '읽기 실패'로 처리한다.
    if flags["captcha"]:
        result.error = "네이버 봇 차단(CAPTCHA) 화면이 떴습니다 — 자동 접근이 막혔습니다"
    else:
        result.error = "예약 스케줄 JSON을 찾지 못했습니다 (페이지 구조 변경 가능성)"
    result.captured_json = [(u, b[:15000]) for u, b in captured[:5]]
    try:
        result.screenshot = page.screenshot(full_page=False)
    except Exception:
        pass
    page.close()
    return result
