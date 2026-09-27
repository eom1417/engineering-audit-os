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

PY=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
    PY="$candidate"; break
  fi
done
[ -n "$PY" ] || stop "لم أجد Python 3.10 أو أحدث." "I could not find Python 3.10 or newer." \
  "ثبّته من https://www.python.org/downloads/ ثم أعد تشغيل هذا السطر." "Install it from https://www.python.org/downloads/ then run this line again."
command -v git >/dev/null 2>&1 || stop "لم أجد git." "I could not find git." \
  "ثبّته من https://git-scm.com/downloads ثم أعد تشغيل هذا السطر." "Install it from https://git-scm.com/downloads then run this line again."

say "   [1/3] أجهّز بيئة EAOS الخاصة…" "   [1/3] Preparing EAOS's own environment…"
mkdir -p "$APP"
"$PY" -m venv "$APP/venv" || stop "لم أستطع إنشاء بيئة Python." "I could not create a Python environment." \
  "على Ubuntu/Debian اكتب: sudo apt install python3-venv  ثم أعد تشغيل هذا السطر." "On Ubuntu/Debian type: sudo apt install python3-venv  then run this line again."
"$APP/venv/bin/python" -m pip install --quiet --upgrade pip >/dev/null

say "   [2/3] أنزّل EAOS…" "   [2/3] Downloading EAOS…"
case "$SOURCE" in
  git+*|http*) SPEC="engineering-audit-os[facts,runtime] @ $SOURCE" ;;
  *) SPEC="$SOURCE[facts,runtime]" ;;
esac
"$APP/venv/bin/python" -m pip install --quiet --upgrade "$SPEC" || stop "فشل تنزيل EAOS." "Downloading EAOS failed." \
  "تأكد من الاتصال بالإنترنت ثم أعد تشغيل هذا السطر." "Check your internet connection, then run this line again."
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
if [ -n "${NEW_TERMINAL:-}" ]; then
  say "   افتح نافذة طرفية جديدة أولًا، حتى يعرف جهازك الأمر eaos." "   Open a new terminal window first, so your computer knows the eaos command."
fi
say "⏭️  الخطوة التالية: افتح مجلد مشروعك في الطرفية، ثم انسخ والصق:" "⏭️  Next step: open your project folder in the terminal, then copy and paste:"
printf '   %s\n' "eaos start ."
line
