#!/usr/bin/env bash
# lib/toolchain.sh — Toolchain cloning and export
# Sourced by build.sh — do not execute directly.

setup_toolchain() {
    log_step "Setting up toolchain: ${TOOLCHAIN}"
    case "$TOOLCHAIN" in
        gcc49)      _setup_gcc49      ;;
        gcc_latest) _setup_gcc_latest ;;
    esac
    log_ok "CROSS_COMPILE       = ${CROSS_COMPILE}"
    log_ok "CROSS_COMPILE_ARM32 = ${CROSS_COMPILE_ARM32}"
}

# ── Android GCC 4.9 ──────────────────────────────────────────────────────────
_setup_gcc49() {
    local TC64="${TOOLCHAIN_DIR}/aarch64-linux-android-4.9"
    local TC32="${TOOLCHAIN_DIR}/arm-linux-androideabi-4.9"

    _clone_shallow "$TC64_REPO" "$TC64" "aarch64-linux-android-4.9"
    _clone_shallow "$TC32_REPO" "$TC32" "arm-linux-androideabi-4.9"

    CROSS_COMPILE="${TC64}/bin/aarch64-linux-android-"
    CROSS_COMPILE_ARM32="${TC32}/bin/arm-linux-androideabi-"

    # Verify binaries exist
    [[ -x "${CROSS_COMPILE}gcc" ]] \
        || die "GCC 4.9 aarch64 binary not found at ${CROSS_COMPILE}gcc"
    [[ -x "${CROSS_COMPILE_ARM32}gcc" ]] \
        || die "GCC 4.9 arm binary not found at ${CROSS_COMPILE_ARM32}gcc"
}

# ── System / Linaro GCC (latest available from apt) ──────────────────────────
_setup_gcc_latest() {
    local missing=()
    command -v aarch64-linux-gnu-gcc   &>/dev/null || missing+=(gcc-aarch64-linux-gnu)
    command -v arm-linux-gnueabihf-gcc &>/dev/null || missing+=(gcc-arm-linux-gnueabihf)

    if [[ ${#missing[@]} -gt 0 ]]; then
        log "Installing system GCC cross-compilers: ${missing[*]}"
        sudo apt-get install -y -qq "${missing[@]}" 2>&1 \
            | tee -a "${LOGS_DIR}/toolchain.log" \
            || die "Failed to install GCC cross-compilers"
    fi

    CROSS_COMPILE="aarch64-linux-gnu-"
    CROSS_COMPILE_ARM32="arm-linux-gnueabihf-"

    # Report actual GCC version
    local ver; ver=$(aarch64-linux-gnu-gcc --version | head -1)
    log_info "GCC version: ${ver}"
}

# ── Helper: shallow-clone or fetch ───────────────────────────────────────────
_clone_shallow() {
    local url="$1" dest="$2" label="$3"
    if [[ -d "${dest}/.git" ]]; then
        log_info "${label}: already cloned — skipping"
    else
        log "Cloning ${label}…"
        git clone --depth=1 "$url" "$dest" 2>&1 \
            | tee -a "${LOGS_DIR}/toolchain.log" \
            || die "Failed to clone toolchain: ${label}"
        log_ok "${label} cloned"
    fi
}
