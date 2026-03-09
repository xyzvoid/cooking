# SDM660 / X00T Kernel Builder

Modular build system for [xyzvoid/msm-4.4](https://github.com/xyzvoid/msm-4.4) targeting the Snapdragon 660 platform.

## Project Structure

```
kernel-builder/
├── build.sh                 ← Entry point
├── config/
│   └── build.conf           ← All configuration (repos, flags, paths)
├── lib/
│   ├── logger.sh            ← Colored output + print_banner / print_summary
│   ├── args.sh              ← CLI argument parser
│   ├── config.sh            ← Config loader + directory setup
│   ├── deps.sh              ← Dependency checker / installer
│   ├── toolchain.sh         ← GCC 4.9 / GCC latest setup
│   ├── sources.sh           ← Kernel + AnyKernel3 clone/sync
│   ├── builder.sh           ← defconfig, clean, compile
│   ├── package.sh           ← AnyKernel3 zip creation
│   ├── telegram.sh          ← Telegram Bot API notifications + uploads
│   └── github.sh            ← GitHub Releases API
└── .github/
    └── workflows/
        └── build.yml        ← CI/CD pipeline
```

---

## Quick Start (Local)

### 1. Set secrets

```bash
export TG_BOT_TOKEN="123456:ABCdef..."
export TG_CHAT_ID="-1001234567890"
export GH_TOKEN="ghp_xxxxxxxxxxxx"
```

### 2. Run

```bash
chmod +x build.sh
./build.sh
```

Output zip: `build/zips/xyzvoid-<version>-<YYYYMMDD_HHMMSS>.zip`

---

## CLI Reference

```
./build.sh [OPTIONS]

  --toolchain  <gcc49|gcc_latest>   Toolchain (default: gcc49)
  --defconfig  <n>               Defconfig (default: X00T_defconfig)
  --jobs       <N>                  Parallel jobs (default: nproc)
  --clean                           make clean before build
  --mrproper                        make mrproper before build
  --no-telegram                     Disable all Telegram output
  --no-upload                       Skip file uploads (Telegram)
  --no-github                       Skip GitHub release
  --zip-only   <image_path>         Package existing image, skip build
  -h, --help                        Show help
```

### Examples

```bash
# Default build
./build.sh

# Latest GCC, no GitHub release
./build.sh --toolchain gcc_latest --no-github

# Clean build
./build.sh --mrproper

# Repackage an existing image
./build.sh --zip-only build/msm-4.4/out/arch/arm64/boot/Image.gz-dtb

# Offline test (no notifications)
./build.sh --no-telegram --no-github
```

---

## GitHub Actions (CI/CD)

### Secrets required

Go to **Settings → Secrets and variables → Actions** and add:

| Secret | Description |
|---|---|
| `TG_BOT_TOKEN` | Telegram bot token from @BotFather |
| `TG_CHAT_ID` | Channel/group ID (e.g. `-1001234567890`) |
| `GH_TOKEN` | Personal access token with `repo` + `write:packages` scope |

### Triggers

| Event | Behavior |
|---|---|
| `push` to `android-4.4` / `main` | Full build + Telegram + GitHub Release |
| `pull_request` | Build only (no upload, no release) |
| `workflow_dispatch` | Manual — all options configurable in the UI |

### Manual trigger inputs

When running manually from **Actions → Build Kernel → Run workflow**:

- **Toolchain** — `gcc49` or `gcc_latest`
- **Defconfig** — defaults to `X00T_defconfig`
- **Clean build** — runs `mrproper` before building
- **Upload to Telegram** — toggle artifact upload
- **Create GitHub release** — toggle release creation

---

## Configuration (`config/build.conf`)

Edit this file instead of the scripts themselves.

```bash
KERNEL_NAME="xyzvoid"
ARCH="arm64"
DEFCONFIG="X00T_defconfig"
TOOLCHAIN="gcc49"

KERNEL_REPO="https://github.com/xyzvoid/msm-4.4.git"
ANYKERNEL_REPO="https://github.com/xyzvoid/AnyKernel3.git"

GH_RELEASE_REPO="xyzvoid/msm-4.4"
GH_RELEASE_BRANCH="android-4.4"
```

---

## Telegram Notifications

| Event | Message |
|---|---|
| Build queued | Start message (edited live) |
| Compiling | Status updated in-place |
| Build failed | Error message + log upload |
| Build done | Summary + zip upload + log upload |

The status message is **edited in-place** — one clean message per build.

---

## Output

```
build/
├── msm-4.4/            ← Kernel source
├── AnyKernel3/         ← Flashable package template
├── toolchains/         ← GCC toolchains (auto-downloaded)
├── logs/               ← All build logs
└── zips/
    ├── xyzvoid-4.4.302-20250310_143022.zip   ← Flashable zip
    └── xyzvoid-4.4.302-20250310_143022.info  ← Build metadata
```
