#!/usr/bin/env bash
# lib/args.sh — CLI argument parser
# Sourced by build.sh — do not execute directly.

usage() {
cat <<EOF
Usage: ./build.sh [OPTIONS]

Options:
  --toolchain  <gcc49|gcc_latest>   Toolchain selection      (default: gcc49)
  --defconfig  <name>               Kernel defconfig          (default: X00T_defconfig)
  --jobs       <N>                  Parallel jobs             (default: nproc)
  --clean                           Run 'make clean' before build
  --mrproper                        Run 'make mrproper' before build
  --no-telegram                     Disable all Telegram output
  --no-upload                       Skip Telegram file uploads
  --no-github                       Skip GitHub release
  --zip-only   <image_path>         Package an existing image, skip build
  -h, --help                        Print this help

Environment variables (can also be set in config/build.conf):
  TG_BOT_TOKEN    Telegram bot token
  TG_CHAT_ID      Telegram chat/channel ID  (e.g. -1001234567890)
  GH_TOKEN        GitHub personal access token

Examples:
  ./build.sh
  ./build.sh --toolchain gcc_latest --no-github
  ./build.sh --mrproper --jobs 8
  ./build.sh --zip-only out/arch/arm64/boot/Image.gz-dtb
EOF
}

parse_args() {
    # Defaults (can be overridden by config or CLI)
    OPT_TOOLCHAIN="${TOOLCHAIN:-gcc49}"
    OPT_DEFCONFIG="${DEFCONFIG:-X00T_defconfig}"
    OPT_JOBS="${JOBS:-$(nproc --all)}"
    OPT_CLEAN=false
    OPT_MRPROPER=false
    OPT_NO_TELEGRAM=false
    OPT_NO_UPLOAD=false
    OPT_NO_GITHUB=false
    OPT_ZIP_ONLY=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --toolchain)    OPT_TOOLCHAIN="$2";  shift 2 ;;
            --defconfig)    OPT_DEFCONFIG="$2";  shift 2 ;;
            --jobs)         OPT_JOBS="$2";       shift 2 ;;
            --clean)        OPT_CLEAN=true;      shift   ;;
            --mrproper)     OPT_MRPROPER=true;   shift   ;;
            --no-telegram)  OPT_NO_TELEGRAM=true; shift  ;;
            --no-upload)    OPT_NO_UPLOAD=true;  shift   ;;
            --no-github)    OPT_NO_GITHUB=true;  shift   ;;
            --zip-only)     OPT_ZIP_ONLY="$2";   shift 2 ;;
            -h|--help)      usage; exit 0 ;;
            *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
        esac
    done

    # Propagate parsed opts to global vars used by modules
    TOOLCHAIN="$OPT_TOOLCHAIN"
    DEFCONFIG="$OPT_DEFCONFIG"
    JOBS="$OPT_JOBS"

    [[ "$OPT_NO_TELEGRAM" == true ]] && TG_BOT_TOKEN="" && TG_CHAT_ID=""

    # Validate toolchain
    case "$TOOLCHAIN" in
        gcc49|gcc_latest) ;;
        *) echo "Invalid toolchain: ${TOOLCHAIN}. Use gcc49 or gcc_latest." >&2; exit 1 ;;
    esac
}
