"""구글 시트에서 감시 목록을 읽어온다.

시트 컬럼: 상태 | 가게명 | URL | 날짜 | 시간 | 필요인원
- 상태가 'O'인 행만 감시 대상
- 날짜: "2026-08-20" / "2026-08-20 ~ 2026-08-25" / 쉼표로 여러 개
- 시간: "18:00" / "18:00 ~ 20:00" / 쉼표로 여러 개, 비우면 전체 시간 허용
"""
import json
import os
import re
from datetime import date, datetime, timedelta, timezone

import gspread
from google.oauth2.service_account import Credentials

KST = timezone(timedelta(hours=9))


def _today() -> date:
    return datetime.now(KST).date()


def parse_one_date(raw: str) -> date:
    """사람이 적을 법한 날짜 표기를 관대하게 해석한다.

    허용 예: 2026-08-20 / 2026.8.20 / 2026. 8. 20. / 2026/08/20 /
             8-20 / 8/20 / 8.20 / 8월 20일 / 2026년 8월 20일
    연도가 없으면 오늘(KST) 기준으로 아직 지나지 않은 가장 가까운 해로 본다.
    """
    s = re.sub(r"[년월]", "-", str(raw))
    s = s.replace("일", "")
    s = re.sub(r"[./]", "-", s)
    s = re.sub(r"\s+", "", s).strip("-")
    parts = [p for p in s.split("-") if p]
    if len(parts) == 3:
        y, m, d = (int(p) for p in parts)
    elif len(parts) == 2:
        m, d = (int(p) for p in parts)
        y = _today().year
        if date(y, m, d) < _today():
            y += 1
    else:
        raise ValueError(raw)
    if y < 100:
        y += 2000
    return date(y, m, d)


def parse_dates(raw: str) -> list[str]:
    """쉼표 구분 + '~' 범위 조합을 날짜 목록으로. 이미 지난 날짜는 뺀다."""
    dates: set[date] = set()
    for rule in [r.strip() for r in str(raw).split(",") if r.strip()]:
        if "~" in rule:
            start_s, end_s = rule.split("~", 1)
            start, end = parse_one_date(start_s), parse_one_date(end_s)
            while start <= end:
                dates.add(start)
                start += timedelta(days=1)
        else:
            dates.add(parse_one_date(rule))
    return sorted(d.strftime("%Y-%m-%d") for d in dates if d >= _today())


def parse_one_time(raw: str):
    """'18:00' / '18시' / '18시 30분' / '오후 6시' / '18' 을 time으로 해석."""
    s = re.sub(r"\s+", "", str(raw))
    pm = s.startswith("오후")
    s = s.removeprefix("오전").removeprefix("오후")
    s = s.replace("시", ":").replace("분", "")
    s = s.rstrip(":")
    if ":" in s:
        h, m = s.split(":", 1)
    else:
        h, m = s, "0"
    h = int(h)
    if pm and h < 12:
        h += 12
    return datetime.strptime(f"{h:02d}:{int(m):02d}", "%H:%M").time()


def time_matches(time_str: str, rules: list[str]) -> bool:
    if not rules:
        return True
    try:
        t = datetime.strptime(time_str.strip(), "%H:%M").time()
    except ValueError:
        return False
    for rule in rules:
        if "~" in rule:
            start_s, end_s = rule.split("~", 1)
            if parse_one_time(start_s) <= t <= parse_one_time(end_s):
                return True
        elif parse_one_time(rule) == t:
            return True
    return False


def load_targets() -> list[dict]:
    creds_info = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    creds = Credentials.from_service_account_info(
        creds_info, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    sheet = gspread.authorize(creds).open_by_url(os.environ["SHEET_URL"]).sheet1

    targets = []
    for i, row in enumerate(sheet.get_all_records()):
        if str(row.get("상태", "")).strip().upper() != "O":
            continue
        name = str(row.get("가게명", "")).strip() or f"이름없는 타겟(행 {i + 2})"
        url = str(row.get("URL", "")).strip()
        if not url:
            continue
        try:
            dates = parse_dates(row.get("날짜", ""))
        except ValueError:
            print(f"[시트] {mask(name)}: 날짜 형식 오류 → 이 행은 건너뜀 (예: 2026-08-20)")
            continue
        if not dates:
            print(f"[시트] {mask(name)}: 유효한 날짜 없음(모두 지난 날짜?) → 이 행은 건너뜀")
            continue

        times = []
        for t in str(row.get("시간", "")).split(","):
            if not t.strip():
                continue
            try:
                for part in t.split("~"):
                    parse_one_time(part)
                times.append(t.strip())
            except ValueError:
                print(f"[시트] {mask(name)}: 시간 형식 오류('{'*' * len(t.strip())}') → 이 규칙만 무시")

        try:
            qty = int(str(row.get("필요인원", "")).strip() or 1)
        except ValueError:
            qty = 1
        targets.append({
            "name": name,
            "url": url,
            "dates": dates,
            "times": times,
            "qty": max(qty, 1),
        })
    return targets


def mask(name: str) -> str:
    """공개 저장소의 Actions 로그에 가게명이 노출되지 않도록 마스킹."""
    return name[0] + "*" * max(len(name) - 1, 2) if name else "?"
