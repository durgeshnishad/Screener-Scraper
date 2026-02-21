#!/bin/bash

# ── Auto-fix permissions on all scripts in this folder ───────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
chmod +x "$SCRIPT_DIR"/*.sh 2>/dev/null

clear
echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   Screener Scraper — Mac Setup           ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""
echo "  This will install everything needed."
echo "  It may ask for your Mac password once."
echo ""
read -p "  Press Enter to start..."
echo ""

# ── Xcode Command Line Tools ──────────────────────────────────────────────────
if ! xcode-select -p &>/dev/null; then
    echo "  [..] Installing Xcode tools (a popup will appear)..."
    xcode-select --install
    echo ""
    echo "  [!] Click 'Install' in the popup that appeared."
    echo "  [!] Wait for it to finish, then run this script again."
    echo ""
    read -p "  Press Enter to close..."
    exit 0
fi
echo "  [OK] Xcode tools"

# ── Homebrew ──────────────────────────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
    echo "  [..] Installing Homebrew..."
    NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add to PATH for both Apple Silicon and Intel
    if [[ -f "/opt/homebrew/bin/brew" ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    elif [[ -f "/usr/local/bin/brew" ]]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
fi
echo "  [OK] Homebrew"

# ── Python ────────────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null || ! python3 -c "import sys; assert sys.version_info >= (3,9)" 2>/dev/null; then
    echo "  [..] Installing Python..."
    brew install python
fi
echo "  [OK] $(python3 --version)"

# ── Node.js ───────────────────────────────────────────────────────────────────
if ! command -v node &>/dev/null; then
    echo "  [..] Installing Node.js (for YouTube downloads)..."
    brew install node
fi
echo "  [OK] Node.js $(node --version)"

# ── Python packages ───────────────────────────────────────────────────────────
echo "  [..] Installing Python packages..."
python3 -m pip install --upgrade pip --quiet --break-system-packages 2>/dev/null || python3 -m pip install --upgrade pip --quiet
python3 -m pip install playwright requests yt-dlp --quiet --break-system-packages 2>/dev/null || python3 -m pip install playwright requests yt-dlp --quiet
echo "  [OK] Python packages"

# ── Playwright browser ────────────────────────────────────────────────────────
echo "  [..] Installing browser (~150MB, may take a few minutes)..."
python3 -m playwright install chromium
echo "  [OK] Browser ready"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   Setup complete!                        ║"
echo "  ║   Double-click run_mac.command to start  ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""
read -p "  Press Enter to close..."
