#!/usr/bin/env bash
# lib/logger.sh — Colored logging helpers
# Sourced by build.sh — do not execute directly.

# ── Colors ────────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
    CR='\033[0;31m' CG='\033[0;32m' CY='\033[1;33m'
    CB='\033[0;34m' CC='\033[0;36m' CW='\033[1;37m' CN='\033[0m'
else
    # No color when piped (CI logs)
    CR='' CG='' CY='' CB='' CC='' CW='' CN=''
fi

_ts() { date '+%H:%M:%S'; }

log()      { echo -e "${CW}[$(_ts)] $*${CN}"; }
log_ok()   { echo -e "${CG}[$(_ts)] ✔  $*${CN}"; }
log_err()  { echo -e "${CR}[$(_ts)] ✘  $*${CN}" >&2; }
log_warn() { echo -e "${CY}[$(_ts)] ⚠  $*${CN}"; }
log_info() { echo -e "${CC}[$(_ts)] ℹ  $*${CN}"; }
log_step() { echo -e "\n${CB}[$(_ts)] ──  $*  ──${CN}"; }
die()      { log_err "$*"; tg_send_message "❌ *BUILD FAILED*\n\`$*\`" 2>/dev/null || true; exit 1; }

print_banner() {
cat <<EOF

${CB}╔═══════════════════════════════════════════════════════════╗
║         SDM660 / X00T  Kernel Builder  v2.0               ║
║         github.com/xyzvoid/msm-4.4                        ║
╚═══════════════════════════════════════════════════════════╝${CN}

EOF
}

print_summary() {
    echo -e "\n${CG}╔═══════════════════════════════════════════════════════════╗${CN}"
    log_ok "Kernel  : ${KERNEL_VERSION}"
    log_ok "ZIP     : ${ZIP_NAME}"
    log_ok "Path    : ${ZIP_PATH}"
    log_ok "Time    : $(( BUILD_ELAPSED/60 ))m $(( BUILD_ELAPSED%60 ))s"
    [[ -n "${GH_RELEASE_URL:-}" ]] && log_ok "Release : ${GH_RELEASE_URL}"
    echo -e "${CG}╚═══════════════════════════════════════════════════════════╝${CN}\n"
}
