import { readFile, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';

const STATE_PATH = new URL('../state.json', import.meta.url);
const KEEP_DAYS = 14;

export async function loadState() {
  if (!existsSync(STATE_PATH)) return {};
  const raw = await readFile(STATE_PATH, 'utf8');
  try {
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

export async function saveState(state) {
  const cutoff = Date.now() - KEEP_DAYS * 24 * 60 * 60 * 1000;
  const pruned = Object.fromEntries(
    Object.entries(state).filter(([, notifiedAt]) => notifiedAt >= cutoff)
  );
  await writeFile(STATE_PATH, JSON.stringify(pruned, null, 2) + '\n', 'utf8');
}

export function slotKey(target, date, time) {
  return `${target.label}|${date}|${time}`;
}
