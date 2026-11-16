// Runs apps-script/Code.gs inside Node with a fake Google Sheet, so the real backend code can be tested locally.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

function createBackend() {
  const sheets = {};
  const lockState = { busy: false };

  function makeSheet() {
    const sh = {
      rows: [],
      getLastRow() { return this.rows.length; },
      getRange(r, c, nr = 1, nc = 1) {
        const self = this;
        return {
          getValues() {
            return self.rows.slice(r - 1, r - 1 + nr).map(row => {
              const out = [];
              for (let i = 0; i < nc; i++) out.push(row[c - 1 + i] === undefined ? '' : row[c - 1 + i]);
              return out;
            });
          },
          setFontWeight() { return this; }
        };
      },
      appendRow(arr) {
        // behave like Sheets: a leading ' marks plain text and is not stored; a leading = becomes a formula
        this.rows.push(arr.map(v => {
          if (typeof v !== 'string') return v;
          if (v.startsWith("'")) return v.slice(1);
          if (/^[=+\-@]/.test(v)) return { FORMULA: v };
          return v;
        }));
      },
      setFrozenRows() {}
    };
    return sh;
  }

  const order = [];
  const ss = {
    getSheetByName(n) { return sheets[n] || null; },
    getSheets() { return order.map(n => sheets[n]); },
    insertSheet(n) { sheets[n] = makeSheet(); sheets[n].name = n; order.push(n); return sheets[n]; }
  };
  function addSheet(n, rows) {                       // a spreadsheet that already has a tab (e.g. "Sheet1")
    const sh = ss.insertSheet(n); sh.rows = rows || [];
    sh.setName = function (newName) { delete sheets[this.name]; order[order.indexOf(this.name)] = newName; this.name = newName; sheets[newName] = this; };
    return sh;
  }

  const context = {
    SpreadsheetApp: { getActiveSpreadsheet: () => ss, flush() {} },
    LockService: {
      getScriptLock: () => ({
        waitLock() { if (lockState.busy) throw new Error('Lock timeout'); },
        releaseLock() {}
      })
    },
    ContentService: {
      createTextOutput: s => ({ body: s, setMimeType() { return this; } }),
      MimeType: { JSON: 'application/json' }
    },
    Math, Date, JSON, String, Object, Array, Error
  };
  vm.createContext(context);
  const code = fs.readFileSync(path.join(__dirname, '..', 'apps-script', 'Code.gs'), 'utf8');
  vm.runInContext(code, context, { filename: 'Code.gs' });

  const parse = out => JSON.parse(out.body);
  return {
    get: () => parse(context.doGet({})),
    post: body => parse(context.doPost({ postData: { contents: typeof body === 'string' ? body : JSON.stringify(body) } })),
    sheet: () => sheets['Keputusan'],
    reset() { if (sheets['Keputusan']) sheets['Keputusan'].rows = sheets['Keputusan'].rows.slice(0, 1); },
    addSheet, sheetNames: () => order.slice(),
    lockState
  };
}

module.exports = { createBackend };
