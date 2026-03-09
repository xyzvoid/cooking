#!/usr/bin/env bash
# lib/builder.sh — Kernel compilation logic
# Sourced by build.sh — do not execute directly.

# Populated by run_build():
KERNEL_IMAGE=""
BUILD_LOG=""
BUILD_ELAPSED=0
KERNEL_VERSION=""
DATETIME=""
ZIP_NAME=""

# ── Common make flags array ───────────────────────────────────────────────────
_make_flags() {
    echo -C "$KERNEL_DIR" \
         O="$OUT_DIR" \
         ARCH="$ARCH" \
         CROSS_COMPILE="$CROSS_COMPILE" \
         CROSS_COMPILE_ARM32="$CROSS_COMPILE_ARM32" \
         -j"$JOBS"
}

# ── Clean targets ─────────────────────────────────────────────────────────────
run_clean() {
    log_step "Running: make clean"
    # shellcheck disable=SC2046
    make $(_make_flags) clean 2>&1 | tee -a "${LOGS_DIR}/clean.log" || true
    log_ok "Clean done"
}

run_mrproper() {
    log_step "Running: make mrproper"
    # shellcheck disable=SC2046
    make $(_make_flags) mrproper 2>&1 | tee -a "${LOGS_DIR}/clean.log" || true
    log_ok "mrproper done"
}

# ── Resolve version strings (used by zip-only mode too) ──────────────────────
resolve_version_strings() {
    KERNEL_VERSION=$(make -C "$KERNEL_DIR" O="$OUT_DIR" \
        ARCH="$ARCH" CROSS_COMPILE="$CROSS_COMPILE" \
        kernelversion 2>/dev/null | grep -v "^make" | head -1 | tr -d '[:space:]')
    KERNEL_VERSION="${KERNEL_VERSION:-unknown}"
    DATETIME=$(date '+%Y%m%d_%H%M%S')
    ZIP_NAME="${KERNEL_NAME}-${KERNEL_VERSION}-${DATETIME}.zip"
}

# ── Detect the best explicit build target for this defconfig ─────────────────
# CAF 4.4 kernels with CONFIG_BUILD_ARM64_DT_OVERLAY=y add dtbo.img as a
# dependency of 'all', but the host build system has no rule to produce it.
# Building Image.gz-dtb (or Image.gz) explicitly bypasses that broken target.
_get_build_target() {
    local cfg="${OUT_DIR}/.config"
    # If .config already exists from the defconfig step, inspect it;
    # otherwise fall back to Image.gz-dtb which is safe for X00T.
    if [[ -f "$cfg" ]] && grep -q "^CONFIG_BUILD_ARM64_DT_OVERLAY=y" "$cfg" 2>/dev/null; then
        log_warn "CONFIG_BUILD_ARM64_DT_OVERLAY=y detected — targeting Image.gz-dtb to skip dtbo.img"
        echo "Image.gz-dtb"
    else
        # Default: build everything; falls back to Image.gz-dtb on failure
        echo "Image.gz-dtb"
    fi
}

# ── Full build ────────────────────────────────────────────────────────────────
run_build() {
    log_step "Building kernel (defconfig: ${DEFCONFIG})"

    BUILD_LOG="${LOGS_DIR}/build_$(date '+%Y%m%d_%H%M%S').log"
    local start; start=$(date +%s)

    mkdir -p "$OUT_DIR"

    # defconfig
    log "Generating .config from ${DEFCONFIG}…"
    # shellcheck disable=SC2046
    make $(_make_flags) "$DEFCONFIG" 2>&1 | tee "$BUILD_LOG" \
        || die "defconfig step failed — see ${BUILD_LOG}"

    # Resolve version now (after defconfig so OUT_DIR/include exists)
    resolve_version_strings

    # Pick explicit build target (avoids broken dtbo.img rule in CAF 4.4)
    local build_target; build_target=$(_get_build_target)

    log_info "Kernel version : ${KERNEL_VERSION}"
    log_info "Output zip     : ${ZIP_NAME}"
    log_info "Build target   : ${build_target}"

    tg_send_or_edit "🔨 *Build in Progress*
━━━━━━━━━━━━━━━━━━━
📦 Version  : \`${KERNEL_VERSION}\`
🔧 Defconfig: \`${DEFCONFIG}\`
⚙️ Toolchain: \`${TOOLCHAIN}\`
🧵 Jobs     : \`${JOBS}\`
🎯 Target   : \`${build_target}\`
🕐 Started  : \`$(date '+%Y-%m-%d %H:%M:%S')\`
━━━━━━━━━━━━━━━━━━━
_Compiling… please wait ⏳_"

    # Full build — explicit target bypasses the dtbo.img dependency
    log "Compiling (target: ${build_target})…"
    # shellcheck disable=SC2046
    if ! make $(_make_flags) "$build_target" 2>&1 | tee -a "$BUILD_LOG"; then
        local end; end=$(date +%s)
        BUILD_ELAPSED=$(( end - start ))
        tg_send_or_edit "❌ *Build FAILED* after $(( BUILD_ELAPSED/60 ))m $(( BUILD_ELAPSED%60 ))s"
        tg_upload_log "$BUILD_LOG" "Error log — ${ZIP_NAME}"
        die "Kernel build failed — see ${BUILD_LOG}"
    fi

    local end; end=$(date +%s)
    BUILD_ELAPSED=$(( end - start ))
    log_ok "Build finished in $(( BUILD_ELAPSED/60 ))m $(( BUILD_ELAPSED%60 ))s"

    # Locate kernel image (preference order: dtb-appended > gz > plain)
    local img_dtb="${OUT_DIR}/arch/${ARCH}/boot/Image.gz-dtb"
    local img_gz="${OUT_DIR}/arch/${ARCH}/boot/Image.gz"
    local img_plain="${OUT_DIR}/arch/${ARCH}/boot/Image"

    if   [[ -f "$img_dtb"   ]]; then KERNEL_IMAGE="$img_dtb"
    elif [[ -f "$img_gz"    ]]; then KERNEL_IMAGE="$img_gz";    log_warn "Using Image.gz (no appended dtb)"
    elif [[ -f "$img_plain" ]]; then KERNEL_IMAGE="$img_plain"; log_warn "Using plain Image"
    else die "No kernel image found in ${OUT_DIR}/arch/${ARCH}/boot/"; fi

    log_ok "Kernel image : ${KERNEL_IMAGE}  ($(du -sh "$KERNEL_IMAGE" | cut -f1))"
}
