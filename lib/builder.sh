#!/usr/bin/env bash
# lib/builder.sh — Kernel compilation logic
# Sourced by build.sh — do not execute directly.

# Populated by run_build() / resolve_version_strings():
KERNEL_IMAGE=""
BUILD_LOG=""
BUILD_ELAPSED=0
KERNEL_VERSION=""
DATETIME=""
ZIP_NAME=""

# ── Make flag array ───────────────────────────────────────────────────────────
# Using a bash array avoids word-splitting pitfalls when any value contains
# spaces (unlikely for toolchain paths, but defensive).
_make_flags() {
    MAKE_FLAGS=(
        -C "$KERNEL_DIR"
        O="$OUT_DIR"
        ARCH="$ARCH"
        CROSS_COMPILE="$CROSS_COMPILE"
        CROSS_COMPILE_ARM32="$CROSS_COMPILE_ARM32"
        -j"$JOBS"
    )
}

# ── Clean targets ─────────────────────────────────────────────────────────────
run_clean() {
    log_step "Running: make clean"
    _make_flags
    make "${MAKE_FLAGS[@]}" clean 2>&1 | tee -a "${LOGS_DIR}/clean.log" || true
    log_ok "Clean done"
}

run_mrproper() {
    log_step "Running: make mrproper"
    _make_flags
    make "${MAKE_FLAGS[@]}" mrproper 2>&1 | tee -a "${LOGS_DIR}/clean.log" || true
    log_ok "mrproper done"
}

# ── Resolve version strings ───────────────────────────────────────────────────
resolve_version_strings() {
    KERNEL_VERSION=$(make -C "$KERNEL_DIR" O="$OUT_DIR" \
        ARCH="$ARCH" CROSS_COMPILE="$CROSS_COMPILE" \
        kernelversion 2>/dev/null \
        | grep -v "^make" | head -1 | tr -d '[:space:]')
    KERNEL_VERSION="${KERNEL_VERSION:-unknown}"
    DATETIME=$(date '+%Y%m%d_%H%M%S')
    ZIP_NAME="${KERNEL_NAME}-${KERNEL_VERSION}-${DATETIME}.zip"
}

# ── Post-defconfig .config patching ──────────────────────────────────────────
# CONFIG_BUILD_ARM64_DT_OVERLAY=y injects dtbo.img into the 'all' target.
# CAF 4.4 on a plain Ubuntu host has no mkdtimg, so we disable it after
# running defconfig — plain `make` can then proceed without a target override.
_patch_config() {
    local cfg="${OUT_DIR}/.config"
    [[ -f "$cfg" ]] || return 0

    if grep -q "^CONFIG_BUILD_ARM64_DT_OVERLAY=y" "$cfg"; then
        log_warn "Disabling CONFIG_BUILD_ARM64_DT_OVERLAY (no mkdtimg on host)"
        sed -i \
            's/^CONFIG_BUILD_ARM64_DT_OVERLAY=y/# CONFIG_BUILD_ARM64_DT_OVERLAY is not set/' \
            "$cfg"
    fi
}

# ── Full build ────────────────────────────────────────────────────────────────
run_build() {
    log_step "Building kernel (defconfig: ${DEFCONFIG})"

    BUILD_LOG="${LOGS_DIR}/build_$(date '+%Y%m%d_%H%M%S').log"
    local start; start=$(date +%s)

    mkdir -p "$OUT_DIR"
    _make_flags   # populate MAKE_FLAGS array

    # 1. Generate .config from defconfig
    log "Generating .config from ${DEFCONFIG}…"
    make "${MAKE_FLAGS[@]}" "$DEFCONFIG" 2>&1 | tee "$BUILD_LOG" \
        || die "defconfig step failed — see ${BUILD_LOG}"

    # 2. Patch .config (remove broken dtbo.img dependency)
    _patch_config

    # 3. Resolve version + zip name now that .config exists
    resolve_version_strings
    log_info "Kernel version : ${KERNEL_VERSION}"
    log_info "Output zip     : ${ZIP_NAME}"

    tg_send_or_edit "🔨 *Build in Progress*
━━━━━━━━━━━━━━━━━━━
📦 Version  : \`${KERNEL_VERSION}\`
🔧 Defconfig: \`${DEFCONFIG}\`
⚙️ Toolchain: \`${TOOLCHAIN}\`
🧵 Jobs     : \`${JOBS}\`
🕐 Started  : \`$(date '+%Y-%m-%d %H:%M:%S')\`
━━━━━━━━━━━━━━━━━━━
_Compiling… please wait ⏳_"

    # 4. Full build — plain make, no explicit target
    log "Compiling…"
    if ! make "${MAKE_FLAGS[@]}" 2>&1 | tee -a "$BUILD_LOG"; then
        local elapsed=$(( $(date +%s) - start ))
        BUILD_ELAPSED=$elapsed
        tg_send_or_edit "❌ *Build FAILED* after $(( elapsed/60 ))m $(( elapsed%60 ))s"
        tg_upload_log "$BUILD_LOG" "Error log — ${ZIP_NAME}"
        die "Kernel build failed — see ${BUILD_LOG}"
    fi

    BUILD_ELAPSED=$(( $(date +%s) - start ))
    log_ok "Build finished in $(( BUILD_ELAPSED/60 ))m $(( BUILD_ELAPSED%60 ))s"

    # 5. Locate the kernel image (preference: dtb-appended > gz > plain)
    local img_dtb="${OUT_DIR}/arch/${ARCH}/boot/Image.gz-dtb"
    local img_gz="${OUT_DIR}/arch/${ARCH}/boot/Image.gz"
    local img_plain="${OUT_DIR}/arch/${ARCH}/boot/Image"

    if   [[ -f "$img_dtb"   ]]; then KERNEL_IMAGE="$img_dtb"
    elif [[ -f "$img_gz"    ]]; then KERNEL_IMAGE="$img_gz";    log_warn "Using Image.gz (no appended dtb)"
    elif [[ -f "$img_plain" ]]; then KERNEL_IMAGE="$img_plain"; log_warn "Using plain Image"
    else die "No kernel image found in ${OUT_DIR}/arch/${ARCH}/boot/"; fi

    log_ok "Kernel image : ${KERNEL_IMAGE}  ($(du -sh "$KERNEL_IMAGE" | cut -f1))"
}
