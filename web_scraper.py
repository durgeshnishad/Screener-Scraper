"""
Screener.in Document Scraper
Just double-click run.bat to start!
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

import requests
from playwright.async_api import async_playwright


# ─── CONFIG ──────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent / "scraper_output"
COOKIE_FILE = Path(__file__).parent / "screener_session.json"
MONTHS_BACK = 18

MONTH_MAP = {
    "jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
    "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12
}


# ─── SESSION SAVE/LOAD ───────────────────────────────────────────────────────
def save_session(cookies: list):
    COOKIE_FILE.write_text(json.dumps(cookies, indent=2))

def load_session() -> list:
    if not COOKIE_FILE.exists():
        return []
    try:
        return json.loads(COOKIE_FILE.read_text())
    except Exception:
        return []


# ─── LOGIN: open real browser, wait for user ─────────────────────────────────
async def get_session_context(playwright):
    """
    Opens a visible browser. Uses saved cookies if still valid, otherwise
    shows the login page and waits for the user to log in.
    The SAME browser context is used for all scraping so cookies work everywhere.
    """
    cookies = load_session()

    browser = await playwright.chromium.launch(
        headless=False,
        args=["--start-maximized", "--disable-blink-features=AutomationControlled"],
    )
    context = await browser.new_context(
        accept_downloads=True,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport=None,
    )

    if cookies:
        print("  [..] Checking saved session...")
        await context.add_cookies(cookies)
        page = await context.new_page()
        await page.goto("https://www.screener.in", wait_until="networkidle", timeout=20000)
        logged_in = "logout" in (await page.content()).lower()
        await page.close()

        if logged_in:
            print("  [OK] Logged in using saved session!")
            return browser, context

        print("  [..] Session expired — please log in again")
        COOKIE_FILE.unlink(missing_ok=True)

    # Open login page and wait for user
    print()
    print("  ┌──────────────────────────────────────────┐")
    print("  │  A browser window has opened             │")
    print("  │  Please log in to screener.in            │")
    print("  │  (Google login works fine)               │")
    print("  │  Come back here once you are logged in   │")
    print("  └──────────────────────────────────────────┘")
    print()

    page = await context.new_page()
    await page.goto("https://www.screener.in/login/", wait_until="networkidle")

    print("  Waiting for login", end="", flush=True)
    while True:
        await asyncio.sleep(2)
        print(".", end="", flush=True)
        try:
            if "logout" in (await page.content()).lower():
                break
        except Exception:
            pass
    print(" done!\n")
    await page.close()

    cookies = await context.cookies()
    save_session(cookies)
    print("  [OK] Session saved — next run will skip this step!\n")

    return browser, context


# ─── HELPERS ─────────────────────────────────────────────────────────────────
def make_dirs(ticker: str) -> dict:
    root = BASE_DIR / ticker
    dirs = {
        "root":     root,
        "pages":    root / "pages",
        "annual":   root / "annual_reports",
        "ratings":  root / "credit_ratings",
        "concalls": root / "concalls",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs

def get_valid_fy_years() -> set:
    today = datetime.now()
    fy = today.year + 1 if today.month > 3 else today.year
    return {fy, fy - 1}

def get_concall_cutoff() -> tuple:
    today = datetime.now()
    total = today.year * 12 + today.month - MONTHS_BACK
    y, m  = divmod(total, 12)
    if m == 0: m = 12; y -= 1
    return y, m

def year_from_text(text: str):
    m = re.search(r"\b(20\d{2})\b", text)
    return int(m.group(1)) if m else None

def parse_month_year(text: str):
    m = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+(20\d{2})",
                  text.strip().lower())
    if m:
        return int(m.group(2)), MONTH_MAP[m.group(1)[:3]]
    return None

def safe_name(s: str) -> str:
    return re.sub(r"[^\w\-]", "_", s.strip())[:60].strip("_")

def is_youtube_url(url: str) -> bool:
    return any(x in url for x in ["youtube.com/watch", "youtu.be/", "youtube.com/live"])


# ─── FILE DOWNLOAD ────────────────────────────────────────────────────────────
async def download_file(context, url: str, save_path: Path, base_url: str) -> bool:
    clean_url = url.split("#")[0]
    if not clean_url.startswith("http"):
        return False
    if save_path.exists() and save_path.stat().st_size > 0:
        print(f"        [=] Already exists — {save_path.name}")
        return True

    # Method 1: Playwright (authenticated via cookies)
    try:
        resp = await context.request.get(
            clean_url, timeout=60000,
            headers={"Referer": base_url, "Accept": "*/*"}
        )
        if resp.ok:
            save_path.write_bytes(await resp.body())
            print(f"        [↓] {save_path.name}")
            return True
    except Exception:
        pass

    # Method 2: urllib fallback
    try:
        req = urllib.request.Request(clean_url, headers={
            "User-Agent": "Mozilla/5.0 Chrome/120.0.0.0",
            "Referer": base_url,
        })
        with urllib.request.urlopen(req, timeout=60) as r:
            save_path.write_bytes(r.read())
        print(f"        [↓] {save_path.name}")
        return True
    except Exception as e:
        print(f"        [!!] Failed: {save_path.name} — {e}")
        return False




def find_node() -> str:
    """Return path to node executable, works on Windows and Mac."""
    found = shutil.which("node")
    if found:
        return found
    # Windows paths
    for c in [
        "C:\\Program Files\\nodejs\\node.exe",
        "C:\\Program Files (x86)\\nodejs\\node.exe",
    ]:
        if Path(c).exists():
            return c
    # Mac/Linux paths (Homebrew)
    for c in [
        "/opt/homebrew/bin/node",       # Apple Silicon
        "/usr/local/bin/node",          # Intel Mac
        "/usr/bin/node",
    ]:
        if Path(c).exists():
            return c
    return None


def install_node():
    """Download and silently install Node.js on Windows or Mac."""
    import platform
    system = platform.system()
    print("        [..] Node.js not found — installing for YouTube support...")

    try:
        if system == "Windows":
            node_url  = "https://nodejs.org/dist/v20.11.0/node-v20.11.0-x64.msi"
            installer = Path(__file__).parent / "node_installer.msi"
            import urllib.request as ur
            ur.urlretrieve(node_url, str(installer))
            print("        [..] Installing Node.js (may take ~1 min)...")
            subprocess.run(["msiexec", "/i", str(installer), "/quiet", "/norestart"],
                           timeout=180, check=True)
            try:
                installer.unlink()
            except Exception:
                pass
            node_dir = "C:\\Program Files\\nodejs"
            if node_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = node_dir + ";" + os.environ.get("PATH", "")

        elif system == "Darwin":  # Mac
            # Try brew first
            if shutil.which("brew"):
                print("        [..] Installing via Homebrew...")
                subprocess.run(["brew", "install", "node"], timeout=180, check=True)
            else:
                print("        [!!] Please install Node.js from https://nodejs.org")
                return False
            # Add brew paths
            for p in ["/opt/homebrew/bin", "/usr/local/bin"]:
                if p not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = p + ":" + os.environ.get("PATH", "")

        else:
            print("        [!!] Please install Node.js from https://nodejs.org")
            return False

        print("        [OK] Node.js installed!")
        return True

    except Exception as e:
        print(f"        [!!] Could not install Node.js: {e}")
        print("        [!!] Install manually from: https://nodejs.org")
        return False


async def download_rec(url: str, save_path: Path, base_url: str, context) -> bool:
    clean_url = url.split("#")[0]
    stem = save_path.stem
    existing = list(save_path.parent.glob(f"{stem}.*"))
    if existing and existing[0].stat().st_size > 0:
        print(f"        [=] Already exists — {existing[0].name}")
        return True

    if is_youtube_url(clean_url):
        print(f"        [YT] Downloading audio as MP3...")

        # Ensure yt-dlp is installed
        if not shutil.which("yt-dlp"):
            subprocess.run([sys.executable, "-m", "pip", "install", "yt-dlp", "--quiet"], check=True)

        # Ensure Node.js is available
        node = find_node()
        if not node:
            if install_node():
                node = find_node()

        mp3_path = save_path.with_suffix(".mp3")
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "--output", str(mp3_path),
            "--no-playlist",
            "--no-warnings",
            "--newline",          # one progress line per update (no ANSI cursor tricks)
        ]
        if node:
            cmd += ["--js-runtimes", f"nodejs:{node}"]
        cmd.append(clean_url)

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            last_pct = ""
            for line in proc.stdout:
                line = line.strip()
                # yt-dlp progress lines look like:
                # [download]  42.3% of ~  8.50MiB at  1.23MiB/s ETA 00:05
                if "[download]" in line and "%" in line:
                    m = re.search(r'([\d\.]+)%.*?of\s+([\S]+).*?at\s+([\S]+)', line)
                    if m:
                        pct, total, speed = m.group(1), m.group(2), m.group(3)
                        bar_len   = 20
                        filled    = int(float(pct) / 100 * bar_len)
                        bar       = "█" * filled + "░" * (bar_len - filled)
                        progress  = f"        [YT] |{bar}| {pct:>5}%  {total}  @ {speed}"
                        # Overwrite same line
                        print(f"\r{progress}", end="", flush=True)
                        last_pct = pct
            proc.wait()
            if last_pct:
                print()  # newline after progress bar

            if mp3_path.exists() and mp3_path.stat().st_size > 0:
                size_mb = mp3_path.stat().st_size / (1024 * 1024)
                print(f"        [↓] {mp3_path.name}  ({size_mb:.1f} MB)")
                return True
            else:
                print(f"        [!!] yt-dlp failed (exit code {proc.returncode})")
        except Exception as e:
            print(f"        [!!] yt-dlp error: {e}")
        return False

    return await download_file(context, clean_url, save_path.with_suffix(".mp3"), base_url)


# ─── EXCEL ───────────────────────────────────────────────────────────────────
async def download_excel(page, context, base_url: str, dirs: dict, ticker: str) -> bool:
    print("\n  [Excel]")
    existing = list(dirs["root"].glob("*.xlsx"))
    if existing and existing[0].stat().st_size > 0:
        print(f"    [=] Already exists — {existing[0].name}")
        return True

    # ── Step 1: Find the Export button ───────────────────────────────────────
    btn = None
    btn_text_found = None
    selectors = [
        "a:has-text('EXPORT TO EXCEL')",
        "a:has-text('Export to Excel')",
        "button:has-text('EXPORT TO EXCEL')",
        "button:has-text('Export to Excel')",
    ]
    for sel in selectors:
        b = page.locator(sel).first
        if await b.count() > 0:
            btn = b
            btn_text_found = sel
            break

    if not btn:
        # Log what buttons ARE on the page to help diagnose
        all_btns = await page.evaluate("""
            () => Array.from(document.querySelectorAll('a, button'))
                  .map(el => el.innerText.trim())
                  .filter(t => t.length > 0 && t.length < 50)
        """)
        excel_hints = [t for t in all_btns if "excel" in t.lower() or "export" in t.lower()]
        if excel_hints:
            print(f"    [i] Found export-like buttons: {excel_hints}")
            print(f"    [i] Trying to click first one...")
            try:
                btn = page.locator(f"a:has-text('{excel_hints[0]}'), button:has-text('{excel_hints[0]}')").first
            except Exception:
                pass
        else:
            print(f"    [i] No Export button found on page")
            print(f"    [i] This usually means you are not logged in")

    # ── Step 2: Click the button ──────────────────────────────────────────────
    if btn:
        print(f"    [i] Found button — clicking...")
        try:
            async with page.expect_download(timeout=60000) as dl_info:
                await btn.click()
            dl    = await dl_info.value
            fname = dl.suggested_filename or f"{ticker}_financials.xlsx"
            sp    = dirs["root"] / fname
            await dl.save_as(str(sp))
            size_kb = sp.stat().st_size // 1024
            print(f"    [↓] {sp.name}  ({size_kb} KB)")
            return True
        except Exception as e:
            print(f"    [i] Button click failed: {e}")

    # ── Step 3: Fallback direct HTTP request ──────────────────────────────────
    print(f"    [i] Trying direct download URLs...")
    for url in [
        f"https://www.screener.in/api/company/{ticker}/export/",
        f"https://www.screener.in/company/{ticker}/export/",
    ]:
        try:
            resp = await context.request.get(url, timeout=30000)
            content_type = resp.headers.get("content-type", "")
            body = await resp.body()
            print(f"    [i] {url.split('/')[-2]}/ → HTTP {resp.status}  {content_type[:50]}  {len(body)} bytes")
            if resp.ok and len(body) > 5000 and "html" not in content_type:
                sp = dirs["root"] / f"{ticker}_financials.xlsx"
                sp.write_bytes(body)
                print(f"    [↓] {sp.name}  ({len(body)//1024} KB)")
                return True
        except Exception as e:
            print(f"    [i] {url} failed: {e}")

    print("    [!!] Excel download failed — most likely not logged in")
    print("    [i]  Delete screener_session.json and run again to re-login")
    return False


# ─── DOCUMENT SECTIONS ───────────────────────────────────────────────────────
async def scrape_annual_reports(page, context, base_url, valid_years, dirs):
    print("\n  [Annual Reports]")
    items = await page.evaluate("""() => {
        const results = [];
        const heading = Array.from(document.querySelectorAll('*'))
            .find(el => el.childElementCount === 0 && el.innerText?.trim() === 'Annual reports');
        if (!heading) return results;
        let c = heading.parentElement;
        for (let i = 0; i < 6; i++) {
            const links = c?.querySelectorAll('a[href]');
            if (links?.length) {
                links.forEach(a => results.push({
                    text: (a.closest('li,div,tr') || a).innerText.trim(),
                    url: a.href
                }));
                break;
            }
            c = c?.parentElement;
        }
        return results;
    }""")
    count = 0
    for item in items:
        year = year_from_text(item["text"])
        if year not in valid_years:
            continue
        label = safe_name(item["text"].split('\n')[0])
        ok = await download_file(context, item["url"],
                                 dirs["annual"] / f"AnnualReport_FY{year}_{label}.pdf", base_url)
        if ok: count += 1
    print(f"    {count} downloaded" if count else "    None found")
    return count


async def scrape_credit_ratings(page, context, base_url, valid_years, dirs):
    print("\n  [Credit Ratings]")
    items = await page.evaluate("""() => {
        const results = [];
        const heading = Array.from(document.querySelectorAll('*'))
            .find(el => el.childElementCount === 0 && el.innerText?.trim() === 'Credit ratings');
        if (!heading) return results;
        let c = heading.parentElement;
        for (let i = 0; i < 6; i++) {
            const links = c?.querySelectorAll('a[href]');
            if (links?.length) {
                links.forEach(a => {
                    const row = a.closest('li,tr,div') || a.parentElement;
                    results.push({ text: a.innerText.trim(),
                                   rowText: row?.innerText.trim() || '', url: a.href });
                });
                break;
            }
            c = c?.parentElement;
        }
        return results;
    }""")
    count = 0
    for item in items:
        year = year_from_text(item["rowText"]) or year_from_text(item["text"])
        if year not in valid_years:
            continue
        label = safe_name(item["rowText"].replace('\n', ' '))
        ok = await download_file(context, item["url"],
                                 dirs["ratings"] / f"CreditRating_{year}_{label}.pdf", base_url)
        if ok: count += 1
    print(f"    {count} downloaded" if count else "    None found")
    return count


async def scrape_concalls(page, context, base_url, dirs):
    print("\n  [Concalls]")
    cutoff_y, cutoff_m = get_concall_cutoff()

    await page.evaluate("""() => {
        const el = Array.from(document.querySelectorAll('*'))
            .find(e => e.childElementCount === 0 && e.innerText?.trim() === 'Concalls');
        el?.scrollIntoView();
    }""")
    await page.wait_for_timeout(1500)

    rows = await page.evaluate("""() => {
        const results = [];
        const heading = Array.from(document.querySelectorAll('*'))
            .find(el => el.childElementCount === 0 && el.innerText?.trim() === 'Concalls');
        if (!heading) return results;
        let c = heading.parentElement;
        for (let i = 0; i < 6; i++) {
            const dateEls = Array.from(c?.querySelectorAll('*') || []).filter(el =>
                /^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\\s+20\\d{2}$/.test(el.innerText?.trim())
            );
            if (dateEls.length) {
                dateEls.forEach(dateEl => {
                    let row = dateEl.parentElement;
                    for (let j = 0; j < 4; j++) {
                        const links = row?.querySelectorAll('a[href]');
                        if (links?.length) {
                            results.push({ date: dateEl.innerText.trim(),
                                files: Array.from(links).map(a => ({
                                    label: a.innerText.trim() || 'file', url: a.href }))
                            });
                            break;
                        }
                        row = row?.parentElement;
                    }
                });
                break;
            }
            c = c?.parentElement;
        }
        return results;
    }""")

    count = 0
    for row in rows:
        parsed = parse_month_year(row["date"])
        if not parsed:
            continue
        ry, rm = parsed
        if ry * 12 + rm < cutoff_y * 12 + cutoff_m:
            continue
        folder = dirs["concalls"] / f"{ry}_{rm:02d}_{safe_name(row['date'])}"
        folder.mkdir(exist_ok=True)
        print(f"    {row['date']}  ({len(row['files'])} files)")
        for f in row["files"]:
            label = safe_name(f["label"]) or "file"
            url   = f["url"]
            if label.lower() == "rec" or is_youtube_url(url) or url.lower().endswith(".mp3"):
                ok = await download_rec(url, folder / f"{label}.mp3", base_url, context)
            elif label.lower() == "ppt" or ".ppt" in url.lower():
                ok = await download_file(context, url, folder / f"{label}.pptx", base_url)
            else:
                ok = await download_file(context, url, folder / f"{label}.pdf", base_url)
            if ok: count += 1
    print(f"    {count} files downloaded" if count else "    None found")
    return count


# ─── SCRAPE ONE TICKER ────────────────────────────────────────────────────────
async def scrape_ticker(ticker: str, context):
    url = f"https://www.screener.in/company/{ticker}/consolidated/"
    dirs = make_dirs(ticker)
    valid_years = get_valid_fy_years()

    print(f"\n{'━'*48}")
    print(f"  {ticker}  →  {url}")
    print(f"{'━'*48}")

    page = await context.new_page()
    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
        title = await page.title()
        print(f"  Loaded: {title}\n")

        await page.evaluate("document.querySelector('#documents')?.scrollIntoView()")
        await page.wait_for_timeout(2000)

        x  = await download_excel(page, context, url, dirs, ticker)
        a  = await scrape_annual_reports(page, context, url, valid_years, dirs)
        r  = await scrape_credit_ratings(page, context, url, valid_years, dirs)
        c  = await scrape_concalls(page, context, url, dirs)

        print(f"\n  Done! Saved to: {dirs['root'].resolve()}")
        print(f"  Excel: {'✓' if x else '✗'}  |  Annual Reports: {a}  |  Ratings: {r}  |  Concalls: {c}")

    except Exception as e:
        print(f"  Error scraping {ticker}: {e}")
        import traceback; traceback.print_exc()
    finally:
        await page.close()


# ─── MAIN ────────────────────────────────────────────────────────────────────
async def main():
    print()
    print("  ╔══════════════════════════════════════════╗")
    print("  ║     Screener.in Document Scraper         ║")
    print("  ╚══════════════════════════════════════════╝")
    print()

    async with async_playwright() as p:
        # Get a logged-in browser context
        print("  Checking login status...")
        browser, context = await get_session_context(p)

        print()
        print("  Enter ticker symbols to scrape.")
        print("  Examples: GRWRHITECH   or   GRWRHITECH INFY TCS WIPRO")
        print("  Type 'quit' to exit.")
        print()

        while True:
            try:
                raw = input("  Tickers: ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not raw or raw.lower() in ("quit", "exit", "q"):
                break

            tickers = [t.upper().strip() for t in raw.split() if t.strip()]
            if not tickers:
                continue

            print(f"\n  Scraping {len(tickers)} ticker(s): {', '.join(tickers)}")

            for i, ticker in enumerate(tickers, 1):
                print(f"\n  [{i}/{len(tickers)}]", end="")
                await scrape_ticker(ticker, context)

            print(f"\n  All done! Files in: {BASE_DIR.resolve()}")
            print()
            print("  Enter more tickers, or type 'quit' to exit.")

        # Save updated cookies before closing
        updated = await context.cookies()
        save_session(updated)
        await browser.close()

    print("\n  Goodbye!")


if __name__ == "__main__":
    # Support both interactive mode and command-line args
    if len(sys.argv) > 1:
        # Command line: python web_scraper.py GRWRHITECH INFY
        async def cli_main():
            async with async_playwright() as p:
                print("\n  Checking login status...")
                browser, context = await get_session_context(p)
                tickers = [a.upper() for a in sys.argv[1:]]
                print(f"\n  Scraping: {', '.join(tickers)}\n")
                for i, ticker in enumerate(tickers, 1):
                    print(f"  [{i}/{len(tickers)}]", end="")
                    await scrape_ticker(ticker, context)
                updated = await context.cookies()
                save_session(updated)
                await browser.close()
                print(f"\n  Done! Files in: {BASE_DIR.resolve()}")
        asyncio.run(cli_main())
    else:
        asyncio.run(main())
