# 🎁 Rode Warne Tuka Hadioh

Gaya Gen Z, loghat Terengganu 🐢 — setiap ahli keluarga pusing guna phone sendiri, dapat satu warne tema untuk tukar hadiah.

🔗 Live: https://mohdfarez.github.io/roda-rawak/

**11 warna tema:** Merah ❤️ · Pink 💗 · Blue 💙 · Ungu 💜 · Hijau 💚 · Kuning 💛 · Oren 🧡 · Putih 🤍 · Hitam 🖤 · Coklat 🤎 · Gold ✨

## Cara guna
1. Buka link kat phone, taip name, tekan **🌀 Pusing!**
2. Server pilih warne secara rawak — warne yang doh keluar terus hilang dari rode semua orang
3. **Senarai Keluarga** update sendiri; had 11 orang
4. Name yang sama dok buleh pusing dua kali

## Database (Google Sheet)
- Semua keputusan masuk Google Sheet **"Rode Warne Tuka Hadioh — Database"** (tab `Keputusan`)
- Buang sorang (warne die balik kak rode) → padam baris die
- Maing semule → padam semua baris kecuali tajuk
- Jangan ubah lajur **Kod**

Backend: [`apps-script/Code.gs`](apps-script/Code.gs) — Google Apps Script Web App (Execute as: Me, Access: Anyone).
URL Web App diletak dalam `DEFAULT_API` dalam `index.html`.

## Test
```bash
node tests/backend.test.js        # Code.gs dengan Sheet tiruan
python3 tests/e2e_test.py         # page + Code.gs sebenar, beberapa phone serentak (perlu Playwright)
```
