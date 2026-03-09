#!/usr/bin/env bash
# lib/package.sh — Package kernel into AnyKernel3 flashable zip
# Sourced by build.sh — do not execute directly.

# Populated by create_zip():
ZIP_PATH=""

create_zip() {
    log_step "Packaging with AnyKernel3"

    # Clean stale images from AnyKernel dir
    rm -f "${ANYKERNEL_DIR}"/Image* \
          "${ANYKERNEL_DIR}"/zImage* \
          "${ANYKERNEL_DIR}"/*.dtb  \
          "${ANYKERNEL_DIR}"/dtbo.img 2>/dev/null || true

    # Copy kernel image
    cp "$KERNEL_IMAGE" "${ANYKERNEL_DIR}/"
    log_info "Copied $(basename "$KERNEL_IMAGE") → AnyKernel3/"

    # Copy dtbo if present
    local dtbo="${OUT_DIR}/arch/${ARCH}/boot/dtbo.img"
    if [[ -f "$dtbo" ]]; then
        cp "$dtbo" "${ANYKERNEL_DIR}/"
        log_info "Copied dtbo.img → AnyKernel3/"
    fi

    # Copy any .dtb files if present
    local dtb_src="${OUT_DIR}/arch/${ARCH}/boot/dts"
    if [[ -d "$dtb_src" ]]; then
        find "$dtb_src" -name "*.dtb" -exec cp {} "${ANYKERNEL_DIR}/" \; 2>/dev/null || true
    fi

    ZIP_PATH="${ZIP_DIR}/${ZIP_NAME}"

    (
        cd "$ANYKERNEL_DIR"
        zip -r9 "$ZIP_PATH" . \
            --exclude="*.git*"           \
            --exclude=".github/*"        \
            --exclude="*.DS_Store"       \
            --exclude="*COMMIT_EDITMSG"  \
            --exclude="*.md"
    ) || die "zip creation failed"

    local size; size=$(du -sh "$ZIP_PATH" | cut -f1)
    log_ok "ZIP created : ${ZIP_PATH}  (${size})"
    log_ok "ZIP name    : ${ZIP_NAME}"

    # Write a build-info sidecar
    cat > "${ZIP_DIR}/${ZIP_NAME%.zip}.info" <<INFO
kernel_version=${KERNEL_VERSION}
zip_name=${ZIP_NAME}
defconfig=${DEFCONFIG}
toolchain=${TOOLCHAIN}
arch=${ARCH}
jobs=${JOBS}
build_elapsed=${BUILD_ELAPSED}
built_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
kernel_repo=${KERNEL_REPO}
anykernel_repo=${ANYKERNEL_REPO}
INFO
}
