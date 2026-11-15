/**
 * Rode Warne Tuka Hadioh — backend (Google Apps Script)
 * -----------------------------------------------------
 * Google Sheet ni jadi database. Setiap baris = sorang + warne die.
 *
 *   Masa | Nama | Warna | Kod
 *
 * Nok buang sorang (warne die balik kak rode)  → padam baris die.
 * Nok maing semule                              → padam semue baris kecuali tajuk.
 * Jangan ubah lajur "Kod" — page guna lajur tu.
 *
 * Deploy: Deploy → New deployment → Web app
 *         Execute as: Me   |   Who has access: Anyone
 */

const SHEET_NAME = 'Keputusan';
const MAX_NAMES = 11;
const HEADER = ['Masa', 'Nama', 'Warna', 'Kod'];
const COLORS = [
  ['red', 'Merah', '❤️'], ['pink', 'Pink', '💗'], ['blue', 'Blue', '💙'], ['purple', 'Ungu', '💜'],
  ['green', 'Hijau', '💚'], ['yellow', 'Kuning', '💛'], ['orange', 'Oren', '🧡'], ['white', 'Putih', '🤍'],
  ['black', 'Hitam', '🖤'], ['brown', 'Coklat', '🤎'], ['gold', 'Gold', '✨']
];

/* ---------- GET: senarai semue ---------- */
function doGet(e) {
  try {
    return json_({ ok: true, picks: readPicks_(sheet_()), max: MAX_NAMES });
  } catch (err) {
    return json_({ ok: false, error: 'server', message: String(err) });
  }
}

/* ---------- POST: pusing ---------- */
function doPost(e) {
  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(20000);                       // sorang-sorang — dua orang serentak dok dapak warne same
  } catch (err) {
    return json_({ ok: false, error: 'busy' });
  }
  try {
    let body = {};
    try { body = JSON.parse((e && e.postData && e.postData.contents) || '{}'); } catch (x) { body = {}; }
    if (body.action !== 'spin') return json_({ ok: false, error: 'bad_action' });

    const name = cleanName_(body.name);
    if (!name) return json_({ ok: false, error: 'no_name' });

    const sh = sheet_();
    const picks = readPicks_(sh);
    const mine = picks.find(p => sameName_(p.name, name));
    if (mine) return json_({ ok: false, error: 'exists', pick: mine, picks: picks, max: MAX_NAMES });
    if (picks.length >= MAX_NAMES) return json_({ ok: false, error: 'full', picks: picks, max: MAX_NAMES });

    const taken = {};
    picks.forEach(p => { if (p.color) taken[p.color] = true; });
    const free = COLORS.filter(c => !taken[c[0]]);
    if (!free.length) return json_({ ok: false, error: 'no_colors', picks: picks, max: MAX_NAMES });

    const c = free[Math.floor(Math.random() * free.length)];   // server pilih — adil, dok buleh tipu
    const now = new Date();
    sh.appendRow([now, sheetSafe_(name), c[1] + ' ' + c[2], c[0]]);
    SpreadsheetApp.flush();

    const pick = { name: name, color: c[0], time: now.toISOString() };
    picks.push(pick);
    return json_({ ok: true, pick: pick, picks: picks, max: MAX_NAMES });
  } catch (err) {
    return json_({ ok: false, error: 'server', message: String(err) });
  } finally {
    lock.releaseLock();
  }
}

/* ---------- helpers ---------- */
function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) {
    const first = ss.getSheets()[0];
    if (first && first.getLastRow() <= 1) { first.setName(SHEET_NAME); sh = first; }   // guna tab pertame kalau masih kosong
    else sh = ss.insertSheet(SHEET_NAME);
  }
  if (sh.getLastRow() === 0) {
    sh.appendRow(HEADER);
    sh.setFrozenRows(1);
    sh.getRange(1, 1, 1, HEADER.length).setFontWeight('bold');
  }
  return sh;
}

function readPicks_(sh) {
  const last = sh.getLastRow();
  if (last < 2) return [];
  const rows = sh.getRange(2, 1, last - 1, HEADER.length).getValues();
  const seen = {};
  const out = [];
  rows.forEach(r => {
    const name = cleanName_(r[1]);
    if (!name) return;                                       // baris kosong — abaikan
    if (out.some(p => sameName_(p.name, name))) return;      // name berulang (edit tangan) — ambik yang pertame
    let key = keyOf_(r[3], r[2]);
    if (key && seen[key]) key = null;                        // warne berulang (edit tangan) — yang pertame je kire
    if (key) seen[key] = true;
    out.push({ name: name, color: key, time: r[0] instanceof Date ? r[0].toISOString() : String(r[0] || '') });
  });
  return out.slice(0, MAX_NAMES);
}

function keyOf_(code, warna) {
  const k = String(code || '').trim().toLowerCase();
  if (COLORS.some(c => c[0] === k)) return k;
  const w = String(warna || '').trim().toLowerCase();
  const hit = COLORS.find(c => w === c[1].toLowerCase() || w.indexOf(c[1].toLowerCase() + ' ') === 0);
  return hit ? hit[0] : null;
}

function cleanName_(s) { return String(s == null ? '' : s).replace(/\s+/g, ' ').trim().slice(0, 40); }
function sameName_(a, b) { return cleanName_(a).toLowerCase() === cleanName_(b).toLowerCase(); }
function sheetSafe_(s) { return /^[=+\-@]/.test(s) ? "'" + s : s; }   // elak name jadi formula Sheet

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
