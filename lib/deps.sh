#!/usr/bin/env bash
# lib/deps.sh — Build dependency checker and installer
# Sourced by build.sh — do not execute directly.

# Packages required on Ubuntu/Debian hosts
_REQUIRED_PKGS=(
    git make curl zip bc bison flex
    libssl-dev libelf-dev
    python3 python3-pip
    device-tree-compiler
    ccache
    binutils
    gcc g++
    cpio
    kmod
)

check_deps() {
    log_step "Checking build dependencies"

    local missing=()
    for pkg in "${_REQUIRED_PKGS[@]}"; do
        dpkg -s "$pkg" &>/dev/null 2>&1 || missing+=("$pkg")
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_warn "Missing packages: ${missing[*]}"
        log "Installing…"

        sudo apt-get update -qq 2>&1 | tee -a "${LOGS_DIR}/deps.log"
        sudo apt-get install -y -qq "${missing[@]}" 2>&1 | tee -a "${LOGS_DIR}/deps.log" \
            || die "Failed to install dependencies"

        log_ok "Dependencies installed"
    else
        log_ok "All dependencies satisfied"
    fi

    # Runtime tool checks (always)
    for cmd in git make curl zip python3 bc; do
        command -v "$cmd" &>/dev/null || die "Required command not found: ${cmd}"
    done
}
