#!/usr/bin/env bash
# EAOS in one line:
#   curl -fsSL https://raw.githubusercontent.com/eom1417/engineering-audit-os/main/install.sh | bash
#
# Installs EAOS in ~/.eaos/app (its own Python environment, nothing global), puts the `eaos` command in
# ~/.local/bin, installs the checking tools, and says what to type next. Run it again to update.
# EAOS_SOURCE=<folder or git URL> installs from somewhere else; EAOS_SKIP_TOOLS=1 skips the tools.
set -eu

case "${EAOS_LANG:-${LANG:-}}" in ar*) AR=1 ;; *) AR= ;; esac
say() { if [ -n "$AR" ]; then printf '%s\n' "$1"; else printf '%s\n' "$2"; fi; }
line() { printf '%s\n' "────────────────────────────────────────────────────────────"; }
stop() { line; say "❌ ما حدث: $1" "❌ What happened: $2"; say "   $3" "   $4"; line; exit 1; }

SOURCE="${EAOS_SOURCE:-git+https://github.com/eom1417/engineering-audit-os@main}"
APP="${EAOS_APP:-$HOME/.eaos/app}"
BIN="$HOME/.local/bin"

say "أثبّت EAOS على جهازك. يأخذ هذا بضع دقائق." "Installing EAOS on your computer. This takes a few minutes."

LOG="$APP/install.log"
mkdir -p "$APP"; : > "$LOG"
command -v git >/dev/null 2>&1 || stop "لم أجد git." "I could not find git." \
  "على Mac اكتب: xcode-select --install  وعلى غيره ثبّته من https://git-scm.com/downloads ثم أعد تشغيل هذا السطر." \
  "On a Mac type: xcode-select --install  otherwise install it from https://git-scm.com/downloads, then run this line again."

# EAOS brings its own Python 3.12 through uv (a single file, no administrator rights, kept in ~/.eaos): the
# Python a computer happens to have (3.13, 3.14, or none) never decides whether EAOS installs.
say "   [1/3] أجهّز بيئة EAOS الخاصة…" "   [1/3] Preparing EAOS's own environment…"
UV="$(command -v uv || true)"
if [ -z "$UV" ]; then
  curl -LsSf https://astral.sh/uv/install.sh 2>>"$LOG" | env UV_INSTALL_DIR="$APP/uv" UV_NO_MODIFY_PATH=1 INSTALLER_NO_MODIFY_PATH=1 sh >>"$LOG" 2>&1 || true
  [ -x "$APP/uv/uv" ] && UV="$APP/uv/uv"
fi
rm -rf "$APP/venv"                # EAOS's own environment, made fresh: an earlier attempt may hold another Python
if [ -n "$UV" ]; then
  "$UV" venv --quiet --python 3.12 "$APP/venv" >>"$LOG" 2>&1 || UV=""
fi
if [ -z "$UV" ]; then             # no uv: the computer's own Python, the newest of the versions EAOS knows
  PY=""
  for candidate in python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
      PY="$candidate"; break
    fi
  done
  [ -n "$PY" ] || stop "لم أجد Python 3.10 أو أحدث، ولم أستطع تنزيله." "I found no Python 3.10 or newer, and could not download one." \
    "ثبّته من https://www.python.org/downloads/ ثم أعد تشغيل هذا السطر." "Install it from https://www.python.org/downloads/ then run this line again."
  "$PY" -m venv "$APP/venv" >>"$LOG" 2>&1 || stop "لم أستطع إنشاء بيئة Python." "I could not create a Python environment." \
    "على Ubuntu/Debian اكتب: sudo apt install python3-venv  ثم أعد تشغيل هذا السطر." "On Ubuntu/Debian type: sudo apt install python3-venv  then run this line again."
  "$APP/venv/bin/python" -m pip install --quiet --upgrade pip >>"$LOG" 2>&1
fi
pip_install() {
  if [ -n "$UV" ]; then "$UV" pip install --quiet --python "$APP/venv/bin/python" "$@" >>"$LOG" 2>&1
  else "$APP/venv/bin/python" -m pip install --quiet --upgrade "$@" >>"$LOG" 2>&1; fi
}

say "   [2/3] أنزّل EAOS…" "   [2/3] Downloading EAOS…"
case "$SOURCE" in
  git+*|http*) spec() { printf 'engineering-audit-os%s @ %s' "$1" "$SOURCE"; } ;;
  *) spec() { printf '%s%s' "$SOURCE" "$1"; } ;;
esac
if ! pip_install "$(spec '')"; then
  if ! curl -fsS -o /dev/null https://pypi.org/simple/ 2>/dev/null; then
    stop "لا يوجد اتصال بالإنترنت، وأحتاجه لتنزيل EAOS." "There is no internet connection, and I need it to download EAOS." \
      "تأكد من الاتصال ثم أعد تشغيل هذا السطر." "Check your connection, then run this line again."
  fi
  stop "فشل تثبيت EAOS لسبب غير الاتصال." "Installing EAOS failed, and not because of the connection." \
    "أرسل هذا الملف لمن يساعدك: $LOG" "Send this file to whoever helps you: $LOG"
fi
# The extras make EAOS stronger, not possible: one that has no build for this computer is a warning, never a stop.
MISSING=""
for extra in facts runtime live; do pip_install "$(spec "[$extra]")" || MISSING="$MISSING $extra"; done
mkdir -p "$BIN"
ln -sf "$APP/venv/bin/eaos" "$BIN/eaos"

case ":$PATH:" in
  *":$BIN:"*) ;;
  *) for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
       if [ -f "$rc" ] || [ "$rc" = "$HOME/.bashrc" ]; then
         grep -qs 'EAOS: the eaos command' "$rc" || printf '\n# EAOS: the eaos command\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$rc"
       fi
     done
     export PATH="$BIN:$PATH"
     NEW_TERMINAL=1 ;;
esac

if [ -z "${EAOS_SKIP_TOOLS:-}" ]; then
  say "   [3/3] أثبّت أدوات الفحص…" "   [3/3] Installing the checking tools…"
  "$APP/venv/bin/eaos" tools install --stage assessment >"$APP/tools-install.log" 2>&1 || \
    say "   ⚠️ بعض الأدوات لم تُثبّت. سيخبرك eaos doctor بما ينقص." "   ⚠️ Some tools did not install. eaos doctor will tell you what is missing."
fi

line
say "✅ ما حدث: تم تثبيت EAOS" "✅ What happened: EAOS is installed"
if [ -n "$MISSING" ]; then
  say "   ⚠️ أجزاء اختيارية لم تُثبّت على جهازك:$MISSING. يعمل EAOS بدونها، و eaos doctor يقول ما يتأثر." \
      "   ⚠️ Optional parts did not install on this computer:$MISSING. EAOS works without them; eaos doctor says what is affected."
fi
if [ -n "${NEW_TERMINAL:-}" ]; then
  say "   افتح نافذة طرفية جديدة أولًا، حتى يعرف جهازك الأمر eaos." "   Open a new terminal window first, so your computer knows the eaos command."
fi
say "⏭️  الخطوة التالية: افتح مجلد مشروعك في الطرفية، ثم انسخ والصق:" "⏭️  Next step: open your project folder in the terminal, then copy and paste:"
printf '   %s\n' "eaos start ."
line
