// 실제 예약 페이지를 렌더링해서 screenshot.png / page.html로 저장합니다.
// 이 파일들을 열어보면서 selectors.json의 값을 실제 페이지 구조에 맞게 고칠 수 있습니다.
//
// 사용법: npm run debug -- "https://booking.naver.com/booking/13/bizes/000000/items/0000000"

import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';

const url = process.argv[2];
if (!url) {
  console.error('사용법: npm run debug -- "<네이버 예약 URL>"');
  process.exit(1);
}

const outDir = new URL('../debug/', import.meta.url);
await mkdir(outDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

console.log(`[debug] 접속 중: ${url}`);
await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
await page.waitForTimeout(2000);

const html = await page.content();
await writeFile(new URL('page.html', outDir), html, 'utf8');
await page.screenshot({ path: new URL('screenshot.png', outDir).pathname, fullPage: true });

console.log('[debug] 저장 완료: naver-booking-watcher/debug/page.html, screenshot.png');
console.log('[debug] 브라우저 개발자도구(F12)로 실제 예약 페이지를 열어 달력/시간 버튼의 class명을 확인한 뒤 selectors.json을 수정하세요.');

await browser.close();
