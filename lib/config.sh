#!/usr/bin/env bash
# lib/config.sh — Load build.conf and resolve all path variables
# Sourced by build.sh — do not execute directly.

load_config() {
    local conf_file="$1"

    # ── Save CLI-supplied values before sourcing conf ─────────────────────────
    # parse_args already set TOOLCHAIN/DEFCONFIG/JOBS from CLI flags.
    # We save them here so build.conf cannot override explicit CLI choices.
    local _cli_toolchain="${TOOLCHAIN:-}"
    local _cli_defconfig="${DEFCONFIG:-}"
    local _cli_jobs="${JOBS:-}"

    # ── Source the conf file ──────────────────────────────────────────────────
    if [[ -f "$conf_file" ]]; then
        # shellcheck disable=SC1090
        source "$conf_file"
        log_ok "Loaded config: ${conf_file}"
    else
        log_warn "Config file not found: ${conf_file} — using defaults"
    fi

    # ── Re-apply CLI values (CLI always wins over conf file) ─────────────────
    [[ -n "$_cli_toolchain" ]] && TOOLCHAIN="$_cli_toolchain"
    [[ -n "$_cli_defconfig" ]] && DEFCONFIG="$_cli_defconfig"
    [[ -n "$_cli_jobs"      ]] && JOBS="$_cli_jobs"

    # ── Re-apply --no-telegram (in case conf file restored the tokens) ────────
    if [[ "${OPT_NO_TELEGRAM:-false}" == true ]]; then
        TG_BOT_TOKEN=""
        TG_CHAT_ID=""
    fi

    # ── Secrets (from env or conf; never overwrite if already set) ────────────
    TG_BOT_TOKEN="${TG_BOT_TOKEN:-}"
    TG_CHAT_ID="${TG_CHAT_ID:-}"
    GH_TOKEN="${GH_TOKEN:-}"

    # ── Build identity ────────────────────────────────────────────────────────
    KERNEL_NAME="${KERNEL_NAME:-xyzvoid}"
    ARCH="${ARCH:-arm64}"
    DEFCONFIG="${DEFCONFIG:-X00T_defconfig}"
    TOOLCHAIN="${TOOLCHAIN:-gcc49}"
    JOBS="${JOBS:-$(nproc --all)}"

    # ── Repository URLs ───────────────────────────────────────────────────────
    KERNEL_REPO="${KERNEL_REPO:-https://github.com/xyzvoid/msm-4.4.git}"
    ANYKERNEL_REPO="${ANYKERNEL_REPO:-https://github.com/xyzvoid/AnyKernel3.git}"
    GH_RELEASE_REPO="${GH_RELEASE_REPO:-xyzvoid/msm-4.4}"
    GH_RELEASE_BRANCH="${GH_RELEASE_BRANCH:-android-4.4}"

    # ── Toolchain repos (gcc49) ───────────────────────────────────────────────
    TC64_REPO="${TC64_REPO:-https://github.com/LineageOS/android_prebuilts_gcc_linux-x86_aarch64_aarch64-linux-android-4.9}"
    TC32_REPO="${TC32_REPO:-https://github.com/LineageOS/android_prebuilts_gcc_linux-x86_arm_arm-linux-androideabi-4.9}"

    # ── Directory layout ──────────────────────────────────────────────────────
    BUILD_ROOT="${BUILD_ROOT:-$(pwd)/build}"
    KERNEL_DIR="${BUILD_ROOT}/msm-4.4"
    ANYKERNEL_DIR="${BUILD_ROOT}/AnyKernel3"
    TOOLCHAIN_DIR="${BUILD_ROOT}/toolchains"
    OUT_DIR="${KERNEL_DIR}/out"
    LOGS_DIR="${BUILD_ROOT}/logs"
    ZIP_DIR="${BUILD_ROOT}/zips"

    # Only pre-create dirs that must exist before git clone runs.
    # Do NOT pre-create KERNEL_DIR or ANYKERNEL_DIR — git clone creates them,
    # and pre-creating empty dirs would cause sources.sh to log "stale cache"
    # on every fresh run and pointlessly rm -rf + reclone.
    mkdir -p "$TOOLCHAIN_DIR" "$LOGS_DIR" "$ZIP_DIR"

    log_info "Build root : ${BUILD_ROOT}"
    log_info "Arch       : ${ARCH}"
    log_info "Defconfig  : ${DEFCONFIG}"
    log_info "Toolchain  : ${TOOLCHAIN}"
    log_info "Jobs       : ${JOBS}"
}
