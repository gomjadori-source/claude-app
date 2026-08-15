> 📌 이 저장소에는 [네이버 예약 빈자리 알림 봇](watcher/README.md)도 있습니다. 설정 방법은 `watcher/README.md` 참고.

# 🔨 두더지 잡기 (미니 웹게임)

심심할 때 한 판씩 하는 클릭형 미니게임입니다. `mole-game.html` 파일 하나로 완성되어 있어 다운로드 없이 바로 브라우저에서 실행됩니다.

## 조건 반영

1. **파일 하나로 실행** — HTML/CSS/JS가 `mole-game.html` 한 파일에 모두 들어있어 더블클릭 또는 서버 업로드만으로 바로 플레이됩니다.
2. **모바일 대응** — `touchstart` 이벤트, 반응형 레이아웃(`max-width`, `aspect-ratio`), 확대/스크롤 방지(`viewport`, `touch-action`) 적용.
3. **1~3분 플레이** — 한 판 45초. 시간이 지날수록 두더지가 더 빨리, 더 짧게 나와 난이도가 올라갑니다. 콤보(연속 성공)로 점수 배율이 붙어 다시 도전하고 싶게 설계했습니다.
4. **"다시 하기" 유지** — 게임 종료 시 점수/최고 점수(로컬 저장) 표시 후 바로 재시작할 수 있는 버튼 제공.
5. **광고 자리** — 상단(`#ad-top`)·하단(`#ad-bottom`) `.ad-slot` div가 미리 배치되어 있어 광고 코드만 넣으면 됩니다.

## 광고(예: 구글 애드센스) 넣는 법

1. 애드센스 승인을 받으면 발급되는 스크립트를 `<head>` 안에 붙여넣습니다.
   ```html
   <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-XXXXXXXXXXXXXXXX" crossorigin="anonymous"></script>
   ```
2. `mole-game.html`의 `<div class="ad-slot" id="ad-top">광고 영역 (상단)</div>` 부분을 실제 광고 단위 코드로 교체합니다. 예:
   ```html
   <div class="ad-slot" id="ad-top">
     <ins class="adsbygoogle"
          style="display:block; width:100%;"
          data-ad-client="ca-pub-XXXXXXXXXXXXXXXX"
          data-ad-slot="1234567890"
          data-ad-format="auto"></ins>
     <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
   </div>
   ```
3. `#ad-bottom`도 동일하게 다른 광고 슬롯 코드로 교체하면 됩니다.

## 내 사이트에 올리는 법 (무료 방법 3가지)

어떤 방법을 원하시는지(깃허브 페이지 / 넷리파이 / 버셀 등) 정해주시면 그에 맞춰 더 자세히 도와드릴게요. 우선 가장 쉬운 방법부터 안내합니다.

### 방법 A. GitHub Pages (무료, 도메인 연결 가능)
1. GitHub에서 새 저장소(Repository)를 만듭니다.
2. `mole-game.html`을 `index.html`로 이름을 바꿔서 저장소에 업로드합니다.
3. 저장소 **Settings → Pages**에서 Source를 `main` 브랜치 `/ (root)`로 설정 후 저장합니다.
4. 몇 분 뒤 `https://아이디.github.io/저장소이름/` 주소로 접속하면 게임이 바로 열립니다.

### 방법 B. Netlify Drop (가장 간단, 가입만 하면 끝)
1. https://app.netlify.com/drop 접속
2. `mole-game.html` 파일(또는 이 파일이 든 폴더)을 화면에 그대로 드래그 앤 드롭
3. 몇 초 안에 `https://랜덤이름.netlify.app` 주소가 생성되어 바로 배포 완료

### 방법 C. Vercel
1. https://vercel.com 가입 후 새 프로젝트 생성
2. GitHub 저장소를 연결하거나 파일을 직접 업로드
3. 자동 배포되어 `https://프로젝트명.vercel.app` 주소로 접속 가능

세 방법 모두 무료이며, 이후 원하는 도메인(예: 가비아, 후이즈 등에서 구매)을 연결할 수 있습니다.

## 로컬에서 바로 확인하기

파일을 다운로드해 더블클릭하면 브라우저에서 바로 실행됩니다. 별도 서버나 설치가 필요 없습니다.
