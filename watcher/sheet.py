"""구글 시트에서 감시 목록을 읽어온다.

시트 컬럼: 상태 | 가게명 | URL | 날짜 | 시간 | 필요인원
- 상태가 'O'인 행만 감시 대상
- 날짜: "2026-08-20" / "2026-08-20 ~ 2026-08-25" / 쉼표로 여러 개
- 시간: "18:00" / "18:00 ~ 20:00" / 쉼표로 여러 개, 비우면 전체 시간 허용
"""
import json
import os
from datetime import datetime, timedelta

import gspread
from google.oauth2.service_account import Credentials


def parse_dates(raw: str) -> list[str]:
    dates: set[str] = set()
    for rule in [r.strip() for r in str(raw).split(",") if r.strip()]:
        if "~" in rule:
            start_s, end_s = [s.strip() for s in rule.split("~", 1)]
            start = datetime.strptime(start_s, "%Y-%m-%d")
            end = datetime.strptime(end_s, "%Y-%m-%d")
            while start <= end:
                dates.add(start.strftime("%Y-%m-%d"))
                start += timedelta(days=1)
        else:
            datetime.strptime(rule, "%Y-%m-%d")  # 형식 검증
            dates.add(rule)
    return sorted(dates)


def time_matches(time_str: str, rules: list[str]) -> bool:
    if not rules:
        return True
    try:
        t = datetime.strptime(time_str.strip(), "%H:%M").time()
    except ValueError:
        return False
    for rule in rules:
        if "~" in rule:
            start_s, end_s = [s.strip() for s in rule.split("~", 1)]
            start = datetime.strptime(start_s, "%H:%M").time()
            end = datetime.strptime(end_s, "%H:%M").time()
            if start <= t <= end:
                return True
        elif datetime.strptime(rule.strip(), "%H:%M").time() == t:
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
            continue
        try:
            qty = int(str(row.get("필요인원", "")).strip() or 1)
        except ValueError:
            qty = 1
        targets.append({
            "name": name,
            "url": url,
            "dates": dates,
            "times": [t.strip() for t in str(row.get("시간", "")).split(",") if t.strip()],
            "qty": max(qty, 1),
        })
    return targets


def mask(name: str) -> str:
    """공개 저장소의 Actions 로그에 가게명이 노출되지 않도록 마스킹."""
    return name[0] + "*" * max(len(name) - 1, 2) if name else "?"
