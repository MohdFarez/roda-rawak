import asyncio, json, subprocess, time, sys, os
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = 'http://127.0.0.1:8765/index.html'
HEX = {'Merah':'#FF4245','Pink':'#FF6FB5','Blue':'#0091FF','Ungu':'#AF52DE','Hijau':'#30D158','Kuning':'#FFD600',
       'Oren':'#FF9230','Putih':'#F5F5F7','Hitam':'#1C1C1E','Coklat':'#8B5E3C','Gold':None}
KEY = {'Merah':'red','Pink':'pink','Blue':'blue','Ungu':'purple','Hijau':'green','Kuning':'yellow','Oren':'orange',
       'Putih':'white','Hitam':'black','Coklat':'brown','Gold':'gold'}
SIMILAR = {frozenset(p.split('|')) for p in ['red|pink','red|orange','orange|yellow','yellow|gold','orange|gold','brown|gold','brown|orange','pink|purple','black|brown']}

results = []
def check(name, ok, detail=''):
    results.append((name, bool(ok), detail))
    print(('PASS ' if ok else 'FAIL ') + name + ((' — ' + str(detail)) if detail and not ok else ''))

def colour_of(title):            # "Pink 💗" -> "Pink"
    return title.split(' ')[0]

async def pointer_rgb(pg):
    return await pg.evaluate("""() => {
      const c = document.querySelector('#wheelWrap canvas'), ctx = c.getContext('2d');
      const x = Math.round(c.width / 2), y = Math.round(c.height / 2 - (c.width / 2) * 0.6);
      const d = ctx.getImageData(x, y, 1, 1).data; return [d[0], d[1], d[2]];
    }""")

def rgb_matches(name, rgb):
    if name == 'Gold':
        r, g, b = rgb
        return r >= 150 and g >= 100 and b <= 150 and r > g > b
    h = HEX[name]; exp = [int(h[i:i+2], 16) for i in (1, 3, 5)]
    return all(abs(a - e) <= 4 for a, e in zip(rgb, exp))

async def modal_open(pg):
    return await pg.evaluate("!document.getElementById('modal').classList.contains('hidden')")

async def close_modal(pg, how='btn'):
    if how == 'btn': await pg.click('#closeBtn')
    elif how == 'esc': await pg.keyboard.press('Escape')
    elif how == 'backdrop': await pg.mouse.click(8, 8)
    await pg.wait_for_timeout(150)

async def do_spin(pg, how='btn', label=''):
    if how == 'btn': await pg.click('#spinBtn')
    elif how == 'hub': await pg.click('#hub')
    elif how == 'canvas': await pg.click('#wheelWrap canvas', position={'x': 60, 'y': 200})
    elif how == 'ctrl': await pg.evaluate("document.activeElement && document.activeElement.blur()"); await pg.keyboard.press('Control+Enter')
    elif how == 'space': await pg.evaluate("document.activeElement && document.activeElement.blur()"); await pg.keyboard.press('Space')
    await pg.wait_for_selector('#modal:not(.hidden)', timeout=9000)
    title = await pg.text_content('#winTitle')
    rgb = await pointer_rgb(pg)
    check(f'{label} pointer colour = announced colour ({title.strip()})', rgb_matches(colour_of(title), rgb), f'{title} rgb={rgb}')
    return colour_of(title)

async def assigned(pg):
    return await pg.evaluate("""() => [...document.querySelectorAll('.nrow')].map(r => ({
        name: r.querySelector('.nm').textContent, res: r.querySelector('.res').textContent.trim(),
        turn: r.classList.contains('is-turn') }))""")

async def chip_state(pg):
    return await pg.evaluate("""() => [...document.querySelectorAll('.cchip')].map(b => ({
        t: b.textContent.trim().split(' ')[0], used: b.classList.contains('used'), off: b.classList.contains('off') }))""")

async def toast_text(pg):
    return await pg.text_content('#toast')

async def add(pg, name):
    await pg.fill('#nameInput', name); await pg.press('#nameInput', 'Enter')

async def paste(pg, text):
    await pg.evaluate("""(t) => { const i = document.getElementById('nameInput'); i.focus();
      const dt = new DataTransfer(); dt.setData('text/plain', t);
      i.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true })); }""", text)

async def count(pg):
    return int((await pg.text_content('#nameCount')).split('/')[0])

async def main():
    srv = subprocess.Popen([sys.executable, '-m', 'http.server', '8765', '--bind', '127.0.0.1'], cwd=ROOT,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    errors = []
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch()
            ctx = await b.new_context(viewport={'width': 1280, 'height': 820}, permissions=['clipboard-read', 'clipboard-write'])
            pg = await ctx.new_page()
            pg.on('pageerror', lambda e: errors.append('pageerror: ' + str(e)))
            pg.on('console', lambda m: errors.append('console: ' + m.text) if m.type == 'error' else None)
            await pg.goto(URL); await pg.wait_for_timeout(400)

            # ---------- 1. empty state ----------
            check('empty: wheel locked with "Bubuh name"', 'Bubuh name' in (await pg.text_content('#lock')) and not await pg.evaluate("document.getElementById('lock').classList.contains('hidden')"))
            check('empty: spin button disabled', await pg.is_disabled('#spinBtn'))
            check('empty: centre button hidden', await pg.evaluate("getComputedStyle(document.getElementById('hub')).visibility === 'hidden'"))
            check('empty: name list shows empty message', 'Dok ade name' in await pg.text_content('#names'))
            check('empty: result buttons hidden', await pg.evaluate("document.getElementById('namesActions').classList.contains('hidden')"))
            await pg.click('#wheelWrap canvas', position={'x': 60, 'y': 200}, force=True)
            await pg.evaluate("document.activeElement.blur()"); await pg.keyboard.press('Space'); await pg.keyboard.press('Control+Enter')
            await pg.wait_for_timeout(500)
            check('empty: clicking/keys cannot spin', not await modal_open(pg))

            # ---------- 2. adding names ----------
            await add(pg, '    ')
            check('blank name rejected', await count(pg) == 0 and 'Taip name' in await toast_text(pg))
            await add(pg, 'Farez')
            check('Enter adds name', await count(pg) == 1 and await pg.input_value('#nameInput') == '')
            check('wheel unlocks after first name', await pg.evaluate("document.getElementById('lock').classList.contains('hidden')") and not await pg.is_disabled('#spinBtn'))
            check('turn label + button name the first person', 'Farez' in await pg.text_content('#turnLabel') and 'Farez' in await pg.text_content('#spinBtn'))
            await add(pg, '  fArEz  ')
            check('duplicate (any case / spaces) rejected', await count(pg) == 1 and 'doh ade' in await toast_text(pg))
            await pg.fill('#nameInput', 'Aini'); await pg.click('#addBtn')
            check('Tamboh button adds name', await count(pg) == 2)
            await add(pg, '<b>Bold</b><img src=x onerror=alert(1)>')
            rows = await assigned(pg)
            check('HTML in a name shows as plain text (no injection)', rows[-1]['name'].startswith('<b>Bold</b>') and await pg.evaluate("!document.querySelector('.nm b') && !document.querySelector('.nm img')"))
            await add(pg, 'X' * 60)
            rows = await assigned(pg)
            check('very long name trimmed to 40 chars', len(rows[-1]['name']) == 40)
            before = await count(pg)
            await paste(pg, 'Ali\nSiti\nfarez\n\n  Ravi  \r\n')
            check('pasting a list adds each new line, skips duplicates/blanks', await count(pg) == before + 3)
            # delete the two odd names
            await pg.click('.nrow:nth-child(3) .mini')      # <b>Bold…
            await pg.click('.nrow:nth-child(3) .mini')      # XXXX…
            rows = await assigned(pg)
            check('× removes names and list renumbers', [r['name'] for r in rows] == ['Farez', 'Aini', 'Ali', 'Siti', 'Ravi']
                  and await pg.evaluate("[...document.querySelectorAll('.nrow .no')].map(n=>n.textContent).join('')") == '1.2.3.4.5.')

            # ---------- 3. spinning ----------
            await pg.evaluate("const d=document.getElementById('duration'); d.value=2; d.dispatchEvent(new Event('input'))")
            await pg.click('#spinBtn')
            await pg.wait_for_timeout(300)
            locked = await pg.evaluate("""() => ['spinBtn','nameInput','addBtn','resetBtn','clearBtn','regenBtn'].filter(id => document.getElementById(id))
                        .every(id => document.getElementById(id).disabled) && [...document.querySelectorAll('.cchip,.nrow .mini')].every(b => b.disabled)""")
            check('while spinning: buttons, chips, name box all locked', locked)
            await pg.click('#wheelWrap canvas', position={'x': 60, 'y': 200}, force=True)
            await pg.wait_for_selector('#modal:not(.hidden)', timeout=9000)
            t1 = await pg.text_content('#winTitle')
            check('spin 1: pointer colour = announced colour', rgb_matches(colour_of(t1), await pointer_rgb(pg)), t1)
            check('popup names the right person', 'Farez dapak warne' in await pg.text_content('#winKicker'))
            check('popup has no hex colour code', '#' not in await pg.text_content('#modalTop'))
            check('popup button points to next person', 'Lepah ning: Aini' in await pg.text_content('#closeBtn'))
            await pg.wait_for_timeout(2500)
            check('double click during spin did not start a 2nd spin', (await assigned(pg))[1]['res'] == '👀 gilirang')
            got = [colour_of(t1)]
            await close_modal(pg, 'btn')
            chips = await chip_state(pg)
            check('picked colour struck out in colour chips', any(c['t'] == got[0] and c['used'] for c in chips))

            for how, close in [('hub', 'esc'), ('ctrl', 'backdrop'), ('space', 'btn'), ('canvas', 'btn')]:
                got.append(await do_spin(pg, how, f'spin via {how}:'))
                last = how == 'canvas'
                if last: check('last popup says "Siap! Slay"', 'Siap' in await pg.text_content('#closeBtn'))
                await close_modal(pg, close)
                check(f'popup closes via {close}', not await modal_open(pg))
            check('5 spins → 5 different colours (no repeat)', len(set(got)) == 5, got)
            rows = await assigned(pg)
            check('every name shows its colour in the list', all(r['res'].split(' ')[0] in HEX for r in rows))
            check('all done → wheel locked "Semue doh dapak warne"', 'Semue doh dapak warne' in await pg.text_content('#lock') and await pg.is_disabled('#spinBtn'))

            # ---------- 4. copy ----------
            await pg.click('#copyBtn'); await pg.wait_for_timeout(200)
            clip = await pg.evaluate('navigator.clipboard.readText()')
            exp_lines = [f"{i+1}. {r['name']} — {r['res']}" for i, r in enumerate(rows)]
            check('Saling keputusang copies header + every line', clip.split('\n')[0].startswith('🎁 Tuka Hadioh') and clip.split('\n')[2:] == exp_lines, clip)

            # ---------- 5. redo + delete free a colour ----------
            aini_col = rows[1]['res'].split(' ')[0]
            await pg.click('.nrow:nth-child(2) .mini')     # ↺ on Aini
            rows = await assigned(pg)
            chips = await chip_state(pg)
            check('↺ frees the colour back to the wheel', not any(c['t'] == aini_col and c['used'] for c in chips) and rows[1]['turn'])
            c = await do_spin(pg, 'btn', 'respin Aini:')
            await close_modal(pg)
            others = [r['res'].split(' ')[0] for i, r in enumerate(await assigned(pg)) if i != 1]
            check('respin gives a colour nobody else has', c not in others, (c, others))
            farez_col = (await assigned(pg))[0]['res'].split(' ')[0]
            await pg.click('.nrow:nth-child(1) .mini:last-child')   # × Farez
            chips = await chip_state(pg)
            check('deleting a name frees its colour', await count(pg) == 4 and not any(cc['t'] == farez_col and cc['used'] for cc in chips))

            # ---------- 6. persistence ----------
            snap = await assigned(pg)
            await pg.reload(); await pg.wait_for_timeout(400)
            check('reload keeps names + colours', await assigned(pg) == snap)
            check('reload keeps duration setting', await pg.input_value('#duration') == '2')

            # ---------- 7. Maing semule / confirm ----------
            pg.once('dialog', lambda d: asyncio.ensure_future(d.dismiss()))
            await pg.click('#resetBtn'); await pg.wait_for_timeout(200)
            check('Maing semule + Cancel changes nothing', await assigned(pg) == snap)
            pg.once('dialog', lambda d: asyncio.ensure_future(d.accept()))
            await pg.click('#resetBtn'); await pg.wait_for_timeout(200)
            rows = await assigned(pg)
            check('Maing semule clears colours, keeps names', [r['name'] for r in rows] == [r['name'] for r in snap] and all(r['res'] in ('—', '👀 gilirang') for r in rows) and rows[0]['turn'])

            # ---------- 8. colour chips ----------
            chips = await chip_state(pg)
            keep = ['Hitam', 'Putih']
            for cch in chips:
                if cch['t'] not in keep:
                    await pg.click(f".cchip:has-text('{cch['t']}')")
            got = []
            for i in range(2):
                got.append(await do_spin(pg, 'btn', f'2-colour wheel spin {i+1}:')); await close_modal(pg)
            check('only enabled colours can come out', sorted(got) == sorted(keep), got)
            check('colours used up → locked "Warne doh habih"', 'Warne doh habih' in await pg.text_content('#lock') and await pg.is_disabled('#spinBtn'))
            await pg.click('#allColorsBtn')
            check('"Semue warne" re-enables colours and unlocks', await pg.evaluate("document.getElementById('lock').classList.contains('hidden')"))
            for cch in await chip_state(pg):
                if not cch['off']: await pg.click(f".cchip:has-text('{cch['t']}')")
            check('all colours off → locked "Rode kosong"', 'Rode kosong' in await pg.text_content('#lock'))
            await pg.click('#allColorsBtn')
            order1 = [c['t'] for c in await chip_state(pg)]
            await pg.click('#shuffleColorsBtn')
            order2 = [c['t'] for c in await chip_state(pg)]
            adj = [frozenset((KEY[order2[i]], KEY[order2[(i + 1) % len(order2)]])) for i in range(len(order2))]
            check('Kocok warne reorders, no look-alike colours side by side', order1 != order2 and not any(a in SIMILAR for a in adj), order2)

            # ---------- 9. more names than colours ----------
            pg.once('dialog', lambda d: asyncio.ensure_future(d.accept()))
            await pg.click('#clearBtn'); await pg.wait_for_timeout(200)
            check('Kosongkang clears everything', await count(pg) == 0)
            check('counter shows 0/11', await pg.text_content('#nameCount') == '0/11')
            for i in range(1, 11):
                await add(pg, f'Org{i}')
            await paste(pg, 'Org11\nOrg12\nOrg13')
            check('pasting past the limit: stops at 11, says how many were left out', await count(pg) == 11 and 'Had 11 name' in await toast_text(pg) and '2 name dok masuk' in await toast_text(pg))
            check('counter shows 11/11', await pg.text_content('#nameCount') == '11/11')
            check('at 11 names: name box + Tamboh blocked, box says "cukup 11"', await pg.is_disabled('#nameInput') and await pg.is_disabled('#addBtn') and 'cukup 11' in (await pg.get_attribute('#nameInput', 'placeholder')))
            await pg.evaluate("document.getElementById('nameInput').disabled=false")   # even if someone forces the box open…
            await add(pg, 'Org99')
            check('…a 12th name still cannot get in', await count(pg) == 11 and 'Had 11 name' in await toast_text(pg))
            got = []
            for i in range(11):
                got.append(await do_spin(pg, 'btn', f'big game spin {i+1}:')); await close_modal(pg)
                if i == 0: check('name box stays blocked after a spin when full', await pg.is_disabled('#nameInput') and await pg.is_disabled('#addBtn'))
            check('11 names → 11 spins → all 11 colours, none repeated', sorted(got) == sorted(HEX.keys()), got)
            check('all 11 done → wheel locked "Semue doh dapak warne"', 'Semue doh dapak warne' in await pg.text_content('#lock') and await pg.is_disabled('#spinBtn'))
            await pg.evaluate("document.activeElement.blur()"); await pg.keyboard.press('Space'); await pg.wait_for_timeout(300)
            check('Space cannot force a spin when everyone is done', not await modal_open(pg))
            await pg.click('.nrow:nth-child(11) .mini:last-child')
            check('removing one name re-opens the name box (10/11)', not await pg.is_disabled('#nameInput') and await pg.text_content('#nameCount') == '10/11')

            # ---------- 10. keyboard in the name box ----------
            pg.once('dialog', lambda d: asyncio.ensure_future(d.accept()))
            await pg.click('#clearBtn'); await pg.wait_for_timeout(200)
            await pg.click('#nameInput'); await pg.keyboard.type('Mak Su'); await pg.keyboard.press('Control+Enter')
            await pg.wait_for_timeout(2600)
            check('Ctrl+Enter in name box adds name, does not spin', await count(pg) == 1 and not await modal_open(pg) and (await assigned(pg))[0]['name'] == 'Mak Su')

            # ---------- 11. sound + presentation ----------
            await pg.click('#soundBtn')
            check('sound toggles off', await pg.text_content('#soundBtn') == '🔇')
            await pg.reload(); await pg.wait_for_timeout(300)
            check('sound setting persists', await pg.text_content('#soundBtn') == '🔇')
            await pg.click('#fsBtn'); await pg.wait_for_timeout(400)
            pres = await pg.evaluate("document.body.classList.contains('presenting') || !!document.fullscreenElement")
            check('fullscreen / presentation mode turns on', pres)
            check('presentation hides settings', await pg.evaluate("getComputedStyle(document.querySelector('.settings-col')).display === 'none'") if await pg.evaluate("document.body.classList.contains('presenting')") else True)
            await pg.click('#fsBtn'); await pg.wait_for_timeout(400)
            check('presentation mode turns off', not await pg.evaluate("document.body.classList.contains('presenting') || !!document.fullscreenElement"))

            # ---------- 12. bad / old saved data ----------
            await pg.evaluate("localStorage.setItem('rodaWarna.v1', '{broken json')")
            await pg.reload(); await pg.wait_for_timeout(300)
            check('corrupted save → app still loads clean', await count(pg) == 0 and 'Bubuh name' in await pg.text_content('#lock'))
            await pg.evaluate("""localStorage.setItem('rodaWarna.v1', JSON.stringify({names:[{name:'A',color:'red'},{name:'B',color:'red'},{name:'C',color:'mint'},{name:'',color:null},{bad:1}], order:['x'], duration:99}))""")
            await pg.reload(); await pg.wait_for_timeout(300)
            rows = await assigned(pg)
            check('old save: repeated colour cleared, unknown colour cleared, junk ignored',
                  [r['name'] for r in rows] == ['A', 'B', 'C'] and rows[0]['res'].startswith('Merah') and rows[1]['res'] == '👀 gilirang' and rows[2]['res'] == '—', rows)
            check('old save: bad duration ignored', await pg.input_value('#duration') == '5')
            await pg.evaluate("""localStorage.setItem('rodaWarna.v1', JSON.stringify({names: Array.from({length:15}, (_, i) => ({name:'P'+i, color:null}))}))""")
            await pg.reload(); await pg.wait_for_timeout(300)
            check('old save with 15 names → only first 11 load', await count(pg) == 11 and (await assigned(pg))[-1]['name'] == 'P10')
            await ctx.close()

            # ---------- 13. phone ----------
            m = await b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
            mp = await m.new_page()
            mp.on('pageerror', lambda e: errors.append('mobile pageerror: ' + str(e)))
            mp.on('console', lambda msg: errors.append('mobile console: ' + msg.text) if msg.type == 'error' else None)
            await mp.goto(URL); await mp.wait_for_timeout(400)
            check('phone: no sideways scrolling', await mp.evaluate('document.documentElement.scrollWidth <= innerWidth'))
            for n in ['Farez', 'Aini', 'Ali', 'Siti', 'Ravi', 'Mak Su', 'Pak Long']:
                await mp.fill('#nameInput', n); await mp.press('#nameInput', 'Enter')
            await mp.evaluate("const d=document.getElementById('duration'); d.value=2; d.dispatchEvent(new Event('input'))")
            await mp.evaluate('window.scrollTo(0, 0)'); await mp.wait_for_timeout(200)
            y0 = await mp.evaluate('scrollY')
            await mp.tap('#spinBtn')
            await mp.wait_for_selector('#modal:not(.hidden)', timeout=9000)
            t = await mp.text_content('#winTitle')
            check('phone: pointer colour = announced colour', rgb_matches(colour_of(t), await pointer_rgb(mp)), t)
            check('phone: page does not jump after a spin', await mp.evaluate('scrollY') == y0)
            box = await mp.evaluate("(() => { const r = document.querySelector('.modal-card').getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom]; })()")
            check('phone: popup fits on screen', box[0] >= 0 and box[1] <= 390 and box[2] >= 0 and box[3] <= 844, box)
            await mp.tap('#closeBtn'); await mp.wait_for_timeout(200)
            check('phone: still no sideways scrolling with names', await mp.evaluate('document.documentElement.scrollWidth <= innerWidth'))
            await m.close()
            await b.close()
    finally:
        srv.terminate()

    # web font can't download inside this test sandbox — ignore only that
    real = [e for e in errors if 'fonts.g' not in e and 'Failed to load resource' not in e]
    check('no JavaScript errors anywhere', not real, real)
    fails = [r for r in results if not r[1]]
    print(f'\n==== {len(results) - len(fails)}/{len(results)} checks passed ====')
    for f in fails: print('FAILED:', f[0], '|', f[2])

asyncio.run(main())
