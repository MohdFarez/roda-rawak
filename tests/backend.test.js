// node tests/backend.test.js — tests apps-script/Code.gs with a fake Sheet
const { createBackend } = require('./gas-mock');
const KEYS = ['red', 'pink', 'blue', 'purple', 'green', 'yellow', 'orange', 'white', 'black', 'brown', 'gold'];

let pass = 0, fail = 0;
function check(name, ok, detail) {
  if (ok) { pass++; console.log('PASS ' + name); }
  else { fail++; console.log('FAIL ' + name + (detail !== undefined ? ' — ' + JSON.stringify(detail) : '')); }
}

let b;
// spreadsheet created with only a header row in its first tab (how the Drive file is made)
b = createBackend(); b.addSheet('Sheet1', [['Masa', 'Nama', 'Warna', 'Kod']]);
b.get();
check('first tab reused + renamed "Keputusan" (no extra empty tab)', JSON.stringify(b.sheetNames()) === '["Keputusan"]' && b.sheet().rows.length === 1, b.sheetNames());
b = createBackend(); b.addSheet('Data lain', [['x'], ['y'], ['z']]);
b.get();
check('first tab already has other data → new "Keputusan" tab instead', JSON.stringify(b.sheetNames()) === '["Data lain","Keputusan"]');

b = createBackend();
let r = b.get();
check('empty sheet: list ok, no picks, max 11', r.ok && r.picks.length === 0 && r.max === 11, r);
check('sheet created with header row', JSON.stringify(b.sheet().rows[0]) === JSON.stringify(['Masa', 'Nama', 'Warna', 'Kod']));

check('bad JSON body rejected', b.post('{oops').error === 'bad_action');
check('unknown action rejected', b.post({ action: 'hack' }).error === 'bad_action');
check('blank name rejected', b.post({ action: 'spin', name: '   ' }).error === 'no_name');
check('missing name rejected', b.post({ action: 'spin' }).error === 'no_name');

r = b.post({ action: 'spin', name: '  Farez   Che  Musa ' });
check('spin ok, spaces tidied', r.ok && r.pick.name === 'Farez Che Musa' && KEYS.includes(r.pick.color), r);
const row = b.sheet().rows[1];
check('row written: name, "Warna emoji", key', row[1] === 'Farez Che Musa' && row[3] === r.pick.color && /^\S+ \S+$/.test(row[2]), row);

r = b.post({ action: 'spin', name: 'farez che musa' });
check('same name (any case) cannot spin twice → returns their colour', !r.ok && r.error === 'exists' && r.pick.name === 'Farez Che Musa', r);

r = b.post({ action: 'spin', name: 'x'.repeat(80) });
check('long name cut to 40', r.ok && r.pick.name.length === 40);

r = b.post({ action: 'spin', name: '=HYPERLINK("http://evil","klik")' });
const injRow = b.sheet().rows[b.sheet().rows.length - 1];
check('formula-looking name stored as plain text (no Sheet formula)', r.ok && typeof injRow[1] === 'string' && injRow[1] === '=HYPERLINK("http://evil","klik")', injRow);
check('formula-looking name read back unchanged', b.get().picks.some(p => p.name === '=HYPERLINK("http://evil","klik")'));

// fill to 11
for (let i = 0; b.get().picks.length < 11; i++) {
  const x = b.post({ action: 'spin', name: 'Org' + i });
  if (!x.ok) { check('filling to 11 works', false, x); break; }
}
r = b.get();
const cols = r.picks.map(p => p.color);
check('11 people → 11 different colours, all colours used', new Set(cols).size === 11 && KEYS.every(k => cols.includes(k)), cols);
r = b.post({ action: 'spin', name: 'Orang ke-12' });
check('12th person refused: full', !r.ok && r.error === 'full', r);
check('nothing written for refused spin', b.sheet().rows.length === 12);

// manual Sheet edits by the organiser
const sh = b.sheet();
const freed = sh.rows[3][3];
sh.rows.splice(3, 1);                         // delete one person
r = b.post({ action: 'spin', name: 'Ganti' });
check('deleting a row in the Sheet frees that colour for the next spin', r.ok && r.pick.color === freed, { got: r.pick && r.pick.color, freed });

b = createBackend(); b.get();
const s2 = b.sheet();
s2.rows.push([new Date(), 'A', 'Merah ❤️', 'red']);
s2.rows.push([new Date(), 'B', 'Merah ❤️', 'red']);        // duplicate colour typed by hand
s2.rows.push([new Date(), 'C', 'Hijau 💚', '']);            // Kod wiped, Warna still there
s2.rows.push([new Date(), '', '', '']);                    // blank row
s2.rows.push([new Date(), 'a', 'Blue 💙', 'blue']);         // duplicate name (case)
s2.rows.push(['', 'D', 'whatever', 'zzz']);                // junk colour
r = b.get();
check('hand edits: blank + duplicate-name rows ignored', r.picks.map(p => p.name).join(',') === 'A,B,C,D', r.picks);
check('hand edits: repeated colour counts once', r.picks[0].color === 'red' && r.picks[1].color === null);
check('hand edits: colour recovered from Warna when Kod wiped', r.picks[2].color === 'green');
check('hand edits: junk colour → none', r.picks[3].color === null);
const r2 = b.post({ action: 'spin', name: 'E' });
check('after hand edits, new spin never gives a taken colour', r2.ok && !['red', 'green'].includes(r2.pick.color), r2);

b = createBackend(); b.get();
for (let i = 0; i < 15; i++) b.sheet().rows.push([new Date(), 'P' + i, '', '']);
check('more than 11 rows typed in → only first 11 count', b.get().picks.length === 11);

b = createBackend(); b.get();
b.lockState.busy = true;
check('lock busy → polite "busy" error, nothing written', b.post({ action: 'spin', name: 'Z' }).error === 'busy' && b.sheet().rows.length === 1);

// fairness: first spin on an empty sheet, many times
b = createBackend(); b.get();
const counts = Object.fromEntries(KEYS.map(k => [k, 0]));
const N = 5500;
for (let i = 0; i < N; i++) { b.reset(); counts[b.post({ action: 'spin', name: 'T' }).pick.color]++; }
const exp = N / 11, chi = KEYS.reduce((s, k) => s + (counts[k] - exp) ** 2 / exp, 0);
check(`fair random: ${N} spins spread evenly over 11 colours (chi²=${chi.toFixed(1)} < 29.6)`, chi < 29.6, counts);

// fairness with some colours taken
b = createBackend(); b.get();
const c2 = {};
for (let i = 0; i < 3000; i++) {
  b.reset();
  b.sheet().rows.push([new Date(), 'X', '', 'red'], [new Date(), 'Y', '', 'gold']);
  const k = b.post({ action: 'spin', name: 'T' }).pick.color;
  c2[k] = (c2[k] || 0) + 1;
}
check('taken colours (red, gold) never come out again', !c2.red && !c2.gold && Object.keys(c2).length === 9, c2);

console.log(`\n==== backend: ${pass}/${pass + fail} checks passed ====`);
process.exit(fail ? 1 : 0);
