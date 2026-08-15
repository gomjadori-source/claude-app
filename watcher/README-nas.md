# 🏠 시놀로지 나스(DS220+)에서 돌리기

GitHub 대신 집에 있는 시놀로지 나스에서 이 봇을 돌리는 방법입니다.
나스는 **집 인터넷 회선(가정용 IP)**으로 접속하기 때문에, GitHub의 데이터센터 IP보다
네이버의 봇 차단에 걸릴 확률이 낮습니다.

> ⚠️ 그래도 네이버가 자동화 브라우저 자체를 감지해 CAPTCHA를 띄울 수는 있습니다.
> 집 IP가 가장 큰 원인 하나를 없애줄 뿐, "무조건 통과"는 아닙니다.

준비물: DS220+ (또는 다른 인텔 "+" 시리즈), DSM 7.x, 인터넷 연결.
소요 시간: 약 15분. SSH는 필요 없습니다.

---

## 1. Container Manager 설치

1. DSM 접속 → **패키지 센터** 열기
2. "Container Manager" 검색 → **설치** (구버전 DSM에서는 "Docker"라는 이름)

## 2. 파일 올리기

1. **File Station**을 열고, `docker` 공유 폴더 안에 `naver-watcher` 폴더를 만듭니다.
   (경로 예: `/docker/naver-watcher`)
2. 이 `watcher` 폴더 안의 파일들을 그 폴더에 업로드합니다. 최소한 아래가 필요합니다:
   - `Dockerfile`
   - `docker-compose.yml`
   - `main.py`, `naver.py`, `notify.py`, `sheet.py`, `state.py`
   - `.env.example`
3. 같은 폴더 안에 **`data`** 라는 하위 폴더를 하나 만듭니다. (상태 파일과 인증키가 여기 저장됩니다)

## 3. 비밀값 3종 넣기

1. `.env.example`을 복사해 같은 폴더에 **`.env`** 라는 이름으로 저장하고, 값을 채웁니다:
   ```
   TELEGRAM_TOKEN=봇토큰
   TELEGRAM_CHAT_ID=7926337905
   SHEET_URL=https://docs.google.com/spreadsheets/d/....
   ```
2. 구글 서비스 계정 JSON 파일을 **`data` 폴더 안에 `service-account.json`** 이라는 이름으로 넣습니다.
   (GitHub 때 쓰던 그 JSON 파일 그대로입니다. 시트에 이 계정 이메일이 뷰어로 공유돼 있어야 합니다.)

폴더 구조가 이렇게 됩니다:
```
/docker/naver-watcher/
├── Dockerfile
├── docker-compose.yml
├── .env
├── main.py  (그 외 .py들)
└── data/
    └── service-account.json
```

## 4. 프로젝트로 실행

1. **Container Manager** 열기 → 왼쪽 **프로젝트** → **생성**
2. 프로젝트 이름: `naver-watcher`
3. 경로: 방금 만든 `/docker/naver-watcher` 선택
4. 소스: **"기존 docker-compose.yml 사용"** 선택 (폴더 안 파일을 자동 인식)
5. **다음 → 완료**. 첫 실행 때 이미지를 빌드하느라 몇 분 걸립니다.

빌드가 끝나면 컨테이너가 상주하면서 **2시간마다** 시트를 읽고 확인합니다.
켜지자마자 1회 즉시 확인하므로, 조건에 맞는 빈자리가 있으면 곧 텔레그램 알림이 옵니다.

## 5. 잘 도는지 확인

- Container Manager → **컨테이너** → `naver-watcher` → **로그** 탭에서
  `[시작] 감시 대상 N개`, `확인 완료` 같은 줄이 보이면 정상입니다.
- 매일 아침 9시경 요약 메시지가 텔레그램으로 옵니다.

---

## 자주 쓰는 조작

| 하고 싶은 것 | 방법 |
|---|---|
| 감시 주기 바꾸기 | `docker-compose.yml`의 `INTERVAL_SECONDS` 숫자 변경 (7200=2시간, 3600=1시간) 후 프로젝트 재빌드 |
| 잠깐 끄기 | Container Manager에서 컨테이너 **중지** |
| 감시 가게 추가/제거 | 구글 시트만 수정 (나스는 건드릴 필요 없음) |
| 코드 업데이트 | 새 `.py` 파일 덮어쓰고 프로젝트 **재빌드** |

## 문제 해결

| 증상 | 조치 |
|---|---|
| 로그에 `구글 시트를 읽지 못했습니다` | `data/service-account.json`이 있는지, 시트에 그 계정이 뷰어로 공유됐는지 확인 |
| 텔레그램 알림이 안 옴 | `.env`의 토큰/챗ID 확인. 봇에게 먼저 아무 메시지나 1회 보냈는지 확인 |
| `자리 정보를 읽지 못하고 있어요` + CAPTCHA 화면 | 네이버가 봇을 감지한 것. 집 IP로도 막히면 이 방식으로는 한계입니다 |
| 컨테이너가 자꾸 재시작 | 로그 확인. RAM 부족이면 감시 대상 수를 줄이거나 나스 RAM 증설 검토 |

## GitHub 버전과의 차이

- 상태(`state.json`)는 저장소가 아니라 나스의 `data/` 폴더에 저장됩니다.
- 비밀값은 GitHub Secrets가 아니라 나스 안의 `.env` / `data/`에만 있습니다.
- 따라서 나스에서 돌릴 거라면 GitHub Actions 워크플로는 꺼두어도 됩니다
  (저장소 Actions 탭 → 워크플로 → Disable).
