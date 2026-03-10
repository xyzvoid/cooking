#!/usr/bin/env python3
# ============================================================
#  baka-compile — Kernel Build Script (Python edition)
#  Email   : xealea@proton.me
#  GitHub  : github.com/xealea
#  Copyright (c) 2023-2025 xealea <xealea@proton.me>
# ============================================================

import argparse
import configparser
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime
from getpass import getuser
from pathlib import Path

# ── rich imports ────────────────────────────────────────────
try:
    from rich import box
    from rich.align import Align
    from rich.columns import Columns
    from rich.console import Console
    from rich.live import Live
    from rich.markup import escape
    from rich.padding import Padding
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.prompt import Confirm, Prompt
    from rich.rule import Rule
    from rich.status import Status
    from rich.table import Table
    from rich.text import Text
    from rich.theme import Theme
except ImportError:
    print("ERROR: 'rich' library is not installed.")
    print("Install it with:  pip install rich")
    sys.exit(1)

# ============================================================
#  THEME & CONSOLE
# ============================================================
THEME = Theme(
    {
        "ok":      "bold bright_green",
        "warn":    "bold yellow",
        "err":     "bold bright_red",
        "info":    "bold magenta",
        "msg":     "bold cyan",
        "dim":     "dim white",
        "header":  "bold bright_white",
        "accent":  "bold cyan",
        "val":     "bright_yellow",
        "banner":  "bold bright_cyan",
    }
)

console = Console(theme=THEME, highlight=False)

SCRIPT_VERSION = "3.4.7"

# ============================================================
#  DEFAULTS
# ============================================================
DEFAULTS = {
    # Repos
    "kernel_repo":   "https://github.com/xyzvoid/msm-4.4",
    "kernel_branch": "",
    "ak3_repo":      "https://github.com/xyzvoid/AnyKernel3",
    "ak3_branch":    "",
    # Directories (resolved at runtime relative to BASE_DIR)
    "base_dir":      str(Path.cwd()),
    "kernel_dir":    "",   # → base_dir/msm-4.4
    "ak3_dir":       "",   # → base_dir/AnyKernel3
    "out_dir":       "",   # → kernel_dir/out
    "zip_dir":       "",   # → base_dir/zips
    "log_file":      "",   # → base_dir/build.log
    "tc_dir":        "",   # → base_dir/toolchains
    # Build identity
    "defconfig":          "X00T_defconfig",
    "arch":               "arm64",
    "subarch":            "",
    "kbuild_build_user":  "void",
    "kbuild_build_host":  "xyzbuild",
    "kernel_name":        "xyzvoid",
    "device_name":        "X00T",
    # Build options
    "jobs":               str(os.cpu_count() or 4),
    "make_extra_flags":   "",
    "clone_depth":        "1",
    "skip_ak3":           "false",
    "clean_build":        "true",
    "ccache":             "true",
    # GCC auto-clone / download
    # gcc_variant = "mvaisakh" → git-clone mvaisakh prebuilts (branch 08032026)
    # gcc_variant = "gnu"      → download ARM GNU Toolchain 15.2.Rel1 tarballs
    "gcc_auto_clone":    "true",
    "gcc_variant":       "mvaisakh",   # "mvaisakh" | "gnu"
    # ── mvaisakh variant: pre-built release tarballs (08032026) ──
    # Downloaded from github.com/mvaisakh/gcc-build/releases/tag/08032026
    "gcc_arm64_url":     "https://github.com/mvaisakh/gcc-build/releases/download/08032026/eva-gcc-arm64-08032026.xz",
    "gcc_arm32_url":     "https://github.com/mvaisakh/gcc-build/releases/download/08032026/eva-gcc-arm-08032026.xz",
    "gcc_arm64_dir":     "",   # → tc_dir/gcc-arm64
    "gcc_arm32_dir":     "",   # → tc_dir/gcc-arm
    "gcc_arm64_prefix":  "aarch64-elf-",
    "gcc_arm32_prefix":  "arm-eabi-",
    # ── GNU GCC 15.2 variant (ARM GNU Toolchain 15.2.Rel1) ────
    # Tarballs from developer.arm.com — extracted into tc_dir automatically.
    "gnu_gcc_version":   "15.2.rel1",
    "gnu_arm64_url":     "https://developer.arm.com/-/media/Files/downloads/gnu/15.2.rel1/binrel/arm-gnu-toolchain-15.2.rel1-x86_64-aarch64-none-linux-gnu.tar.xz",
    "gnu_arm32_url":     "https://developer.arm.com/-/media/Files/downloads/gnu/15.2.rel1/binrel/arm-gnu-toolchain-15.2.rel1-x86_64-arm-none-linux-gnueabihf.tar.xz",
    "gnu_arm64_dir":     "",   # → tc_dir/arm-gnu-toolchain-15.2.rel1-x86_64-aarch64-none-linux-gnu
    "gnu_arm32_dir":     "",   # → tc_dir/arm-gnu-toolchain-15.2.rel1-x86_64-arm-none-linux-gnueabihf
    "gnu_arm64_prefix":  "aarch64-none-linux-gnu-",
    "gnu_arm32_prefix":  "arm-none-linux-gnueabihf-",
    # Clang
    "clang_dir":         "",
    "clang_triple":      "aarch64-linux-gnu-",
    "clang_arm64_prefix":"aarch64-linux-gnu-",
    "clang_arm32_prefix":"arm-linux-gnueabi-",
    "llvm_ld":           "",
    "llvm_ar":           "",
    "llvm_nm":           "",
    "llvm_objcopy":      "",
    "llvm_objdump":      "",
    "llvm_strip":        "",
    # Credentials / notifications
    "gh_token":      "",
    "tg_bot_token":  "",
    "tg_chat_id":    "",
    "tg_notify":     "true",
    # Zip naming
    "zip_name_template": "%KERNEL%-%DEVICE%-%DATE%-%TIME%.zip",
}


# ============================================================
#  CONFIG MANAGER
# ============================================================
class Config:
    """Wraps DEFAULTS + config file + CLI overrides."""

    def __init__(self, cfg_path: str):
        self._data = dict(DEFAULTS)
        self.cfg_path = cfg_path
        self._load_env()       # env vars override defaults
        self._load_file()      # config file overrides env

    # ── private ─────────────────────────────────────────────
    def _load_env(self):
        for key in self._data:
            env_val = os.environ.get(key.upper())
            if env_val is not None:
                self._data[key] = env_val

    def _load_file(self):
        p = Path(self.cfg_path)
        if not p.exists():
            return
        cp = configparser.ConfigParser()
        cp.read_string("[baka]\n" + p.read_text())
        for key, val in cp["baka"].items():
            if key in self._data:
                self._data[key] = val
        console.print(f"[ok][✓][/ok] Config loaded from [val]{self.cfg_path}[/val]")

    # ── public ──────────────────────────────────────────────
    def get(self, key: str) -> str:
        return self._data.get(key, "")

    def set(self, key: str, value: str):
        self._data[key] = value

    def apply_args(self, namespace: argparse.Namespace):
        """Merge parsed CLI args (highest priority)."""
        for key, val in vars(namespace).items():
            if val is not None and key in self._data:
                self._data[key] = str(val) if not isinstance(val, str) else val

    def resolve_dirs(self):
        base = self.get("base_dir")
        if not self.get("kernel_dir"):
            self.set("kernel_dir", str(Path(base) / "msm-4.4"))
        if not self.get("ak3_dir"):
            self.set("ak3_dir", str(Path(base) / "AnyKernel3"))
        if not self.get("out_dir"):
            self.set("out_dir", str(Path(self.get("kernel_dir")) / "out"))
        if not self.get("zip_dir"):
            self.set("zip_dir", str(Path(base) / "zips"))
        if not self.get("log_file"):
            self.set("log_file", str(Path(base) / "build.log"))
        if not self.get("tc_dir"):
            self.set("tc_dir", str(Path(base) / "toolchains"))
        if not self.get("subarch"):
            self.set("subarch", self.get("arch"))
        # mvaisakh GCC directories
        if not self.get("gcc_arm64_dir"):
            self.set("gcc_arm64_dir",
                     str(Path(self.get("tc_dir")) / "gcc-arm64"))
        if not self.get("gcc_arm32_dir"):
            self.set("gcc_arm32_dir",
                     str(Path(self.get("tc_dir")) / "gcc-arm"))
        # GNU GCC 15.2 directories (derived from tarball name)
        ver = self.get("gnu_gcc_version") or "15.2.rel1"
        if not self.get("gnu_arm64_dir"):
            self.set("gnu_arm64_dir",
                     str(Path(self.get("tc_dir")) /
                         f"arm-gnu-toolchain-{ver}-x86_64-aarch64-none-linux-gnu"))
        if not self.get("gnu_arm32_dir"):
            self.set("gnu_arm32_dir",
                     str(Path(self.get("tc_dir")) /
                         f"arm-gnu-toolchain-{ver}-x86_64-arm-none-linux-gnueabihf"))

    def save(self):
        lines = [
            f"# baka-compile configuration — generated {datetime.now()}",
            f"# Edit manually or regenerate with: baka-compile.py --save-config",
            "",
        ]
        sections = {
            "Repos":       ["kernel_repo","kernel_branch","ak3_repo","ak3_branch"],
            "Directories": ["base_dir","kernel_dir","ak3_dir","out_dir","zip_dir","log_file","tc_dir"],
            "Build identity": ["defconfig","arch","subarch","kbuild_build_user",
                               "kbuild_build_host","kernel_name","device_name"],
            "Build options": ["jobs","make_extra_flags","clone_depth","skip_ak3",
                              "clean_build","ccache"],
            "GCC toolchain": ["gcc_auto_clone","gcc_variant",
                              "gcc_arm64_url","gcc_arm32_url",
                              "gcc_arm64_dir","gcc_arm32_dir",
                              "gcc_arm64_prefix","gcc_arm32_prefix"],
            "GNU GCC 15.2":  ["gnu_gcc_version",
                              "gnu_arm64_url","gnu_arm32_url",
                              "gnu_arm64_dir","gnu_arm32_dir",
                              "gnu_arm64_prefix","gnu_arm32_prefix"],
            "Clang": ["clang_dir","clang_triple","clang_arm64_prefix","clang_arm32_prefix",
                      "llvm_ld","llvm_ar","llvm_nm","llvm_objcopy","llvm_objdump","llvm_strip"],
            "Credentials": ["gh_token","tg_bot_token","tg_chat_id","tg_notify"],
            "Zip naming":  ["zip_name_template"],
        }
        for section, keys in sections.items():
            lines.append(f"# ── {section}")
            for k in keys:
                lines.append(f'{k} = {self._data.get(k, "")}')
            lines.append("")
        Path(self.cfg_path).write_text("\n".join(lines))
        console.print(f"[ok][✓][/ok] Config saved → [val]{self.cfg_path}[/val]")


# ============================================================
#  BANNER
# ============================================================
def print_banner():
    art = Text()
    art.append("  ██████╗  █████╗ ██╗  ██╗ █████╗ \n", style="bold cyan")
    art.append("  ██╔══██╗██╔══██╗██║ ██╔╝██╔══██╗\n", style="bold cyan")
    art.append("  ██████╔╝███████║█████╔╝ ███████║\n", style="bold bright_cyan")
    art.append("  ██╔══██╗██╔══██║██╔═██╗ ██╔══██║\n", style="bold bright_cyan")
    art.append("  ██████╔╝██║  ██║██║  ██╗██║  ██║\n", style="bold white")
    art.append("  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝\n", style="bold white")

    sub = Text.assemble(
        ("  compile  ", "bold bright_black on cyan"),
        ("  kernel build script  ", "bold cyan"),
        (f" v{SCRIPT_VERSION} ", "dim white"),
    )
    console.print(Padding(art, (1, 0, 0, 0)))
    console.print(Padding(sub, (0, 0, 1, 0)))
    console.print(Rule(style="dim cyan"))


# ============================================================
#  LOGGING HELPERS
# ============================================================
def msg(text: str):
    console.print(f"[msg]>>[/msg] {text}")

def ok(text: str):
    console.print(f"[ok][✓][/ok] {text}")

def warn(text: str):
    console.print(f"[warn][!][/warn] {text}")

def die(text: str):
    console.print(f"[err][✗][/err] {text}")
    sys.exit(1)

def info(text: str):
    console.print(f"[info]   {text}[/info]")


# ============================================================
#  SHOW CONFIG (rich table)
# ============================================================
def show_config(cfg: Config):
    cfg.resolve_dirs()

    def section(title: str, rows: list[tuple[str, str]]):
        t = Table(
            box=box.ROUNDED,
            border_style="dim cyan",
            show_header=True,
            header_style="bold cyan",
            expand=False,
            min_width=60,
        )
        t.add_column("Key", style="bold white", min_width=24)
        t.add_column("Value", style="bright_yellow")
        for k, v in rows:
            display = v if v else "[dim](unset)[/dim]"
            t.add_row(k, display)
        console.print(Panel(t, title=f"[header]{title}[/header]",
                            border_style="cyan", padding=(0, 1)))
        console.print()

    console.print()
    section("Repos", [
        ("kernel_repo",    cfg.get("kernel_repo")),
        ("kernel_branch",  cfg.get("kernel_branch") or "(default)"),
        ("ak3_repo",       cfg.get("ak3_repo")),
        ("ak3_branch",     cfg.get("ak3_branch") or "(default)"),
    ])
    section("Directories", [
        ("base_dir",    cfg.get("base_dir")),
        ("kernel_dir",  cfg.get("kernel_dir")),
        ("ak3_dir",     cfg.get("ak3_dir")),
        ("out_dir",     cfg.get("out_dir")),
        ("zip_dir",     cfg.get("zip_dir")),
        ("log_file",    cfg.get("log_file")),
        ("tc_dir",      cfg.get("tc_dir")),
    ])
    section("Build Identity", [
        ("defconfig",          cfg.get("defconfig") or "(prompt at build time)"),
        ("arch",               cfg.get("arch")),
        ("subarch",            cfg.get("subarch")),
        ("kbuild_build_user",  cfg.get("kbuild_build_user") or "(prompt at build time)"),
        ("kbuild_build_host",  cfg.get("kbuild_build_host") or "(prompt at build time)"),
        ("kernel_name",        cfg.get("kernel_name")),
        ("device_name",        cfg.get("device_name")),
        ("zip_name_template",  cfg.get("zip_name_template")),
    ])
    section("Build Options", [
        ("jobs",             cfg.get("jobs")),
        ("make_extra_flags", cfg.get("make_extra_flags") or "(none)"),
        ("clone_depth",      cfg.get("clone_depth")),
        ("clean_build",      cfg.get("clean_build")),
        ("ccache",           cfg.get("ccache")),
        ("skip_ak3",         cfg.get("skip_ak3")),
    ])
    section("GCC — mvaisakh (release 08032026)", [
        ("gcc_auto_clone",   cfg.get("gcc_auto_clone")),
        ("gcc_variant",      cfg.get("gcc_variant")),
        ("gcc_arm64_url",    cfg.get("gcc_arm64_url")),
        ("gcc_arm64_dir",    cfg.get("gcc_arm64_dir")),
        ("gcc_arm32_url",    cfg.get("gcc_arm32_url")),
        ("gcc_arm32_dir",    cfg.get("gcc_arm32_dir")),
        ("gcc_arm64_prefix", cfg.get("gcc_arm64_prefix")),
        ("gcc_arm32_prefix", cfg.get("gcc_arm32_prefix")),
    ])
    section("GCC — GNU 15.2 (ARM GNU Toolchain 15.2.Rel1)", [
        ("gnu_gcc_version",  cfg.get("gnu_gcc_version")),
        ("gnu_arm64_url",    cfg.get("gnu_arm64_url")),
        ("gnu_arm32_url",    cfg.get("gnu_arm32_url")),
        ("gnu_arm64_dir",    cfg.get("gnu_arm64_dir")),
        ("gnu_arm32_dir",    cfg.get("gnu_arm32_dir")),
        ("gnu_arm64_prefix", cfg.get("gnu_arm64_prefix")),
        ("gnu_arm32_prefix", cfg.get("gnu_arm32_prefix")),
    ])
    section("Clang", [
        ("clang_dir",          cfg.get("clang_dir") or "(prompt at build time)"),
        ("clang_triple",       cfg.get("clang_triple")),
        ("clang_arm64_prefix", cfg.get("clang_arm64_prefix")),
        ("clang_arm32_prefix", cfg.get("clang_arm32_prefix")),
        ("llvm_ld",            cfg.get("llvm_ld") or "(auto: clang_dir/ld.lld)"),
        ("llvm_ar",            cfg.get("llvm_ar") or "(auto: clang_dir/llvm-ar)"),
        ("llvm_nm",            cfg.get("llvm_nm") or "(auto: clang_dir/llvm-nm)"),
        ("llvm_objcopy",       cfg.get("llvm_objcopy") or "(auto)"),
        ("llvm_objdump",       cfg.get("llvm_objdump") or "(auto)"),
        ("llvm_strip",         cfg.get("llvm_strip") or "(auto)"),
    ])
    section("Notifications", [
        ("tg_notify",    cfg.get("tg_notify")),
        ("tg_bot_token", "(set)" if cfg.get("tg_bot_token") else "(unset)"),
        ("tg_chat_id",   "(set)" if cfg.get("tg_chat_id") else "(unset)"),
        ("gh_token",     "(set)" if cfg.get("gh_token") else "(unset)"),
    ])


# ============================================================
#  TELEGRAM
# ============================================================
def tg_send_msg(cfg: Config, text: str):
    if cfg.get("tg_notify") == "false":
        return
    token = cfg.get("tg_bot_token")
    chat  = cfg.get("tg_chat_id")
    if not token or not chat:
        return
    try:
        data = urllib.parse.urlencode({
            "chat_id": chat, "parse_mode": "Markdown", "text": text
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=data, method="POST"
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass  # notifications are best-effort


def tg_send_file(cfg: Config, path: str, caption: str = ""):
    if cfg.get("tg_notify") == "false":
        return
    token = cfg.get("tg_bot_token")
    chat  = cfg.get("tg_chat_id")
    if not token or not chat or not Path(path).exists():
        return
    try:
        import urllib.request, mimetypes
        boundary = "----BakaCompileBoundary"
        def field(name, value):
            return (f'--{boundary}\r\n'
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                    f'{value}\r\n').encode()
        fname = Path(path).name
        fdata = Path(path).read_bytes()
        mime  = mimetypes.guess_type(fname)[0] or "application/octet-stream"
        body = (field("chat_id", chat) + field("parse_mode", "Markdown") +
                field("caption", caption) +
                f'--{boundary}\r\nContent-Disposition: form-data; name="document"; '
                f'filename="{fname}"\r\nContent-Type: {mime}\r\n\r\n'.encode() +
                fdata + f'\r\n--{boundary}--\r\n'.encode())
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=30)
    except Exception:
        pass


# ============================================================
#  GIT HELPERS
# ============================================================
def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, **kwargs)


def _git_clone_or_pull(label: str, url: str, dest: str,
                       branch: str, depth: int,
                       recurse_submodules: bool = False):
    dest_path = Path(dest)
    if (dest_path / ".git").exists():
        warn(f"{label} already exists — pulling latest...")
        r = _run(["git", "-C", dest, "pull", "--rebase"],
                 capture_output=True, text=True)
        if r.returncode != 0:
            die(f"git pull failed for {label}:\n{r.stderr}")
        if recurse_submodules:
            msg(f"Updating submodules for {label}...")
            r = _run(["git", "-C", dest, "submodule", "update",
                      "--init", "--recursive"],
                     capture_output=True, text=True)
            if r.returncode != 0:
                die(f"Submodule update failed for {label}:\n{r.stderr}")
            ok(f"{label} submodules updated")
    else:
        cmd = ["git", "clone"]
        if depth > 0:
            cmd += [f"--depth={depth}"]
        if branch:
            cmd += [f"--branch={branch}", "--single-branch"]
        if recurse_submodules:
            cmd += ["--recurse-submodules", "--shallow-submodules"]
        cmd += [url, dest]
        r = _run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            die(f"Failed to clone {label}:\n{r.stderr}")
    ok(f"{label} ready")


# ============================================================
#  SOURCE CLONING
# ============================================================
def clone_sources(cfg: Config):
    cfg.resolve_dirs()
    kurl  = cfg.get("kernel_repo")
    akurl = cfg.get("ak3_repo")
    depth = int(cfg.get("clone_depth") or 1)

    # Inject GH token
    gh = cfg.get("gh_token")
    if gh:
        if kurl.startswith("https://github.com/"):
            kurl = kurl.replace("https://", f"https://x-token:{gh}@")
        if akurl.startswith("https://github.com/"):
            akurl = akurl.replace("https://", f"https://x-token:{gh}@")

    with Progress(
        SpinnerColumn(spinner_name="dots", style="cyan"),
        TextColumn("[msg]{task.description}[/msg]"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        t1 = progress.add_task("Cloning kernel source...", total=None)
        _git_clone_or_pull("Kernel source", kurl,
                           cfg.get("kernel_dir"), cfg.get("kernel_branch"),
                           depth, recurse_submodules=True)
        progress.update(t1, description="[ok]Kernel source + submodules cloned[/ok]")

        t2 = progress.add_task("Cloning AnyKernel3...", total=None)
        _git_clone_or_pull("AnyKernel3", akurl,
                           cfg.get("ak3_dir"), cfg.get("ak3_branch"), depth)
        progress.update(t2, description="[ok]AnyKernel3 cloned[/ok]")


# ============================================================
#  GCC TOOLCHAIN SETUP  (mvaisakh tarball  OR  GNU tarball)
# ============================================================
def _detect_archive_format(path: Path) -> str:
    """
    Return a short format tag by inspecting magic bytes.
    Tags: 'xz', 'gz', 'bz2', 'zst', 'tar', 'unknown'
    """
    try:
        with open(str(path), "rb") as f:
            magic = f.read(6)
        if magic[:6] == b'\xfd7zXZ\x00':          return "xz"
        if magic[:2] == b'\x1f\x8b':               return "gz"
        if magic[:3] == b'BZh':                     return "bz2"
        if magic[:4] == b'\x28\xb5\x2f\xfd':       return "zst"
        if magic[:5] == b'ustar' or magic[257:262] == b'ustar': return "tar"
        # Read further for ustar at offset 257
        with open(str(path), "rb") as f:
            f.seek(257)
            if f.read(5) == b'ustar':               return "tar"
    except Exception:
        pass
    return "unknown"


def _download_and_extract(label: str, url: str, dest: str):
    """
    Download a toolchain archive and extract it.

    Detects the actual file format via magic bytes and uses the right
    tool — handles xz, gz, bz2, zstd, plain tar, and unknown/renamed files.

    Skips download + extract if dest already exists and is non-empty.
    """
    import tarfile as _tarfile

    dest_path = Path(dest)
    if dest_path.exists() and any(dest_path.iterdir()):
        warn(f"{label} already present — skipping download")
        return

    tc_dir = dest_path.parent
    tc_dir.mkdir(parents=True, exist_ok=True)

    fname   = url.split("/")[-1]
    tarball = tc_dir / fname

    # ── download ────────────────────────────────────────────
    if not tarball.exists():
        console.print(Rule(f"[accent]Downloading {label}[/accent]", style="dim cyan"))
        info(f"URL  : {url}")
        info(f"Save : {tarball}")
        with console.status(f"[cyan]Downloading {fname}...[/cyan]", spinner="dots"):
            try:
                urllib.request.urlretrieve(url, str(tarball))
            except Exception as exc:
                die(f"Download failed for {label}: {exc}")
        ok(f"Downloaded → {tarball}")

    # ── detect format ────────────────────────────────────────
    fmt = _detect_archive_format(tarball)
    info(f"Detected format : {fmt}  ({tarball.stat().st_size // 1024 // 1024} MB)")

    console.print(Rule(f"[accent]Extracting {label}[/accent]", style="dim cyan"))
    info(f"Archive : {tarball}")
    info(f"Into    : {tc_dir}")

    with console.status(f"[cyan]Extracting {fname}...[/cyan]", spinner="dots"):

        # ── Strategy 1: tar with explicit flag matching detected format ──
        if shutil.which("tar"):
            flag_map = {"xz": "J", "gz": "z", "bz2": "j", "zst": "--zstd -", "tar": ""}
            flag = flag_map.get(fmt)
            if flag is not None:
                # build the tar command
                if fmt == "zst":
                    tar_cmd = ["tar", "--zstd", "-xf", str(tarball), "-C", str(tc_dir)]
                elif fmt == "tar":
                    tar_cmd = ["tar", "-xf", str(tarball), "-C", str(tc_dir)]
                else:
                    tar_cmd = ["tar", f"-x{flag}f", str(tarball), "-C", str(tc_dir)]
                r = _run(tar_cmd, capture_output=True, text=True)
                if r.returncode == 0:
                    ok(f"{label} extracted → {tc_dir}")
                    return
                warn(f"tar explicit flag failed: {r.stderr.strip()}")

            # ── Strategy 2: tar auto-detect (no compression flag) ────────
            r = _run(["tar", "-xf", str(tarball), "-C", str(tc_dir)],
                     capture_output=True, text=True)
            if r.returncode == 0:
                ok(f"{label} extracted → {tc_dir}")
                return
            warn(f"tar auto-detect failed: {r.stderr.strip()}")

        # ── Strategy 3: Python tarfile (handles gz, bz2, xz natively) ───
        for mode in ("r:*", "r:gz", "r:bz2", "r:xz", "r"):
            try:
                with _tarfile.open(str(tarball), mode=mode) as tf:
                    tf.extractall(path=str(tc_dir))
                ok(f"{label} extracted → {tc_dir}")
                return
            except Exception:
                continue

        # ── Strategy 4: decompress with xz/gzip/zstd then tar ───────────
        decompressed = tarball.with_suffix("")
        decompressed_ok = False
        try:
            if fmt == "xz" and shutil.which("xz"):
                r = _run(["xz", "-dk", str(tarball)], capture_output=True, text=True)
                decompressed_ok = r.returncode == 0
            elif fmt == "gz" and shutil.which("gunzip"):
                r = _run(["gunzip", "-k", str(tarball)], capture_output=True, text=True)
                decompressed_ok = r.returncode == 0
            elif fmt == "zst" and shutil.which("zstd"):
                r = _run(["zstd", "-dk", str(tarball), "-o", str(decompressed)],
                         capture_output=True, text=True)
                decompressed_ok = r.returncode == 0

            if decompressed_ok and decompressed.exists():
                r = _run(["tar", "-xf", str(decompressed), "-C", str(tc_dir)],
                         capture_output=True, text=True)
                decompressed.unlink(missing_ok=True)
                if r.returncode == 0:
                    ok(f"{label} extracted → {tc_dir}")
                    return
        except Exception:
            pass

        die(
            f"Could not extract {tarball.name} (detected format: {fmt}).\n"
            f"       Try manually: tar -xf {tarball} -C {tc_dir}\n"
            f"       Then re-run with --no-gcc-clone."
        )


def clone_gcc_toolchains(cfg: Config):
    cfg.resolve_dirs()

    if cfg.get("gcc_auto_clone") != "true":
        warn("GCC auto-download disabled (gcc_auto_clone=false)")
        warn("Ensure gcc/gnu arm64/arm32 dir flags are set manually.")
        return

    variant = cfg.get("gcc_variant").lower()

    # ── mvaisakh variant: pre-built release tarballs ─────────
    if variant == "mvaisakh":
        tcs = [
            ("mvaisakh GCC ARM64 (eva-gcc-arm64-08032026)",
             cfg.get("gcc_arm64_url"), cfg.get("gcc_arm64_dir")),
            ("mvaisakh GCC ARM32 (eva-gcc-arm-08032026)",
             cfg.get("gcc_arm32_url"), cfg.get("gcc_arm32_dir")),
        ]
        for label, url, dest in tcs:
            _download_and_extract(label, url, dest)

        arm64_gcc = Path(cfg.get("gcc_arm64_dir")) / "bin" / f"{cfg.get('gcc_arm64_prefix')}gcc"
        arm32_gcc = Path(cfg.get("gcc_arm32_dir")) / "bin" / f"{cfg.get('gcc_arm32_prefix')}gcc"
        for p in [arm64_gcc, arm32_gcc]:
            if not p.exists() or not os.access(str(p), os.X_OK):
                die(f"GCC binary not found or not executable: {p}")
        ok("mvaisakh GCC (08032026) toolchain binaries verified")

    # ── GNU variant: ARM GNU Toolchain 15.2.Rel1 tarballs ────
    elif variant == "gnu":
        tcs = [
            ("GNU GCC 15.2 ARM64 (aarch64-none-linux-gnu)",
             cfg.get("gnu_arm64_url"), cfg.get("gnu_arm64_dir")),
            ("GNU GCC 15.2 ARM32 (arm-none-linux-gnueabihf)",
             cfg.get("gnu_arm32_url"), cfg.get("gnu_arm32_dir")),
        ]
        for label, url, dest in tcs:
            _download_and_extract(label, url, dest)

        arm64_gcc = Path(cfg.get("gnu_arm64_dir")) / "bin" / f"{cfg.get('gnu_arm64_prefix')}gcc"
        arm32_gcc = Path(cfg.get("gnu_arm32_dir")) / "bin" / f"{cfg.get('gnu_arm32_prefix')}gcc"
        for p in [arm64_gcc, arm32_gcc]:
            if not p.exists() or not os.access(str(p), os.X_OK):
                die(f"GNU GCC binary not found or not executable: {p}")
        ok("GNU GCC 15.2 toolchain binaries verified")

    else:
        die(f"Unknown gcc_variant '{variant}' — must be 'mvaisakh' or 'gnu'")




# ============================================================
#  PROMPTS
# ============================================================
def set_env_vars(cfg: Config):
    if not cfg.get("defconfig"):
        val = Prompt.ask(
            "[msg]>>[/msg] Defconfig name",
            default="sdm660-perf_defconfig",
            console=console,
        )
        cfg.set("defconfig", val)

    if not cfg.get("kbuild_build_host"):
        val = Prompt.ask(
            "[msg]>>[/msg] Build host string",
            default=socket.gethostname(),
            console=console,
        )
        cfg.set("kbuild_build_host", val)

    if not cfg.get("kbuild_build_user"):
        val = Prompt.ask(
            "[msg]>>[/msg] Build user string",
            default=getuser(),
            console=console,
        )
        cfg.set("kbuild_build_user", val)

    os.environ["KBUILD_BUILD_USER"] = cfg.get("kbuild_build_user")
    os.environ["KBUILD_BUILD_HOST"] = cfg.get("kbuild_build_host")


# ============================================================
#  ZIP NAME BUILDER
# ============================================================
def make_zip_name(cfg: Config, tc_label: str) -> str:
    branch = ""
    try:
        r = _run(["git", "-C", cfg.get("kernel_dir"),
                  "rev-parse", "--abbrev-ref", "HEAD"],
                 capture_output=True, text=True)
        branch = r.stdout.strip()
    except Exception:
        pass

    now = datetime.now()
    name = cfg.get("zip_name_template")
    name = name.replace("%KERNEL%", cfg.get("kernel_name"))
    name = name.replace("%DEVICE%", cfg.get("device_name"))
    name = name.replace("%ARCH%",   cfg.get("arch"))
    name = name.replace("%TC%",     tc_label)
    name = name.replace("%DATE%",   now.strftime("%Y%m%d"))
    name = name.replace("%TIME%",   now.strftime("%H%M"))
    name = name.replace("%BRANCH%", branch or "unknown")
    return name


# ============================================================
#  ANYKERNEL3 PACKAGING
# ============================================================
def package_zip(cfg: Config, tc_label: str) -> str:
    if cfg.get("skip_ak3") == "true":
        warn("Skipping AnyKernel3 packaging (--skip-zip)")
        return ""

    boot_dir = Path(cfg.get("out_dir")) / "arch" / cfg.get("arch") / "boot"
    image = None
    for candidate in ["Image.gz-dtb", "Image.gz", "Image"]:
        p = boot_dir / candidate
        if p.exists():
            image = p
            break
    if image is None:
        die(f"No kernel Image found in {boot_dir}")

    msg("Packaging with AnyKernel3...")
    zip_dir = Path(cfg.get("zip_dir"))
    zip_dir.mkdir(parents=True, exist_ok=True)

    zip_name = make_zip_name(cfg, tc_label)
    zip_path = zip_dir / zip_name

    ak3_dir = Path(cfg.get("ak3_dir"))
    shutil.copy2(str(image), str(ak3_dir / image.name))
    dtbo = boot_dir / "dtbo.img"
    if dtbo.exists():
        shutil.copy2(str(dtbo), str(ak3_dir / "dtbo.img"))
        info("dtbo.img included in flashable zip")
    else:
        info("dtbo.img not found — skipping (not required for this device)")

    with console.status("[cyan]Creating flashable zip...[/cyan]", spinner="dots"):
        r = _run(
            ["zip", "-r9", str(zip_path), ".",
             "-x", "*.git*", "-x", "README.md", "-x", "*placeholder*"],
            cwd=str(ak3_dir),
            capture_output=True, text=True,
        )
    if r.returncode != 0:
        die(f"zip failed:\n{r.stderr}")

    ok(f"Flashable zip → {zip_path}")
    return str(zip_path)


# ============================================================
#  BUILD OUTPUT STREAMING
# ============================================================
def stream_make(cmd: list[str], log_file: str) -> int:
    """Run make, stream output to console with rich + write to log."""
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    console.print(Rule("[dim]Build Output[/dim]", style="dim"))
    with open(log_file, "w") as log:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
        )
        for line in proc.stdout:
            log.write(line)
            stripped = line.rstrip()
            if not stripped:
                continue
            # Colour key patterns
            if " error:" in stripped or "Error " in stripped:
                console.print(f"[err]{escape(stripped)}[/err]")
            elif " warning:" in stripped:
                console.print(f"[warn]{escape(stripped)}[/warn]")
            elif stripped.startswith("  CC") or stripped.startswith("  LD") or \
                 stripped.startswith("  AR") or stripped.startswith("  AS") or \
                 stripped.startswith("  OBJCOPY"):
                console.print(f"[dim]{escape(stripped)}[/dim]")
            else:
                console.print(escape(stripped))
        proc.wait()
    console.print(Rule(style="dim"))
    return proc.returncode


# ============================================================
#  PRE-BUILD
# ============================================================
def pre_build(cfg: Config):
    set_env_vars(cfg)
    cfg.resolve_dirs()

    # ── dependency checks ────────────────────────────────────
    missing = [t for t in ["make", "bc", "git"] if not shutil.which(t)]
    if missing:
        die(
            f"Missing required tools: {', '.join(missing)}\n"
            f"       Install with: sudo apt-get install -y {' '.join(missing)}"
        )

    # ── clone if needed ──────────────────────────────────────
    kernel_git = Path(cfg.get("kernel_dir")) / ".git"
    if not kernel_git.exists():
        clone_sources(cfg)
    else:
        # Ensure submodules are initialised even if the repo was
        # cloned externally (e.g. a pre-existing workspace clone).
        submodule_cfg = Path(cfg.get("kernel_dir")) / ".gitmodules"
        if submodule_cfg.exists():
            msg("Initialising kernel submodules...")
            r = _run(
                ["git", "-C", cfg.get("kernel_dir"), "submodule",
                 "update", "--init", "--recursive"],
                capture_output=True, text=True,
            )
            if r.returncode != 0:
                die(f"Submodule init failed:\n{r.stderr}")
            ok("Kernel submodules ready")

    if cfg.get("clean_build") == "true":
        msg("Running make clean...")
        r = _run(
            ["make", "-C", cfg.get("kernel_dir"),
             f"-j{cfg.get('jobs')}", f"O={cfg.get('out_dir')}",
             f"ARCH={cfg.get('arch')}", "clean"],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            warn("make clean returned non-zero — continuing")

    msg(f"Generating defconfig ({cfg.get('defconfig')})...")
    r = _run([
        "make", "-C", cfg.get("kernel_dir"),
        f"-j{cfg.get('jobs')}", f"O={cfg.get('out_dir')}",
        f"ARCH={cfg.get('arch')}", f"SUBARCH={cfg.get('subarch')}",
        cfg.get("defconfig"),
    ], capture_output=True, text=True)
    if r.returncode != 0:
        die(f"Defconfig step failed:\n{r.stderr}")
    ok(f"Defconfig applied: {cfg.get('defconfig')}")


# ============================================================
#  POST-BUILD
# ============================================================
def post_build(cfg: Config, start_time: float, tc_label: str):
    elapsed = int(time.time() - start_time)
    mins, secs = divmod(elapsed, 60)

    boot_dir = Path(cfg.get("out_dir")) / "arch" / cfg.get("arch") / "boot"
    image_check = None
    for candidate in ["Image.gz-dtb", "Image.gz", "Image"]:
        p = boot_dir / candidate
        if p.exists():
            image_check = p
            break

    if image_check is None:
        tg_send_msg(cfg,
            f"❌ *Kernel build FAILED*\n"
            f"Toolchain: `{tc_label}`\n"
            f"Defconfig: `{cfg.get('defconfig')}`\n"
            f"Arch: `{cfg.get('arch')}`\n"
            f"Duration: {mins}m {secs}s"
        )
        die("Kernel image not found — build failed")

    console.print(Panel(
        f"[ok]Build finished in [val]{mins}m {secs}s[/val][/ok]",
        border_style="green", expand=False
    ))

    zip_path = package_zip(cfg, tc_label)

    tg_msg = (
        f"✅ *Kernel build SUCCESS*\n"
        f"Toolchain: `{tc_label}`\n"
        f"Defconfig: `{cfg.get('defconfig')}`\n"
        f"Arch: `{cfg.get('arch')}`\n"
        f"Duration: {mins}m {secs}s"
    )
    if zip_path:
        tg_msg += f"\nFile: `{Path(zip_path).name}`"

    tg_send_msg(cfg, tg_msg)
    if zip_path:
        tg_send_file(
            cfg, zip_path,
            f"🔥 {cfg.get('kernel_name')} for {cfg.get('device_name')} | "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )

    # ── Final summary panel ─────────────────────────────────
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    t.add_column(style="dim white")
    t.add_column(style="bright_yellow")
    t.add_row("Toolchain",   tc_label)
    t.add_row("Defconfig",   cfg.get("defconfig"))
    t.add_row("Arch",        cfg.get("arch"))
    t.add_row("Duration",    f"{mins}m {secs}s")
    if zip_path:
        t.add_row("Output zip", zip_path)
    console.print(Panel(
        t,
        title="[ok] ✓ Build Complete[/ok]",
        border_style="bright_green",
        padding=(1, 2),
    ))


# ============================================================
#  GCC BUILD
# ============================================================
def build_gcc(cfg: Config):
    cfg.resolve_dirs()

    # ── Setup toolchain (clone or download) ──────────────────
    clone_gcc_toolchains(cfg)

    variant = cfg.get("gcc_variant").lower()

    if variant == "mvaisakh":
        arm64_dir    = cfg.get("gcc_arm64_dir")
        arm32_dir    = cfg.get("gcc_arm32_dir")
        arm64_prefix = cfg.get("gcc_arm64_prefix")
        arm32_prefix = cfg.get("gcc_arm32_prefix")
        tc_label     = "mvaisakh-GCC-08032026"
        tc_desc      = "mvaisakh GCC (branch 08032026)"
    elif variant == "gnu":
        arm64_dir    = cfg.get("gnu_arm64_dir")
        arm32_dir    = cfg.get("gnu_arm32_dir")
        arm64_prefix = cfg.get("gnu_arm64_prefix")
        arm32_prefix = cfg.get("gnu_arm32_prefix")
        tc_label     = "GCC15.2-GNU"
        tc_desc      = f"ARM GNU Toolchain {cfg.get('gnu_gcc_version')}"
    else:
        die(f"Unknown gcc_variant '{variant}' — must be 'mvaisakh' or 'gnu'")

    if not Path(arm64_dir).exists():
        die(f"GCC ARM64 dir not found: {arm64_dir}")
    if not Path(arm32_dir).exists():
        die(f"GCC ARM32 dir not found: {arm32_dir}")

    ok(f"GCC variant    : {tc_desc}")
    ok(f"GCC ARM64 dir  → {arm64_dir}")
    ok(f"GCC ARM32 dir  → {arm32_dir}")
    info(f"ARM64 prefix   : {arm64_prefix}")
    info(f"ARM32 prefix   : {arm32_prefix}")

    arm64_gcc_bin = Path(arm64_dir) / "bin" / f"{arm64_prefix}gcc"
    try:
        r = _run([str(arm64_gcc_bin), "--version"],
                 capture_output=True, text=True)
        gcc_ver = r.stdout.splitlines()[0] if r.stdout else tc_desc
    except Exception:
        gcc_ver = tc_desc
    ok(f"Compiler: {gcc_ver}")

    pre_build(cfg)

    start_time = time.time()
    tg_send_msg(cfg,
        f"🔨 *Kernel build started*\n"
        f"Toolchain: {tc_desc}\n"
        f"Version: `{gcc_ver}`\n"
        f"Defconfig: `{cfg.get('defconfig')}`\n"
        f"Arch: `{cfg.get('arch')}`\n"
        f"Jobs: {cfg.get('jobs')}"
    )

    console.print(Rule(f"[accent]Building kernel — {tc_desc}[/accent]", style="cyan"))

    cmd = [
        "make", "-C", cfg.get("kernel_dir"),
        f"-j{cfg.get('jobs')}",
        f"ARCH={cfg.get('arch')}",
        f"SUBARCH={cfg.get('subarch')}",
        f"O={cfg.get('out_dir')}",
        f"CROSS_COMPILE={arm64_dir}/bin/{arm64_prefix}",
        f"CROSS_COMPILE_ARM32={arm32_dir}/bin/{arm32_prefix}",
        "Image.gz-dtb",
    ]
    if cfg.get("make_extra_flags"):
        cmd += cfg.get("make_extra_flags").split()

    rc = stream_make(cmd, cfg.get("log_file"))
    if rc != 0:
        die(f"Kernel compilation failed (see {cfg.get('log_file')})")

    post_build(cfg, start_time, tc_label)


# ============================================================
#  CLANG BUILD
# ============================================================
def build_clang(cfg: Config):
    cfg.resolve_dirs()

    if not cfg.get("clang_dir"):
        val = Prompt.ask(
            "[msg]>>[/msg] Path to Clang toolchain bin dir",
            console=console,
        )
        cfg.set("clang_dir", val)

    clang_dir = cfg.get("clang_dir")
    if not Path(clang_dir).exists():
        die(f"Clang dir not found: {clang_dir}")

    ld       = cfg.get("llvm_ld")       or f"{clang_dir}/ld.lld"
    ar       = cfg.get("llvm_ar")       or f"{clang_dir}/llvm-ar"
    nm       = cfg.get("llvm_nm")       or f"{clang_dir}/llvm-nm"
    objcopy  = cfg.get("llvm_objcopy")  or f"{clang_dir}/llvm-objcopy"
    objdump  = cfg.get("llvm_objdump")  or f"{clang_dir}/llvm-objdump"
    strip    = cfg.get("llvm_strip")    or f"{clang_dir}/llvm-strip"
    cc       = f"{clang_dir}/clang"
    if cfg.get("ccache") == "true":
        cc = f"ccache {cc}"

    ok(f"Clang dir      → {clang_dir}")
    info(f"CLANG_TRIPLE   : {cfg.get('clang_triple')}")
    info(f"ARM64 prefix   : {cfg.get('clang_arm64_prefix')}")
    info(f"ARM32 prefix   : {cfg.get('clang_arm32_prefix')}")

    try:
        r = _run([f"{clang_dir}/clang", "--version"],
                 capture_output=True, text=True)
        clang_ver = r.stdout.splitlines()[0] if r.stdout else "Clang (unknown)"
    except Exception:
        clang_ver = "Clang (unknown)"
    ok(f"Compiler: {clang_ver}")

    pre_build(cfg)
    start_time = time.time()

    tg_send_msg(cfg,
        f"🔨 *Kernel build started*\n"
        f"Toolchain: Clang\n"
        f"Version: `{clang_ver}`\n"
        f"Defconfig: `{cfg.get('defconfig')}`\n"
        f"Arch: `{cfg.get('arch')}`\n"
        f"Jobs: {cfg.get('jobs')}"
    )

    console.print(Rule("[accent]Building kernel — Clang[/accent]", style="cyan"))

    cmd = [
        "make", "-C", cfg.get("kernel_dir"),
        f"-j{cfg.get('jobs')}",
        f"ARCH={cfg.get('arch')}",
        f"SUBARCH={cfg.get('subarch')}",
        f"O={cfg.get('out_dir')}",
        f"CC={cc}",
        f"LD={ld}",
        f"AR={ar}",
        f"NM={nm}",
        f"OBJCOPY={objcopy}",
        f"OBJDUMP={objdump}",
        f"STRIP={strip}",
        f"CROSS_COMPILE={cfg.get('clang_arm64_prefix')}",
        f"CROSS_COMPILE_ARM32={cfg.get('clang_arm32_prefix')}",
        f"CLANG_TRIPLE={cfg.get('clang_triple')}",
        "Image.gz-dtb",
    ]
    if cfg.get("make_extra_flags"):
        cmd += cfg.get("make_extra_flags").split()

    rc = stream_make(cmd, cfg.get("log_file"))
    if rc != 0:
        die(f"Kernel compilation failed (see {cfg.get('log_file')})")

    post_build(cfg, start_time, "Clang")


# ============================================================
#  MENUCONFIG / SAVEDEFCONFIG
# ============================================================
def run_menuconfig(cfg: Config):
    cfg.resolve_dirs()
    set_env_vars(cfg)
    if not (Path(cfg.get("kernel_dir")) / ".git").exists():
        clone_sources(cfg)
    msg(f"Opening menuconfig (ARCH={cfg.get('arch')})...")
    subprocess.run([
        "make", "-C", cfg.get("kernel_dir"),
        f"O={cfg.get('out_dir')}",
        f"ARCH={cfg.get('arch')}", f"SUBARCH={cfg.get('subarch')}",
        "menuconfig",
    ])


def run_savedefconfig(cfg: Config):
    cfg.resolve_dirs()
    set_env_vars(cfg)
    msg(f"Running savedefconfig (ARCH={cfg.get('arch')})...")
    subprocess.run([
        "make", "-C", cfg.get("kernel_dir"),
        f"O={cfg.get('out_dir')}",
        f"ARCH={cfg.get('arch')}", f"SUBARCH={cfg.get('subarch')}",
        "savedefconfig",
    ])
    src = Path(cfg.get("out_dir")) / "defconfig"
    tgt = (Path(cfg.get("kernel_dir")) / "arch" /
           cfg.get("arch") / "configs" / cfg.get("defconfig"))
    if src.exists():
        shutil.copy2(str(src), str(tgt))
        ok(f"Saved → {tgt}")
    else:
        warn(f"savedefconfig ran but {src} not found")


# ============================================================
#  ARGUMENT PARSER
# ============================================================
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="baka-compile.py",
        description="Fully-customisable kernel build script",
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=False,
    )

    modes = p.add_argument_group("Build modes (pick one)")
    mx = modes.add_mutually_exclusive_group()
    mx.add_argument("--gcc",            action="store_const", const="gcc",    dest="mode")
    mx.add_argument("--clang",          action="store_const", const="clang",  dest="mode")
    mx.add_argument("--clone",          action="store_const", const="clone",  dest="mode")
    mx.add_argument("--clone-gcc",      action="store_const", const="clone-gcc", dest="mode")
    mx.add_argument("--menuconfig",     action="store_const", const="menuconfig", dest="mode")
    mx.add_argument("--savedefconfig",  action="store_const", const="savedefconfig", dest="mode")
    mx.add_argument("--save-config",    action="store_const", const="save-config", dest="mode")
    mx.add_argument("--show-config",    action="store_const", const="show-config", dest="mode")

    misc = p.add_argument_group("Misc")
    misc.add_argument("-h", "--help",    action="store_true")
    misc.add_argument("--version",       action="store_true")

    r = p.add_argument_group("Repo / directory options")
    r.add_argument("--kernel-repo",    dest="kernel_repo")
    r.add_argument("--kernel-branch",  dest="kernel_branch")
    r.add_argument("--ak3-repo",       dest="ak3_repo")
    r.add_argument("--ak3-branch",     dest="ak3_branch")
    r.add_argument("--base-dir",       dest="base_dir")
    r.add_argument("--kernel-dir",     dest="kernel_dir")
    r.add_argument("--ak3-dir",        dest="ak3_dir")
    r.add_argument("--out-dir",        dest="out_dir")
    r.add_argument("--zip-dir",        dest="zip_dir")
    r.add_argument("--log-file",       dest="log_file")
    r.add_argument("--tc-dir",         dest="tc_dir")

    bi = p.add_argument_group("Build identity")
    bi.add_argument("--defconfig",     dest="defconfig")
    bi.add_argument("--arch",          dest="arch")
    bi.add_argument("--subarch",       dest="subarch")
    bi.add_argument("--user",          dest="kbuild_build_user")
    bi.add_argument("--host",          dest="kbuild_build_host")
    bi.add_argument("--kernel-name",   dest="kernel_name")
    bi.add_argument("--device-name",   dest="device_name")
    bi.add_argument("--zip-template",  dest="zip_name_template")

    bo = p.add_argument_group("Build options")
    bo.add_argument("--jobs", "-j",    dest="jobs")
    bo.add_argument("--make-flags",    dest="make_extra_flags")
    bo.add_argument("--clone-depth",   dest="clone_depth")
    bo.add_argument("--clean",         dest="clean_build",  action="store_const", const="true")
    bo.add_argument("--ccache",        dest="ccache",       action="store_const", const="true")
    bo.add_argument("--skip-zip",      dest="skip_ak3",     action="store_const", const="true")
    bo.add_argument("--no-notify",     dest="tg_notify",    action="store_const", const="false")

    gcc = p.add_argument_group("GCC toolchain options")
    gcc.add_argument("--no-gcc-clone",    dest="gcc_auto_clone", action="store_const", const="false")
    gcc.add_argument("--gcc-variant",     dest="gcc_variant",
                     help="'mvaisakh' (release tarball 08032026) or 'gnu' (GCC 15.2.Rel1 tarball)")
    gcc.add_argument("--gcc-arm64-url",   dest="gcc_arm64_url")
    gcc.add_argument("--gcc-arm32-url",   dest="gcc_arm32_url")
    gcc.add_argument("--gcc-arm64-dir",   dest="gcc_arm64_dir")
    gcc.add_argument("--gcc-arm32-dir",   dest="gcc_arm32_dir")
    gcc.add_argument("--gcc-arm64-pfx",   dest="gcc_arm64_prefix")
    gcc.add_argument("--gcc-arm32-pfx",   dest="gcc_arm32_prefix")
    gcc.add_argument("--gnu-arm64-url",   dest="gnu_arm64_url")
    gcc.add_argument("--gnu-arm32-url",   dest="gnu_arm32_url")
    gcc.add_argument("--gnu-arm64-dir",   dest="gnu_arm64_dir")
    gcc.add_argument("--gnu-arm32-dir",   dest="gnu_arm32_dir")
    gcc.add_argument("--gnu-arm64-pfx",   dest="gnu_arm64_prefix")
    gcc.add_argument("--gnu-arm32-pfx",   dest="gnu_arm32_prefix")
    gcc.add_argument("--gnu-gcc-version", dest="gnu_gcc_version")

    cl = p.add_argument_group("Clang options")
    cl.add_argument("--clang-dir",       dest="clang_dir")
    cl.add_argument("--clang-triple",    dest="clang_triple")
    cl.add_argument("--clang-arm64-pfx", dest="clang_arm64_prefix")
    cl.add_argument("--clang-arm32-pfx", dest="clang_arm32_prefix")
    cl.add_argument("--llvm-ld",         dest="llvm_ld")
    cl.add_argument("--llvm-ar",         dest="llvm_ar")
    cl.add_argument("--llvm-nm",         dest="llvm_nm")
    cl.add_argument("--llvm-objcopy",    dest="llvm_objcopy")
    cl.add_argument("--llvm-objdump",    dest="llvm_objdump")
    cl.add_argument("--llvm-strip",      dest="llvm_strip")

    cred = p.add_argument_group("Credentials")
    cred.add_argument("--gh-token",  dest="gh_token")
    cred.add_argument("--tg-token",  dest="tg_bot_token")
    cred.add_argument("--tg-chat",   dest="tg_chat_id")

    return p


def print_help():
    console.print(Panel(
        Text.from_markup(
            "[header]baka-compile[/header] [dim]— fully-customisable kernel build script[/dim]\n\n"
            "[accent]Usage:[/accent]  baka-compile.py [bold][build-mode][/bold] [options...]\n\n"

            "[accent]Build modes:[/accent]\n"
            "  [val]--gcc[/val]               Build with GCC (mvaisakh 08032026 or GNU 15.2 — see variants below)\n"
            "  [val]--clang[/val]             Build with Clang toolchain\n"
            "  [val]--clone[/val]             Clone kernel + AnyKernel3 only\n"
            "  [val]--clone-gcc[/val]         Clone GCC 15 toolchains only\n"
            "  [val]--menuconfig[/val]        Open kernel menuconfig\n"
            "  [val]--savedefconfig[/val]     Run savedefconfig\n"
            "  [val]--save-config[/val]       Write settings to build.cfg\n"
            "  [val]--show-config[/val]       Print resolved configuration\n\n"

            "[accent]Key options:[/accent]\n"
            "  [val]--defconfig[/val] [dim]<name>[/dim]     Defconfig to use\n"
            "  [val]--arch[/val] [dim]<arch>[/dim]          Target arch  (default: arm64)\n"
            "  [val]--jobs / -j[/val] [dim]<n>[/dim]        Parallel jobs\n"
            "  [val]--tc-dir[/val] [dim]<path>[/dim]        Toolchain base dir\n"
            "  [val]--no-gcc-clone[/val]      Disable GCC auto-clone\n"
            "  [val]--clean[/val]             make clean before build\n"
            "  [val]--ccache[/val]            Wrap compiler with ccache\n"
            "  [val]--skip-zip[/val]          Skip AnyKernel3 packaging\n"
            "  [val]--no-notify[/val]         Disable Telegram notifications\n\n"

            "[accent]Config file:[/accent]\n"
            "  Default path : build.cfg  (next to this script)\n"
            "  Custom path  : BAKA_CONFIG=/path/to/file.cfg baka-compile.py ...\n\n"

            "[accent]GCC variants:[/accent]\n"
            "  [val]--gcc-variant mvaisakh[/val]   download pre-built release tarballs [val]08032026[/val] (default)\n"
            "    ARM64: [dim]eva-gcc-arm64-08032026.xz[/dim]  (github.com/mvaisakh/gcc-build)\n"
            "    ARM32: [dim]eva-gcc-arm-08032026.xz[/dim]\n"
            "    Prefixes: [dim]aarch64-elf-[/dim] / [dim]arm-eabi-[/dim]\n"
            "    Override URLs with [val]--gcc-arm64-url[/val] / [val]--gcc-arm32-url[/val]\n\n"
            "  [val]--gcc-variant gnu[/val]         download ARM GNU Toolchain [val]15.2.Rel1[/val] tarball\n"
            "    Source: [dim]developer.arm.com[/dim] (aarch64-none-linux-gnu + arm-none-linux-gnueabihf)\n"
            "    Prefixes: [dim]aarch64-none-linux-gnu-[/dim] / [dim]arm-none-linux-gnueabihf-[/dim]\n"
            "  Use [val]--gnu-gcc-version[/val] to pin a different GNU release (default: 15.2.rel1).\n",
        ),
        title=f"[banner] baka-compile v{SCRIPT_VERSION} [/banner]",
        border_style="cyan",
        padding=(1, 2),
    ))


# ============================================================
#  ENTRY POINT
# ============================================================
def main():
    cfg_path = os.environ.get(
        "BAKA_CONFIG",
        str(Path(__file__).parent / "build.cfg")
    )

    parser  = build_parser()
    ns, _   = parser.parse_known_args()

    print_banner()

    if ns.version:
        console.print(f"[header]baka-compile[/header] [val]v{SCRIPT_VERSION}[/val]")
        sys.exit(0)

    if ns.help or ns.mode is None:
        print_help()
        sys.exit(0)

    cfg = Config(cfg_path)
    cfg.apply_args(ns)

    mode = ns.mode
    console.print(
        Panel(
            f"[accent]Mode:[/accent] [val]{mode}[/val]",
            border_style="dim cyan", expand=False, padding=(0, 2)
        )
    )
    console.print()

    match mode:
        case "gcc":
            build_gcc(cfg)
        case "clang":
            build_clang(cfg)
        case "clone":
            cfg.resolve_dirs()
            clone_sources(cfg)
        case "clone-gcc":
            cfg.resolve_dirs()
            clone_gcc_toolchains(cfg)
        case "menuconfig":
            run_menuconfig(cfg)
        case "savedefconfig":
            run_savedefconfig(cfg)
        case "save-config":
            cfg.resolve_dirs()
            cfg.save()
        case "show-config":
            show_config(cfg)
        case _:
            die(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()