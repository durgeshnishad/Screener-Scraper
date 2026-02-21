╔══════════════════════════════════════════════════════════╗
║           Screener Scraper — Mac Setup                   ║
╚══════════════════════════════════════════════════════════╝

STEP 1 — Install (do this once)
────────────────────────────────
1. Open Terminal  
   → Press Cmd+Space, type "Terminal", press Enter

2. Type "cd " (with a space after cd), then drag the 
   screener_scraper folder into Terminal. Press Enter.

3. Paste this and press Enter:
   xattr -rd com.apple.quarantine . && chmod +x *.sh && bash install_mac.sh


STEP 2 — Run the scraper (every time)
──────────────────────────────────────
1. Open Terminal

2. Type "cd " then drag the screener_scraper folder in. Press Enter.

3. Paste this and press Enter:
   python3 web_scraper.py


That's it! A browser opens → log in → type tickers → done.

══════════════════════════════════════════════════════════
WHY TERMINAL?
Mac blocks double-clicking scripts downloaded from the
internet. Using Terminal directly bypasses this completely
and always works.
══════════════════════════════════════════════════════════
