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
_make_flags() {
    MAKE_FLAGS=(
        -C "$KERNEL_DIR"
        O="$OUT_DIR"
        ARCH="$ARCH"
        CROSS_COMPILE="$CROSS_COMPILE"
        CROSS_COMPILE_ARM32="$CROSS_COMPILE_ARM32"
        -j"$JOBS"
        DTC=dtc
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

# ── Full build ────────────────────────────────────────────────────────────────
run_build() {
    log_step "Building kernel (defconfig: ${DEFCONFIG})"

    BUILD_LOG="${LOGS_DIR}/build_$(date '+%Y%m%d_%H%M%S').log"
    local start; start=$(date +%s)

    mkdir -p "$OUT_DIR"
    _make_flags

    # 1. Generate .config from defconfig
    log "Generating .config from ${DEFCONFIG}…"
    make "${MAKE_FLAGS[@]}" "$DEFCONFIG" 2>&1 | tee "$BUILD_LOG" \
        || die "defconfig step failed — see ${BUILD_LOG}"

    # 2. Resolve version + zip name
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

    # 3. Build — target Image.gz-dtb directly; skips dtbo.img entirely
    log "Compiling…"
    if ! make "${MAKE_FLAGS[@]}" Image.gz-dtb 2>&1 | tee -a "$BUILD_LOG"; then
        local elapsed=$(( $(date +%s) - start ))
        BUILD_ELAPSED=$elapsed
        tg_send_or_edit "❌ *Build FAILED* after $(( elapsed/60 ))m $(( elapsed%60 ))s"
        tg_upload_log "$BUILD_LOG" "Error log — ${ZIP_NAME}"
        die "Kernel build failed — see ${BUILD_LOG}"
    fi

    BUILD_ELAPSED=$(( $(date +%s) - start ))
    log_ok "Build finished in $(( BUILD_ELAPSED/60 ))m $(( BUILD_ELAPSED%60 ))s"

    # 4. Locate kernel image (preference: dtb-appended > gz > plain)
    local img_dtb="${OUT_DIR}/arch/${ARCH}/boot/Image.gz-dtb"
    local img_gz="${OUT_DIR}/arch/${ARCH}/boot/Image.gz"
    local img_plain="${OUT_DIR}/arch/${ARCH}/boot/Image"

    if   [[ -f "$img_dtb"   ]]; then KERNEL_IMAGE="$img_dtb"
    elif [[ -f "$img_gz"    ]]; then KERNEL_IMAGE="$img_gz";    log_warn "Using Image.gz (no appended dtb)"
    elif [[ -f "$img_plain" ]]; then KERNEL_IMAGE="$img_plain"; log_warn "Using plain Image"
    else die "No kernel image found in ${OUT_DIR}/arch/${ARCH}/boot/"; fi

    log_ok "Kernel image : ${KERNEL_IMAGE}  ($(du -sh "$KERNEL_IMAGE" | cut -f1))"
}
