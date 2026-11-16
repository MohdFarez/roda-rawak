# python3 tests/e2e_test.py — end-to-end test: page + real Code.gs (via tests/mock-server.js), several phones at once
import asyncio, json, os, subprocess, sys, time, urllib.request
from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8790
BASE = f'http://127.0.0.1:{PORT}'
API = f'{BASE}/api'
def page_url(poll=2000): return f'{BASE}/index.html?api={API}&poll={poll}'

NAMES = {'Merah': 'red', 'Pink': 'pink', 'Blue': 'blue', 'Ungu': 'purple', 'Hijau': 'green', 'Kuning': 'yellow',
         'Oren': 'orange', 'Putih': 'white', 'Hitam': 'black', 'Coklat': 'brown', 'Gold': 'gold'}
HEX = {'red': '#FF4245', 'pink': '#FF6FB5', 'blue': '#0091FF', 'purple': '#AF52DE', 'green': '#30D158', 'yellow': '#FFD600',
       'orange': '#FF9230', 'white': '#F5F5F7', 'black': '#1C1C1E', 'brown': '#8B5E3C', 'gold': None}

results = []
def check(name, ok, detail=''):
    results.append((name, bool(ok), detail))
    print(('PASS ' if ok else 'FAIL ') + name + ((' — ' + str(detail)) if detail and not ok else ''))

def ctl(path, data=None):
    req = urllib.request.Request(BASE + path, data=data.encode() if data else None, method='POST' if data else 'GET')
    return json.loads(urllib.request.urlopen(req).read())
def rows(): return ctl('/__latency?ms=700')['rows'][1:]
def server_spin(name):
    req = urllib.request.Request(API, data=json.dumps({'action': 'spin', 'name': name}).encode(), method='POST')
    return json.loads(urllib.request.urlopen(req).read())

def rgb_ok(key, rgb):
    if key == 'gold':
        r, g, b = rgb; return r >= 150 and g >= 100 and b <= 150 and r > g > b
    h = HEX[key]; exp = [int(h[i:i + 2], 16) for i in (1, 3, 5)]
    return all(abs(a - e) <= 4 for a, e in zip(rgb, exp))

async def pointer_rgb(pg):
    return await pg.evaluate("""() => { const c = document.querySelector('#wheelWrap canvas'), ctx = c.getContext('2d');
        const d = ctx.getImageData(Math.round(c.width / 2), Math.round(c.height / 2 - c.width / 2 * 0.6), 1, 1).data; return [d[0], d[1], d[2]]; }""")
async def modal_open(pg): return await pg.evaluate("!document.getElementById('modal').classList.contains('hidden')")
async def txt(pg, sel): return (await pg.text_content(sel) or '').strip()
async def list_rows(pg):
    return await pg.evaluate("""() => [...document.querySelectorAll('.prow')].map(r => ({ name: r.querySelector('.nm').textContent,
        res: r.querySelector('.res').textContent.trim(), mine: !!r.querySelector('.me') }))""")
def key_of(title): return NAMES.get(title.split(' ')[0])

async def spin(pg, name, label, expect_ok=True):
    await pg.fill('#nameInput', name)
    await pg.click('#spinBtn')
    await pg.wait_for_selector('#modal:not(.hidden)', timeout=15000)
    title = await txt(pg, '#winTitle')
    key = key_of(title)
    if expect_ok:
        check(f'{label}: wheel stops on the colour the database gave ({title})', key and rgb_ok(key, await pointer_rgb(pg)), await pointer_rgb(pg))
    return key

async def close(pg):
    await pg.click('#closeBtn'); await pg.wait_for_timeout(150)

async def wait_until(pg, js, timeout=8000):
    try:
        await pg.wait_for_function(js, timeout=timeout); return True
    except Exception:
        return False

async def main():
    srv = subprocess.Popen(['node', os.path.join(HERE, 'mock-server.js'), str(PORT)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.8)
    ctl('/__reset')
    errors = []
    def watch(pg, tag):
        pg.on('pageerror', lambda e: errors.append(f'{tag} pageerror: {e}'))
        pg.on('console', lambda m: errors.append(f'{tag} console: {m.text}') if m.type == 'error' else None)
    try:
        async with async_playwright() as p:
            br = await p.chromium.launch()
            # phone A, laptop B, phone C (very slow refresh = stale on purpose)
            cA = await br.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
            cB = await br.new_context(viewport={'width': 1280, 'height': 860}, permissions=['clipboard-read', 'clipboard-write'])
            cC = await br.new_context(viewport={'width': 412, 'height': 900}, is_mobile=True, has_touch=True)
            A, B, C = await cA.new_page(), await cB.new_page(), await cC.new_page()
            for pg, t in ((A, 'A'), (B, 'B'), (C, 'C')): watch(pg, t)
            posts = []
            B.on('request', lambda r: posts.append(r.headers.get('content-type', '')) if r.method == 'POST' else None)

            ctl('/__latency?ms=2500')                     # slow first load so the loading state can be seen
            await A.goto(page_url())
            check('while loading: wheel says "Tengah amik" and Pusing is off', 'Tengah amik' in await txt(A, '#lock') and await A.is_disabled('#spinBtn'))
            await B.goto(page_url()); await C.goto(page_url(poll=600000))
            ctl('/__latency?ms=700')
            await wait_until(A, "document.getElementById('lock').classList.contains('hidden')")
            await wait_until(B, "document.getElementById('lock').classList.contains('hidden')")
            await wait_until(C, "document.getElementById('lock').classList.contains('hidden')")
            check('loaded: 11 colours, 0/11, live, empty list', '11 warne' in await txt(A, '#status') and await txt(A, '#count') == '0/11'
                  and 'Live' in await txt(A, '#live') and 'Belum ade' in await txt(A, '#picks'))

            await A.fill('#nameInput', '   '); await A.click('#spinBtn'); await A.wait_for_timeout(200)
            check('blank name refused', 'Taip name' in await txt(A, '#toast') and not await modal_open(A) and rows() == [])

            # --- first family member
            await A.fill('#nameInput', 'Farez'); await A.click('#spinBtn'); await A.wait_for_timeout(250)
            check('while spinning: form locked, button says "Tengah pusing"', await A.is_disabled('#nameInput') and 'Tengah pusing' in await txt(A, '#spinBtn'))
            await A.wait_for_selector('#modal:not(.hidden)', timeout=15000)
            t = await txt(A, '#winTitle'); kF = key_of(t)
            check(f'phone A: wheel stops on the colour the database gave ({t})', rgb_ok(kF, await pointer_rgb(A)))
            check('popup: "Farez dapak warne", no hex code', 'Farez dapak warne' in await txt(A, '#winKicker') and '#' not in await txt(A, '#modalTop'))
            r = rows()
            check('saved in the Sheet: 1 row with Farez + colour key', len(r) == 1 and r[0][1] == 'Farez' and r[0][3] == kF, r)
            await A.wait_for_timeout(2600)
            check('popup open + live refresh: wheel not reshuffled under it', rgb_ok(kF, await pointer_rgb(A)))
            await A.keyboard.press('Escape'); await A.wait_for_timeout(200)
            check('Escape closes popup', not await modal_open(A))
            lr = await list_rows(A)
            check('phone A list: Farez with colour + "👈 mung"', lr and lr[0]['name'] == 'Farez' and lr[0]['mine'] and key_of(lr[0]['res']) == kF, lr)
            check('phone A wheel: Farez colour gone (10 left)', '10 warne' in await txt(A, '#status'))

            ok = await wait_until(B, "document.querySelectorAll('.prow').length === 1", 6000)
            check('laptop B sees Farez by itself (live update, no reload)', ok and '10 warne' in await txt(B, '#status'))
            check('laptop B: Farez not marked as "mung" there', not (await list_rows(B))[0]['mine'])

            # --- second member on another device
            kA = await spin(B, 'Aini', 'laptop B')
            check('Aini gets a different colour from Farez', kA and kA != kF, (kA, kF))
            check('spin request is text/plain (works with Google Apps Script, no CORS preflight)', posts and all(p.startswith('text/plain') for p in posts), posts)
            await B.mouse.click(5, 5); await B.wait_for_timeout(200)
            check('tap outside closes popup', not await modal_open(B))

            # --- same name again
            await B.fill('#nameInput', '  FAREZ '); await B.click('#spinBtn'); await B.wait_for_timeout(300)
            check('same name again (any case): shows their existing colour, no new row',
                  await modal_open(B) and 'Farez doh pusing' in await txt(B, '#winKicker') and key_of(await txt(B, '#winTitle')) == kF and len(rows()) == 2)
            check('…with a hint to add an initial if it is someone else', 'initial' in await txt(B, '#winSub'))
            await close(B)

            # --- phone C has a stale wheel (has not refreshed since load)
            check('phone C is stale on purpose (still shows 11 colours)', '11 warne' in await txt(C, '#status'))
            await C.fill('#nameInput', 'aini'); await C.click('#spinBtn')
            await C.wait_for_selector('#modal:not(.hidden)', timeout=15000)
            check('stale phone, name taken meanwhile → database says "already spun", shows her colour', 'doh pusing' in await txt(C, '#winKicker') and key_of(await txt(C, '#winTitle')) == kA and len(rows()) == 2)
            await close(C)
            kC = await spin(C, 'Ali', 'stale phone C')
            check('stale phone still never gets a taken colour', kC not in (kF, kA), (kC, kF, kA))
            await close(C)

            # --- two people press Pusing at the same moment
            await A.fill('#nameInput', 'Siti'); await B.fill('#nameInput', 'Ravi')
            await asyncio.gather(A.click('#spinBtn'), B.click('#spinBtn'))
            await asyncio.gather(A.wait_for_selector('#modal:not(.hidden)', timeout=20000), B.wait_for_selector('#modal:not(.hidden)', timeout=20000))
            kS, kR = key_of(await txt(A, '#winTitle')), key_of(await txt(B, '#winTitle'))
            check('two phones spinning at the same time get different colours', kS and kR and kS != kR and len({kF, kA, kC, kS, kR}) == 5, (kS, kR))
            check('both wheels stop on their own colour', rgb_ok(kS, await pointer_rgb(A)) and rgb_ok(kR, await pointer_rgb(B)))
            await close(A); await close(B)

            # --- injection-looking name
            await spin(A, '<img src=x onerror=alert(1)>', 'odd name')
            await close(A)
            check('HTML in a name shows as text, nothing injected', await A.evaluate("!document.querySelector('.prow img')") and any(r['name'].startswith('<img') for r in await list_rows(A)))

            # --- copy (laptop B)
            await wait_until(B, "document.querySelectorAll('.prow').length === 6")
            await B.click('#copyBtn'); await B.wait_for_timeout(200)
            clip = await B.evaluate('navigator.clipboard.readText()')
            lines = clip.split('\n')
            check('Saling keputusang: header + 6 numbered lines', lines[0].startswith('🎁 Tuka Hadioh') and len(lines) == 8 and lines[2].startswith('1. Farez — '), clip)

            # --- fill up to 11 from "other phones"
            i = 0
            while len(rows()) < 11:
                server_spin(f'Sepupu {i}'); i += 1
            ok = await wait_until(A, "document.getElementById('count').textContent === '11/11'")
            check('11/11 shows up on phone A by itself', ok)
            check('full: wheel locked "Semue doh dapak warne", name box closed "cukup 11"',
                  'Semue doh dapak warne' in await txt(A, '#lock') and await A.is_disabled('#nameInput') and await A.is_disabled('#spinBtn')
                  and 'cukup 11' in await A.get_attribute('#nameInput', 'placeholder'))
            ks = [r[3] for r in rows()]
            check('database: 11 people, 11 different colours', len(set(ks)) == 11, ks)

            # stale phone C tries a 12th
            await C.fill('#nameInput', 'Orang 12'); await C.click('#spinBtn'); await C.wait_for_timeout(3500)
            check('stale phone: 12th person refused ("cukup 11"), nothing saved', 'cukup 11' in await txt(C, '#toast') and len(rows()) == 11 and not await modal_open(C))
            check('stale phone catches up to 11/11 after refusal', await txt(C, '#count') == '11/11' and 'Semue doh' in await txt(C, '#lock'))

            # --- organiser deletes a row in the Google Sheet
            all_rows = rows()
            gone = all_rows[3]
            ctl('/__rows', json.dumps([[r[0], r[1], r[2], r[3]] for k, r in enumerate(all_rows) if k != 3]))
            ok = await wait_until(A, "document.getElementById('count').textContent === '10/11'")
            check('row deleted in Sheet → phones show 10/11 and reopen the name box', ok and not await A.is_disabled('#nameInput'))
            check('…wheel shows just the freed colour', '1 warne' in await txt(A, '#status'))
            kL = await spin(A, 'Last One', 'one-colour wheel')
            check('last spin gets exactly the freed colour', kL == gone[3], (kL, gone))
            await close(A)

            # --- network trouble
            ctl('/__reset'); await A.reload(); await wait_until(A, "document.getElementById('lock').classList.contains('hidden')")
            ctl('/__mode?m=down')
            ok = await wait_until(A, "document.getElementById('live').textContent.includes('Offline')")
            check('server unreachable → shows 🔴 Offline', ok)
            await A.fill('#nameInput', 'Tok Wan'); await A.click('#spinBtn'); await A.wait_for_timeout(2500)
            check('spin while offline: wheel stops, friendly "Internet" message, nothing saved', 'Internet' in await txt(A, '#toast') and not await modal_open(A) and len(rows()) == 0)
            check('…form unlocked again so they can retry', not await A.is_disabled('#spinBtn'))
            ctl('/__mode?m=garbage')
            await A.wait_for_timeout(2600)
            check('garbage reply from server (error page) → stays calm, Offline', 'Offline' in await txt(A, '#live'))
            ctl('/__mode?m=ok')
            ok = await wait_until(A, "document.getElementById('live').textContent.includes('Live')")
            check('server back → 🟢 Live again', ok)
            kT = await spin(A, 'Tok Wan', 'after reconnect')
            check('retry after reconnect works', kT and len(rows()) == 1)
            await close(A)

            # --- mine survives reload
            await A.reload(); await wait_until(A, "document.getElementById('lock').classList.contains('hidden')")
            check('"👈 mung" still on my names after reload', any(r['mine'] and r['name'] == 'Tok Wan' for r in await list_rows(A)))

            # --- sound setting persists
            await A.click('#soundBtn'); await A.reload(); await A.wait_for_timeout(400)
            check('sound off remembered', await txt(A, '#soundBtn') == '🔇')

            # --- phone layout
            await A.evaluate('window.scrollTo(0, 0)'); await A.wait_for_timeout(100)
            y0 = await A.evaluate('scrollY')
            await spin(A, 'Mak Su', 'phone layout')
            check('phone: page does not jump during a spin', await A.evaluate('scrollY') == y0)
            box = await A.evaluate("(() => { const r = document.querySelector('.modal-card').getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom, innerWidth, innerHeight]; })()")
            check('phone: popup fits the screen', box[0] >= 0 and box[1] <= box[4] and box[2] >= 0 and box[3] <= box[5], box)
            await close(A)
            check('phone: no sideways scrolling', await A.evaluate('document.documentElement.scrollWidth <= innerWidth'))

            # --- slow server: spin gives up nicely after 30 s
            await wait_until(B, "!document.getElementById('nameInput').disabled")
            ctl('/__mode?m=slow')
            await B.fill('#nameInput', 'Lambat'); await B.click('#spinBtn')
            ok = await wait_until(B, "document.getElementById('toast').textContent.includes('Internet')", 40000)
            check('very slow server: gives up after 30 s with a message, form usable again', ok and not await B.is_disabled('#spinBtn'))
            ctl('/__mode?m=ok')

            # --- not configured yet
            N = await (await br.new_context()).new_page(); watch(N, 'N')
            await N.route('https://script.google.com/**', lambda route: route.abort())
            await N.goto(f'{BASE}/index.html')
            ok = await wait_until(N, "document.getElementById('lock').textContent.includes('Dok leh sambung')", 20000)
            check('real database unreachable → clear "Dok leh sambung", Pusing off', ok and await N.is_disabled('#spinBtn'))
            await br.close()
    finally:
        srv.terminate()

    expected = ('fonts.g', 'Failed to load resource', 'net::')
    real = [e for e in errors if not any(x in e for x in expected)]
    check('no JavaScript errors on any device', not real, real)
    fails = [r for r in results if not r[1]]
    print(f'\n==== e2e: {len(results) - len(fails)}/{len(results)} checks passed ====')
    for f in fails: print('FAILED:', f[0], '|', f[2])
    sys.exit(1 if fails else 0)

asyncio.run(main())
