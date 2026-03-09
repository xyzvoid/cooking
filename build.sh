#!/usr/bin/env bash
# =============================================================================
#  build.sh — Entry point for SDM660 / X00T Kernel Builder
#  Usage: ./build.sh [OPTIONS]
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Load modules ──────────────────────────────────────────────────────────────
source "${SCRIPT_DIR}/lib/logger.sh"
source "${SCRIPT_DIR}/lib/args.sh"
source "${SCRIPT_DIR}/lib/config.sh"
source "${SCRIPT_DIR}/lib/deps.sh"
source "${SCRIPT_DIR}/lib/toolchain.sh"
source "${SCRIPT_DIR}/lib/sources.sh"
source "${SCRIPT_DIR}/lib/builder.sh"
source "${SCRIPT_DIR}/lib/package.sh"
source "${SCRIPT_DIR}/lib/telegram.sh"
source "${SCRIPT_DIR}/lib/github.sh"

# ── Parse args + load config ─────────────────────────────────────────────────
parse_args "$@"
load_config "${SCRIPT_DIR}/config/build.conf"

# ── Banner ────────────────────────────────────────────────────────────────────
print_banner

# ── Pre-flight ────────────────────────────────────────────────────────────────
check_deps
setup_toolchain
setup_sources

# ── Optional clean ────────────────────────────────────────────────────────────
[[ "${OPT_MRPROPER:-false}" == true ]] && run_mrproper
[[ "${OPT_CLEAN:-false}"    == true ]] && run_clean

# ── Build or zip-only ────────────────────────────────────────────────────────
if [[ -n "${OPT_ZIP_ONLY:-}" ]]; then
    log_info "Zip-only mode — skipping build"
    [[ -f "$OPT_ZIP_ONLY" ]] || die "Image not found: ${OPT_ZIP_ONLY}"
    KERNEL_IMAGE="$OPT_ZIP_ONLY"
    BUILD_LOG="/dev/null"
    BUILD_ELAPSED=0
    resolve_version_strings
else
    tg_notify_start
    run_build          # sets KERNEL_IMAGE BUILD_LOG BUILD_ELAPSED
fi

# ── Package ───────────────────────────────────────────────────────────────────
create_zip            # sets ZIP_PATH

# ── Upload & Release ─────────────────────────────────────────────────────────
[[ "${OPT_NO_UPLOAD:-false}"  == false ]] && tg_upload_artifacts
[[ "${OPT_NO_GITHUB:-false}"  == false ]] && gh_create_release

# ── Final summary ─────────────────────────────────────────────────────────────
tg_notify_done
print_summary
