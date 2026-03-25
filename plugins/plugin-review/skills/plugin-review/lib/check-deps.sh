#!/usr/bin/env bash
#
# check-deps.sh — Verify and install dependencies for the plugin-review skill
#
# Usage: ./check-deps.sh [--install]
# Exit codes: 0 = all deps ready, 1 = install failed or user declined

set -euo pipefail

AUTO_INSTALL=false
if [[ "${1:-}" == "--install" ]]; then
    AUTO_INSTALL=true
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }

MISSING=()

echo "Checking dependencies..."
echo ""

# --- curl (should be pre-installed) ---
if command -v curl &>/dev/null; then
    ok "curl $(curl --version | head -1 | awk '{print $2}')"
else
    fail "curl not found"
    MISSING+=("curl")
fi

# --- unzip (should be pre-installed) ---
if command -v unzip &>/dev/null; then
    ok "unzip"
else
    fail "unzip not found"
    MISSING+=("unzip")
fi

# --- jq ---
if command -v jq &>/dev/null; then
    ok "jq $(jq --version 2>&1 | sed 's/jq-//')"
else
    warn "jq not found — needed for JSON parsing"
    MISSING+=("jq")
fi

# --- PHP ---
if command -v php &>/dev/null; then
    ok "php $(php -v | head -1 | awk '{print $2}')"
else
    warn "php not found — needed for PHPCS"
    MISSING+=("php")
fi

# --- Composer ---
COMPOSER_CMD=""
if command -v composer &>/dev/null; then
    COMPOSER_CMD="composer"
    ok "composer"
elif [ -f "$HOME/.composer/composer.phar" ]; then
    COMPOSER_CMD="php $HOME/.composer/composer.phar"
    ok "composer (via composer.phar)"
else
    warn "composer not found — needed to install PHPCS"
    MISSING+=("composer")
fi

# --- PHPCS ---
PHPCS_CMD=""
if command -v phpcs &>/dev/null; then
    PHPCS_CMD="phpcs"
elif [ -f "$HOME/.composer/vendor/bin/phpcs" ]; then
    PHPCS_CMD="$HOME/.composer/vendor/bin/phpcs"
elif [ -f "$HOME/.config/composer/vendor/bin/phpcs" ]; then
    PHPCS_CMD="$HOME/.config/composer/vendor/bin/phpcs"
fi

if [ -n "$PHPCS_CMD" ]; then
    ok "phpcs $($PHPCS_CMD --version 2>&1 | awk '{print $3}')"
else
    warn "phpcs not found — needed for static analysis"
    MISSING+=("phpcs")
fi

# --- WordPress PHPCS Standards ---
if [ -n "$PHPCS_CMD" ]; then
    if $PHPCS_CMD -i 2>/dev/null | grep -q "WordPress"; then
        ok "WordPress PHPCS standards installed"
    else
        warn "WordPress PHPCS standards not found"
        MISSING+=("wpcs")
    fi
fi

echo ""

# --- Install missing dependencies ---
if [ ${#MISSING[@]} -eq 0 ]; then
    echo -e "${GREEN}All dependencies are installed.${NC}"
    exit 0
fi

echo -e "${YELLOW}Missing dependencies: ${MISSING[*]}${NC}"
echo ""

# Check for Homebrew (macOS)
HAS_BREW=false
if command -v brew &>/dev/null; then
    HAS_BREW=true
fi

# Check for apt (Linux)
HAS_APT=false
if command -v apt-get &>/dev/null; then
    HAS_APT=true
fi

if $AUTO_INSTALL; then
    echo "Auto-installing missing dependencies (--install flag)..."
elif [ -t 0 ]; then
    echo "Would you like to install missing dependencies? [y/N]"
    read -r REPLY
    if [[ ! "$REPLY" =~ ^[Yy]$ ]]; then
        fail "Installation declined. The skill requires: ${MISSING[*]}"
        exit 1
    fi
else
    fail "Missing dependencies: ${MISSING[*]}"
    echo "Run with --install flag to auto-install, or install manually:"
    for dep in "${MISSING[@]}"; do
        case "$dep" in
            curl|unzip|jq|php) echo "  brew install $dep  (or apt-get install $dep)" ;;
            composer) echo "  brew install composer" ;;
            phpcs) echo "  composer global require squizlabs/php_codesniffer" ;;
            wpcs) echo "  composer global require wp-coding-standards/wpcs dealerdirect/phpcodesniffer-composer-installer" ;;
        esac
    done
    exit 1
fi

echo ""
echo "Installing missing dependencies..."
echo ""

for dep in "${MISSING[@]}"; do
    case "$dep" in
        curl|unzip|jq|php)
            if $HAS_BREW; then
                echo "  → brew install $dep"
                brew install "$dep"
            elif $HAS_APT; then
                echo "  → sudo apt-get install -y $dep"
                sudo apt-get install -y "$dep"
            else
                fail "No package manager found. Please install $dep manually."
                exit 1
            fi
            ;;
        composer)
            if $HAS_BREW; then
                echo "  → brew install composer"
                brew install composer
                COMPOSER_CMD="composer"
            else
                echo "  → Installing composer to ~/.composer/"
                curl -sS https://getcomposer.org/installer | php -- --install-dir="$HOME/.composer" --filename=composer.phar
                COMPOSER_CMD="php $HOME/.composer/composer.phar"
            fi
            ;;
        phpcs)
            if [ -z "$COMPOSER_CMD" ]; then
                fail "Cannot install phpcs without composer"
                exit 1
            fi
            echo "  → $COMPOSER_CMD global require squizlabs/php_codesniffer"
            $COMPOSER_CMD global require squizlabs/php_codesniffer
            # Find the newly installed phpcs
            if [ -f "$HOME/.composer/vendor/bin/phpcs" ]; then
                PHPCS_CMD="$HOME/.composer/vendor/bin/phpcs"
            elif [ -f "$HOME/.config/composer/vendor/bin/phpcs" ]; then
                PHPCS_CMD="$HOME/.config/composer/vendor/bin/phpcs"
            fi
            ;;
        wpcs)
            if [ -z "$COMPOSER_CMD" ]; then
                fail "Cannot install WordPress standards without composer"
                exit 1
            fi
            echo "  → $COMPOSER_CMD global require wp-coding-standards/wpcs dealerdirect/phpcodesniffer-composer-installer"
            $COMPOSER_CMD global require wp-coding-standards/wpcs dealerdirect/phpcodesniffer-composer-installer
            ;;
    esac
done

echo ""

# Verify everything is now available
STILL_MISSING=false

command -v curl &>/dev/null    || { fail "curl still missing"; STILL_MISSING=true; }
command -v unzip &>/dev/null   || { fail "unzip still missing"; STILL_MISSING=true; }
command -v jq &>/dev/null      || { fail "jq still missing"; STILL_MISSING=true; }
command -v php &>/dev/null     || { fail "php still missing"; STILL_MISSING=true; }

# Re-check PHPCS
if [ -z "$PHPCS_CMD" ]; then
    if command -v phpcs &>/dev/null; then
        PHPCS_CMD="phpcs"
    elif [ -f "$HOME/.composer/vendor/bin/phpcs" ]; then
        PHPCS_CMD="$HOME/.composer/vendor/bin/phpcs"
    elif [ -f "$HOME/.config/composer/vendor/bin/phpcs" ]; then
        PHPCS_CMD="$HOME/.config/composer/vendor/bin/phpcs"
    fi
fi

if [ -z "$PHPCS_CMD" ]; then
    fail "phpcs still missing"
    STILL_MISSING=true
elif ! $PHPCS_CMD -i 2>/dev/null | grep -q "WordPress"; then
    fail "WordPress PHPCS standards still missing"
    STILL_MISSING=true
fi

if $STILL_MISSING; then
    fail "Some dependencies could not be installed. See errors above."
    exit 1
fi

echo -e "${GREEN}All dependencies are now installed.${NC}"
exit 0
