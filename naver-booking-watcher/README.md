# 🔔 네이버 예약 빈자리 알림 봇

원하는 가게/날짜/시간대/인원 조건을 등록해두면, 주기적으로 네이버 예약 페이지를 확인해서 **빈자리가 나면 이메일로 알려주는** 도구입니다.

## 이 도구가 하지 않는 것

- **예약을 대신 진행하지 않습니다.** 결제, 인원/시간 최종 확정 등 예약 완료 단계는 항상 사람이 직접 해야 합니다.
- **예약 페이지를 자동으로 열지 않습니다.** 알림(이메일)에 링크만 담아 보내고, 그 링크를 열지 말지/언제 열지는 사용자가 결정합니다.
- 캡차 우회, 로그인 세션 탈취 같은 부정 접근을 하지 않습니다. 사람이 브라우저로 보는 것과 동일한 공개 예약 페이지만 주기적으로 확인합니다.

이렇게 범위를 좁힌 이유는, "빈자리 나는 즉시 자동 결제까지" 하는 봇은 다른 이용자와의 형평성 문제가 있고 대부분의 예약 플랫폼 약관에서도 금지하는 자동화 행위이기 때문입니다. 너무 잦은 확인 주기는 상대 서버에 부담을 줄 수 있으니 아래 `checkIntervalMinutes` 관련 안내를 참고해 적당한 간격(15분 이상 권장)을 유지해주세요.

## 빠른 시작

1. `config.json`을 열어 확인하고 싶은 가게의 예약 URL, 날짜, 선호 시간대, 인원, 알림받을 이메일을 채웁니다.

   ```json
   {
     "targets": [
       {
         "label": "OO식당 저녁 4인",
         "bookingUrl": "https://booking.naver.com/booking/13/bizes/000000/items/0000000",
         "dates": ["2026-08-20", "2026-08-21"],
         "preferredTimes": ["18:00", "18:30", "19:00"],
         "partySize": 4
       }
     ],
     "notify": { "email": "gomjadori@gmail.com" }
   }
   ```

   - `bookingUrl`은 네이버 지도에서 가게 페이지 → "예약" 버튼을 눌러 들어가는 `booking.naver.com/...` 주소입니다.
   - `preferredTimes`를 비워두면([]) 해당 날짜에 열려있는 모든 시간을 알림 대상으로 봅니다.
   - `targets` 배열에 항목을 여러 개 추가하면 여러 가게/조건을 동시에 감시할 수 있습니다.

2. 이메일 발송을 위해 **Gmail 앱 비밀번호**를 발급받습니다 (Google 계정 → 보안 → 2단계 인증 → 앱 비밀번호).

3. GitHub 저장소 **Settings → Secrets and variables → Actions**에서 아래 Secret을 등록합니다.

   | Secret 이름 | 값 |
   |---|---|
   | `NAVER_WATCHER_SMTP_USER` | 발신용 Gmail 주소 |
   | `NAVER_WATCHER_SMTP_PASS` | 위에서 발급한 앱 비밀번호 |
   | `NAVER_WATCHER_NOTIFY_EMAIL` | (선택) 알림받을 이메일. 비워두면 `config.json`의 `notify.email` 사용 |

4. `.github/workflows/naver-booking-watch.yml`이 15분마다 자동 실행되며, 새로운 빈자리를 찾으면 이메일을 보냅니다. GitHub Actions 탭 → `Naver Booking Watcher` → `Run workflow`로 즉시 실행해서 테스트할 수도 있습니다.

## 선택자(selector) 확인/수정하기 — 꼭 읽어주세요

이 도구를 만든 환경에서는 네트워크 정책상 `naver.com` 접속이 막혀 있어서, 실제 예약 페이지의 달력·시간 버튼 HTML 구조를 직접 보고 검증하지 못했습니다. 즉 `selectors.json`에 들어있는 값은 **검증되지 않은 최선의 추정치**입니다. 처음 사용할 때 아래 순서로 꼭 확인해주세요.

1. 로컬 PC에서 실행 (최초 1회):
   ```bash
   cd naver-booking-watcher
   npm install
   npx playwright install chromium
   npm run debug -- "https://booking.naver.com/booking/13/bizes/000000/items/0000000"
   ```
2. `naver-booking-watcher/debug/screenshot.png`와 `page.html`이 생성됩니다. 스크린샷으로 실제 페이지가 잘 로드됐는지 확인하고, `page.html`(또는 실제 예약 페이지를 브라우저로 열고 F12 개발자도구)에서 달력 날짜 칸과 시간 선택 버튼의 class 이름을 확인합니다.
3. `selectors.json`의 `timeSlotButton`, `waitForSelector` 등을 실제 class명에 맞게 수정합니다.
4. `npm run check`로 로컬에서 정상적으로 시간이 파싱되는지 확인한 뒤 커밋/푸시합니다.

`npm run check` 실행 시 `[경고] ... 달력/시간 영역을 찾지 못했습니다` 로그가 보이면 선택자가 실제 페이지와 맞지 않는다는 뜻이니 위 과정을 다시 확인해주세요.

## 동작 방식

1. 각 `target`의 날짜별로 예약 페이지를 열고(`?date=YYYYMMDD` 파라미터로 이동), 열려있는 시간 버튼을 읽어옵니다.
2. `preferredTimes`와 겹치는 시간이 있으면 "새로 발견된 빈자리"로 기록합니다 (이미 알림을 보낸 슬롯은 `state.json`에 저장되어 중복 알림을 보내지 않습니다).
3. 새 빈자리가 있으면 이메일로 가게명/날짜/시간과 예약 링크를 보냅니다. 예약은 사용자가 링크를 눌러 직접 완료합니다.

## 참고

- 네이버 예약 페이지 구조가 바뀌면 `selectors.json`을 다시 확인해야 할 수 있습니다.
- 확인 주기(`cron: '*/15 * * * *'`)는 `.github/workflows/naver-booking-watch.yml`에서 조절할 수 있습니다. 너무 짧게 잡지 마세요.
- 매장이 인원수에 따라 예약 항목(`items/...`) 자체가 다르다면, `bookingUrl`에 인원수에 맞는 항목 URL을 넣어주세요.
