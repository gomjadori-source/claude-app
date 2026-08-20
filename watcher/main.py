"""네이버 예약 빈자리 감시 → 텔레그램 알림 (알림 전용, 자동 예약 아님).

- 자리가 '없음 → 있음'으로 바뀌는 순간에만 알린다 (계속 열려 있으면 침묵).
- 읽기 실패는 '자리 없음'과 구분해서 직전 상태를 유지한다 (가짜 알림 방지).
- 같은 타겟이 3회 연속 읽기 실패하면 경고 + 스크린샷을 한 번만 보낸다.
- 파서가 응답 구조를 해석 못 하면 가로챈 JSON을 텔레그램으로 보내 보정할 수 있게 한다.
"""
import os
import random
import sys
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

import naver
import notify
import sheet
import state as state_mod

FAIL_ALERT_THRESHOLD = 3


def check_target(browser, target, st) -> list[dict]:
    """한 타겟의 모든 날짜를 확인하고, 새로 열린 슬롯 목록을 돌려준다."""
    thash = state_mod.h(target["name"], target["url"])
    entry = state_mod.target_entry(st, thash)
    masked = sheet.mask(target["name"])
    new_slots, any_ok, first_failure = [], False, None

    for date_str in target["dates"]:
        result = naver.check_date(browser, target["url"], date_str)

        if not result.ok:
            print(f"[{masked}] {date_str}: 읽기 실패 ({result.error}) → 직전 상태 유지")
            if first_failure is None:
                first_failure = (date_str, result)
            continue

        any_ok = True
        wanted = [
            (t, stock) for t, stock in result.slots
            if sheet.time_matches(t, target["times"])
            and (stock is None or stock >= target["qty"])
        ]
        print(f"[{masked}] {date_str}: 확인 완료({result.method}) — "
              f"열린 시간 {len(result.slots)}개, 조건 일치 {len(wanted)}개")

        # 진단 모드: 실행당 1회, 파서 판단 + 가로챈 JSON(있으면 전부)을 텔레그램으로 보낸다.
        if os.environ.get("DEBUG_CAPTURE") and not check_target._dumped:
            urls = "\n".join(f"- {u}" for u, _ in result.captured_json) or "(가로챈 JSON 없음)"
            bodies = "\n\n".join(f"### {u}\n{b}" for u, b in result.captured_json)
            blob = (f"타겟: {target['name']}\n날짜: {date_str}\n"
                    f"읽은 방식: {result.method}\n"
                    f"파서가 '열림'으로 판단한 슬롯: {result.slots}\n\n"
                    f"가로챈 JSON 응답 목록:\n{urls}\n\n{bodies}")
            notify.send_document("naver-response.txt", blob,
                                 f"[진단] {target['name']} {date_str} · 방식={result.method}")
            check_target._dumped = True

        group = state_mod.h(thash, date_str)
        prev_open = st["open"].get(group, {})
        now_open = {}
        for t, stock in wanted:
            shash = state_mod.h(group, t)
            now_open[shash] = time.time()
            if shash not in prev_open:
                new_slots.append({"date": date_str, "time": t, "stock": stock,
                                  "url": target["url"]})
        st["open"][group] = now_open  # 성공한 날짜만 통째로 교체 (닫힌 자리 정리)

    if any_ok:
        entry.update({"fail": 0, "fail_alerted": False, "last_ok": time.time()})
    elif first_failure:
        entry["fail"] += 1
        never_succeeded = entry["last_ok"] == 0
        if (entry["fail"] >= FAIL_ALERT_THRESHOLD or never_succeeded) and not entry["fail_alerted"]:
            date_str, result = first_failure
            notify.send_message(
                f"⚠️ <b>[{target['name']}]</b> 자리 정보를 읽지 못하고 있어요.\n"
                f"연속 {entry['fail']}회 실패 (예: {date_str})\n"
                f"사유: {result.error}\n"
                f"복구되면 자동으로 다시 감시합니다.",
                button_url=target["url"], button_text="문제 페이지 열어보기")
            if result.screenshot:
                notify.send_photo(result.screenshot, f"[{target['name']}] 실패 시점 화면")
            if result.captured_json and not entry["debug_sent"]:
                blob = "\n\n".join(f"### {u}\n{b}" for u, b in result.captured_json)
                notify.send_document(
                    "captured.json.txt", blob,
                    f"[{target['name']}] 파서가 해석 못 한 응답 원본 — 개발자에게 전달하면 보정 가능")
                entry["debug_sent"] = True
            entry["fail_alerted"] = True

    return new_slots


def send_alerts(target, slots):
    lines = [f"🚨 <b>[{target['name']}] 빈자리 발견!</b>", ""]
    for s in sorted(slots, key=lambda x: (x["date"], x["time"])):
        stock_txt = f" (잔여 {s['stock']})" if s["stock"] is not None else ""
        lines.append(f"📅 {s['date']} {s['time']}{stock_txt}")
    lines += ["", f"👥 {target['qty']}명 기준 · 예약은 직접 진행해주세요"]
    first = min(slots, key=lambda x: (x["date"], x["time"]))
    sep = "&" if "?" in target["url"] else "?"
    notify.send_message("\n".join(lines), button_url=f"{target['url']}{sep}date={first['date']}")


def maybe_heartbeat(st, targets):
    today = datetime.now(notify.KST).strftime("%Y-%m-%d")
    if datetime.now(notify.KST).hour != 9 or st.get("_heartbeat") == today:
        return
    lines = [f"🤖 <b>예약 감시 봇 작동 중</b> — 타겟 {len(targets)}개", ""]
    for t in targets:
        entry = st["targets"].get(state_mod.h(t["name"], t["url"]))
        if entry and entry["last_ok"]:
            ago = int((time.time() - entry["last_ok"]) / 60)
            lines.append(f"✅ {t['name']}: {ago}분 전 확인 성공")
        elif entry and entry["fail"]:
            lines.append(f"⚠️ {t['name']}: 연속 {entry['fail']}회 읽기 실패 중")
        else:
            lines.append(f"⏳ {t['name']}: 아직 확인 전")
    notify.send_message("\n".join(lines))
    st["_heartbeat"] = today


def main():
    try:
        targets = sheet.load_targets()
    except Exception as e:
        # 공개 저장소 로그에는 예외 타입과 힌트만 남기고, 상세 메시지는 텔레그램으로만 보낸다
        hints = {
            "KeyError": "Secret이 등록되지 않았거나 이름 오타",
            "JSONDecodeError": "GOOGLE_CREDENTIALS에 JSON 파일 내용 전체가 안 들어감",
            "MalformedError": "GOOGLE_CREDENTIALS 값이 서비스 계정 키 형식이 아님",
            "SpreadsheetNotFound": "SHEET_URL이 틀렸거나 서비스 계정에 시트가 공유되지 않음",
            "NoValidUrlKeyFound": "SHEET_URL이 구글 시트 주소 형식이 아님",
            "PermissionError": "서비스 계정에 시트가 공유되지 않음",
            "APIError": "구글 API 거부 — 시트 공유 여부와 Sheets API 활성화 확인",
        }
        etype = type(e).__name__
        print(f"[오류] 구글 시트 읽기 실패: {etype} — {hints.get(etype, '상세 내용은 텔레그램 참고')}")
        delivered = notify.send_message(
            f"❌ 구글 시트를 읽지 못했습니다.\n"
            f"<b>{etype}</b>: {e}\n\n"
            f"💡 {hints.get(etype, 'watcher/README.md의 문제 해결 표를 확인해주세요')}")
        print(f"[오류] 텔레그램 통지 {'전송됨' if delivered else '전송 실패'}")
        sys.exit(1)

    print(f"[시작] 감시 대상 {len(targets)}개")
    check_target._dumped = False  # 진단 덤프는 실행당 1회만
    st = state_mod.load()

    if targets:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            for target in targets:
                new_slots = check_target(browser, target, st)
                if new_slots:
                    send_alerts(target, new_slots)
            browser.close()

    maybe_heartbeat(st, targets)
    state_mod.save(st)
    print("[완료]")


if __name__ == "__main__":
    # INTERVAL_SECONDS가 있으면(나스/도커 상주 모드) 그 간격으로 무한 반복하고,
    # 없으면(GitHub Actions 등) 1회만 실행한다.
    interval = os.environ.get("INTERVAL_SECONDS")
    if interval:
        interval = int(interval)
        print(f"[상주 모드] {interval}초 간격으로 반복 실행합니다.")
        while True:
            started = time.time()
            try:
                main()
            except (Exception, SystemExit) as e:
                # 한 회차 실패가 루프를 죽이지 않도록 삼킨다.
                print(f"[루프] 이번 회차 오류: {type(e).__name__}: {e}")
            # 매번 정확히 같은 시각에 두드리지 않도록 0~2분 지터를 준다.
            sleep_for = max(interval - (time.time() - started), 60) + random.uniform(0, 120)
            time.sleep(sleep_for)
    else:
        main()
