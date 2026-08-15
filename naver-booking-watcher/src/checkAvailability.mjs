// 네이버 예약 빈자리 감지 -> 알림 전용 스크립트.
// 이 스크립트는 예약 페이지를 자동으로 열거나, 시간 선택/결제 등 예약 과정을 대신 진행하지 않습니다.
// 조건에 맞는 빈자리를 찾으면 이메일로 "링크"만 보내고, 실제 예약은 사용자가 직접 클릭해서 진행합니다.

import { readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { chromium } from 'playwright';
import { loadState, saveState, slotKey } from './state.mjs';
import { sendAvailabilityEmail } from './notify.mjs';

const CONFIG_PATH = new URL('../config.json', import.meta.url);
const SELECTORS_PATH = new URL('../selectors.json', import.meta.url);

function toDateQuery(dateStr, format) {
  const compact = dateStr.replaceAll('-', '');
  return format === 'YYYYMMDD' ? compact : dateStr;
}

function buildUrl(baseUrl, param, value) {
  const url = new URL(baseUrl);
  url.searchParams.set(param, value);
  return url.toString();
}

async function checkOneDate(page, selectors, target, date) {
  const url = buildUrl(target.bookingUrl, selectors.dateQueryParam, toDateQuery(date, selectors.dateQueryFormat));
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });

  if (selectors.partySizeSelect && target.partySize) {
    const select = page.locator(selectors.partySizeSelect);
    if (await select.count()) {
      await select.selectOption(String(target.partySize)).catch(() => {});
    }
  }

  await page
    .waitForSelector(selectors.waitForSelector, { timeout: 15000 })
    .catch(() => {
      console.warn(`[경고] "${target.label}" (${date}) 페이지에서 달력/시간 영역을 찾지 못했습니다. selectors.json을 확인해주세요.`);
    });
  await page.waitForTimeout(selectors.waitAfterLoadMs ?? 1000);

  const buttons = page.locator(selectors.timeSlotButton);
  const count = await buttons.count();
  const times = [];
  for (let i = 0; i < count; i++) {
    const text = (await buttons.nth(i).innerText().catch(() => '')).trim();
    const match = text.match(/\d{1,2}:\d{2}/);
    if (match) times.push(match[0]);
  }
  return { url, times: [...new Set(times)] };
}

async function main() {
  if (!existsSync(CONFIG_PATH)) {
    console.error('config.json이 없습니다. config.example.json을 복사해서 config.json으로 만들고 내용을 채워주세요.');
    process.exit(1);
  }
  const config = JSON.parse(await readFile(CONFIG_PATH, 'utf8'));
  const selectors = JSON.parse(await readFile(SELECTORS_PATH, 'utf8'));
  const state = await loadState();

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  const matches = [];
  for (const target of config.targets) {
    for (const date of target.dates) {
      console.log(`[확인 중] ${target.label} / ${date}`);
      let result;
      try {
        result = await checkOneDate(page, selectors, target, date);
      } catch (err) {
        console.warn(`[오류] ${target.label} / ${date}: ${err.message}`);
        continue;
      }

      const wanted = target.preferredTimes?.length
        ? result.times.filter((t) => target.preferredTimes.includes(t))
        : result.times;

      for (const time of wanted) {
        const key = slotKey(target, date, time);
        if (state[key]) continue; // 이미 알림 보낸 슬롯
        matches.push({ target: target.label, date, time, url: result.url });
        state[key] = Date.now();
      }
    }
  }

  await browser.close();

  if (matches.length) {
    const to = process.env.NOTIFY_EMAIL || config.notify?.email;
    console.log(`[알림] ${matches.length}건의 새 빈자리를 찾았습니다. 이메일을 전송합니다.`);
    await sendAvailabilityEmail({ to, matches });
  } else {
    console.log('[결과] 새로 발견된 빈자리가 없습니다.');
  }

  await saveState(state);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
