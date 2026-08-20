"""네이버 예약 페이지에서 특정 날짜의 예약 가능 시간대를 읽어온다.

전략:
1) 페이지가 백그라운드로 받아오는 JSON 응답을 가로채서 시간대/가능여부/잔여수를 추출 (주 방식)
2) 실패하면 화면(DOM)에서 HH:MM 패턴의 활성 버튼을 찾는 폴백

주의: 이 코드를 작성한 환경에서는 naver.com 접속이 차단되어 있어 실제 응답 구조를
검증하지 못했다. 파서는 흔한 키 이름을 휴리스틱으로 탐색하며, 둘 다 실패하면
가로챈 JSON 원본을 호출 측에 넘겨 텔레그램으로 전달해 파서를 보정할 수 있게 한다.
"""
import json
import re
import random
import time
from dataclasses import dataclass, field

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

    page = browser.new_page(
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
                   "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
        viewport={"width": 390, "height": 844},
    )

    def on_response(response):
        try:
            ctype = response.headers.get("content-type", "")
            if "json" not in ctype:
                return
            body = response.text()
            if body and len(body) < 2_000_000 and _looks_relevant(response.url, body):
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
        result.captured_json = [(u, b[:15000]) for u, b in captured[:3]]
        page.close()
        return result

    # 2차 폴백: DOM에서 활성화된 시간 버튼 탐색
    try:
        dom_times = page.evaluate(
            """() => {
                const out = [];
                for (const el of document.querySelectorAll('button, a, [role="button"], li')) {
                    const m = (el.innerText || '').match(/\\b\\d{1,2}:\\d{2}\\b/);
                    if (!m) continue;
                    const cls = el.className || '';
                    const disabled = el.disabled || el.getAttribute('aria-disabled') === 'true'
                        || /disabled|soldout|dimmed|unselect/i.test(String(cls));
                    if (!disabled) out.push(m[0]);
                }
                return out;
            }"""
        )
        if dom_times:
            uniq = sorted({f"{int(t.split(':')[0]):02d}:{t.split(':')[1]}" for t in dom_times})
            result.ok, result.method = True, "dom"
            result.slots = [(t, None) for t in uniq]
            page.close()
            return result
    except Exception:
        pass

    # 둘 다 실패: 디버깅 재료를 챙겨서 반환
    result.error = "시간표를 JSON에서도 화면에서도 찾지 못함"
    result.captured_json = [(u, b[:15000]) for u, b in captured[:5]]
    try:
        result.screenshot = page.screenshot(full_page=False)
    except Exception:
        pass
    page.close()
    return result
