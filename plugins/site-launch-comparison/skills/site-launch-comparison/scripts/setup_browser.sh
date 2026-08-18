#!/usr/bin/env bash
# Install headless Chromium for the capture scripts.
#
# Handles three environments, because this skill runs in all of them:
#   macOS / Windows-WSL / any Linux with working sudo -> plain Playwright install
#   Linux sandbox without root (Claude Cowork, many CI images) -> unpack the
#     shared libraries Chromium links against into a local prefix by hand,
#     because `playwright install-deps` shells out to sudo and dies there
#
# Idempotent and self-verifying: it launches Chromium at the end and fails loudly
# rather than letting you discover the problem halfway through a capture run.
#
# Writes an env file you must source in every later shell:  /tmp/browser-env.sh

set -uo pipefail

PREFIX="${PREFIX:-/tmp/chromium-deps}"
ENV_FILE="${ENV_FILE:-/tmp/browser-env.sh}"
OS="$(uname -s)"

log() { printf '[setup] %s\n' "$*"; }

pipi() {
  python3 -m pip install "$@" -q 2>/dev/null \
    || python3 -m pip install "$@" --break-system-packages -q 2>&1 | tail -2
}

# ---------------------------------------------------------------- python deps
python3 -c "import playwright" 2>/dev/null || { log "installing playwright"; pipi playwright; }
python3 -c "import PIL"        2>/dev/null || { log "installing pillow";     pipi pillow; }

export PATH="$PATH:$HOME/.local/bin"
export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1

playwright_bin() {
  if command -v playwright >/dev/null 2>&1; then playwright "$@"; else python3 -m playwright "$@"; fi
}

# --------------------------------------------------------------- browser binary
log "installing chromium binary"
playwright_bin install chromium 2>&1 | tail -2

# --------------------------------------------------- platform-specific libraries
write_env() {
  {
    echo 'export PATH="$PATH:$HOME/.local/bin"'
    echo 'export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1'
    if [ -n "${1:-}" ]; then
      # Append rather than replace: clobbering an inherited LD_LIBRARY_PATH
      # breaks whatever else the caller's shell needed it for.
      echo "export LD_LIBRARY_PATH=\"$1\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}\""
      echo "export FONTCONFIG_PATH=\"${PREFIX}/root/etc/fonts\""
    fi
  } > "$ENV_FILE"
  log "wrote $ENV_FILE  (source it in every later shell)"
}

if [ "$OS" = "Darwin" ]; then
  log "macOS detected - Chromium ships with everything it needs"
  write_env ""

elif [ "$OS" = "Linux" ]; then
  # Does Chromium already run as-is? Cheapest possible check.
  if python3 - <<'PY' >/dev/null 2>&1
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); b.close()
PY
  then
    log "system libraries already sufficient"
    write_env ""
  elif sudo -n true 2>/dev/null; then
    log "sudo available - installing system dependencies"
    playwright_bin install-deps chromium 2>&1 | tail -3
    write_env ""
  elif command -v apt-get >/dev/null 2>&1; then
    if [ -d "$PREFIX/root" ] && [ -n "$(ls -A "$PREFIX/root" 2>/dev/null)" ]; then
      log "local library prefix already present at $PREFIX"
    else
      log "no root - unpacking chromium libraries into $PREFIX"
      mkdir -p "$PREFIX/debs" "$PREFIX/root"
      cd "$PREFIX/debs" || exit 1
      PKGS="libasound2 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 libcairo2 libcups2 \
libdbus-1-3 libdrm2 libgbm1 libglib2.0-0 libnspr4 libnss3 libpango-1.0-0 \
libpangocairo-1.0-0 libx11-6 libxcb1 libxcomposite1 libxdamage1 libxext6 \
libxfixes3 libxkbcommon0 libxrandr1 libexpat1 libxshmfence1 libxcursor1 \
libxi6 libxtst6 libepoxy0 libharfbuzz0b libfreetype6 libfontconfig1 \
fonts-liberation fonts-noto-color-emoji"
      DEPS=$(apt-cache depends --recurse --no-recommends --no-suggests --no-conflicts \
        --no-breaks --no-replaces --no-enhances $PKGS 2>/dev/null | grep "^\w" | sort -u)
      apt-get download $DEPS 2>&1 | tail -1
      # Without this the loop runs once with f set to the literal "*.deb",
      # dpkg-deb's error is swallowed by 2>/dev/null, and the failure only
      # surfaces later at verification where the cause is no longer visible.
      shopt -s nullglob
      debs=(*.deb)
      shopt -u nullglob
      if [ "${#debs[@]}" -eq 0 ]; then
        log "ERROR: apt-get downloaded no packages — cannot build a local library"
        log "       prefix. Check network access and apt sources, then re-run."
        exit 1
      fi
      for f in "${debs[@]}"; do dpkg-deb -x "$f" "$PREFIX/root/" 2>/dev/null; done
      log "unpacked ${#debs[@]} packages"
    fi
    # Empty elements in LD_LIBRARY_PATH mean "the current directory" to the
    # dynamic loader, so drop any candidate that didn't resolve instead of
    # leaving a "::" behind.
    LIB_DIRS=()
    for d in "$PREFIX"/root/usr/lib/*-linux-gnu "$PREFIX"/root/lib/*-linux-gnu "$PREFIX/root/usr/lib"; do
      [ -d "$d" ] && LIB_DIRS+=("$d")
    done
    if [ "${#LIB_DIRS[@]}" -eq 0 ]; then
      log "WARNING: no unpacked library directories found under $PREFIX"
      write_env ""
    else
      write_env "$(IFS=:; echo "${LIB_DIRS[*]}")"
    fi
  else
    log "WARNING: no root and no apt-get. If Chromium fails to launch, install"
    log "         its dependencies with your distro's package manager."
    write_env ""
  fi
else
  log "unrecognised platform $OS - trying a plain install"
  write_env ""
fi

# ------------------------------------------------------------------- verify
# shellcheck source=/dev/null
source "$ENV_FILE"
python3 - <<'PY'
from playwright.sync_api import sync_playwright
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.set_content("<h1>ok</h1>")
        assert pg.inner_text("h1") == "ok"
        b.close()
    print("[setup] chromium launches correctly")
except Exception as e:
    print(f"[setup] FAILED: {type(e).__name__}: {str(e)[:400]}")
    raise SystemExit(1)
PY
