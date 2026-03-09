#!/usr/bin/env bash
# lib/sources.sh — Clone / update kernel and AnyKernel3 sources
# Sourced by build.sh — do not execute directly.

setup_sources() {
    log_step "Setting up sources"
    _sync_repo "$KERNEL_REPO"    "$KERNEL_DIR"    "msm-4.4"
    _sync_repo "$ANYKERNEL_REPO" "$ANYKERNEL_DIR" "AnyKernel3"
}

_sync_repo() {
    local url="$1" dest="$2" label="$3"

    if [[ -d "${dest}/.git" ]]; then
        # Valid git repo — fetch latest
        log_info "${label}: cache hit — fetching latest…"
        git -C "$dest" fetch --depth=1 origin 2>&1 \
            | tee -a "${LOGS_DIR}/sources.log" || log_warn "Fetch failed (offline?)"
        git -C "$dest" reset --hard FETCH_HEAD 2>&1 \
            | tee -a "${LOGS_DIR}/sources.log" || true
    else
        # Directory exists but is NOT a valid git repo (stale/broken cache) — wipe it
        if [[ -d "$dest" ]]; then
            log_warn "${label}: directory exists but is not a git repo — removing stale cache…"
            rm -rf "$dest"
        fi

        log "Cloning ${label} from ${url}…"
        git clone --depth=1 "$url" "$dest" 2>&1 \
            | tee -a "${LOGS_DIR}/sources.log" \
            || die "Failed to clone ${label}"
    fi

    local commit; commit=$(git -C "$dest" rev-parse --short HEAD 2>/dev/null || echo "unknown")
    log_ok "${label} @ ${commit}"
}
