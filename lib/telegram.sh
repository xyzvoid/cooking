#!/usr/bin/env bash
# lib/telegram.sh — Telegram Bot API helpers
# Sourced by build.sh — do not execute directly.

_TG_MSG_ID=""          # message_id of the "live status" message

# ── Guard ─────────────────────────────────────────────────────────────────────
_tg_enabled() {
    [[ -n "${TG_BOT_TOKEN:-}" && -n "${TG_CHAT_ID:-}" ]]
}

# ── Send a new text message ───────────────────────────────────────────────────
tg_send_message() {
    _tg_enabled || return 0
    local text="$1"
    curl -fsSL -X POST \
        "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage" \
        --data-urlencode "chat_id=${TG_CHAT_ID}" \
        --data-urlencode "text=${text}" \
        -d "parse_mode=Markdown" \
        -d "disable_web_page_preview=true" \
        2>/dev/null || { log_warn "Telegram sendMessage failed"; return 0; }
}

# ── Internal: send and capture the message_id ────────────────────────────────
_tg_send_and_capture_id() {
    _tg_enabled || return 0
    local text="$1"
    local resp
    resp=$(curl -fsSL -X POST \
        "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage" \
        --data-urlencode "chat_id=${TG_CHAT_ID}" \
        --data-urlencode "text=${text}" \
        -d "parse_mode=Markdown" \
        -d "disable_web_page_preview=true" \
        2>/dev/null) || { log_warn "Telegram sendMessage failed"; return 0; }

    # Parse message_id from response and store in global
    local mid
    mid=$(python3 -c \
        "import sys,json; print(json.loads(sys.stdin.read()).get('result',{}).get('message_id',''))" \
        <<< "$resp" 2>/dev/null || true)
    [[ -n "$mid" ]] && _TG_MSG_ID="$mid"
}

# ── Send or edit the live-status message (edits in-place after first call) ───
tg_send_or_edit() {
    _tg_enabled || return 0
    local text="$1"

    if [[ -z "$_TG_MSG_ID" ]]; then
        # First call — send a new message and capture its ID
        _tg_send_and_capture_id "$text"
    else
        curl -fsSL -X POST \
            "https://api.telegram.org/bot${TG_BOT_TOKEN}/editMessageText" \
            -d "chat_id=${TG_CHAT_ID}" \
            -d "message_id=${_TG_MSG_ID}" \
            --data-urlencode "text=${text}" \
            -d "parse_mode=Markdown" \
            -d "disable_web_page_preview=true" \
            -o /dev/null 2>/dev/null || log_warn "Telegram editMessage failed"
    fi
}

# ── Upload a file (document) ─────────────────────────────────────────────────
tg_upload_file() {
    _tg_enabled || return 0
    local filepath="$1"
    local caption="${2:-}"
    [[ -f "$filepath" ]] || { log_warn "tg_upload_file: file not found: ${filepath}"; return 0; }
    log "Uploading $(basename "$filepath") to Telegram…"
    curl -fsSL -X POST \
        "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendDocument" \
        -F "chat_id=${TG_CHAT_ID}" \
        -F "document=@${filepath}" \
        -F "caption=${caption}" \
        -F "parse_mode=Markdown" \
        -o /dev/null 2>/dev/null || log_warn "Telegram upload failed"
}

# ── Upload a log file (inline if small, as document if large) ────────────────
tg_upload_log() {
    _tg_enabled || return 0
    local logfile="$1"
    local caption="${2:-Build log}"
    [[ -f "$logfile" ]] || return 0

    local size; size=$(wc -c < "$logfile")
    if (( size > 50000 )); then
        tg_upload_file "$logfile" "📋 ${caption}"
    else
        local tail_text; tail_text=$(tail -c 3500 "$logfile")
        tg_send_message "📋 *${caption}*\n\`\`\`\n${tail_text}\n\`\`\`"
    fi
}

# ── Notify build started ──────────────────────────────────────────────────────
tg_notify_start() {
    _tg_enabled || return 0
    tg_send_or_edit "⏳ *Kernel Build Queued*
━━━━━━━━━━━━━━━━━━━
🔧 Defconfig : \`${DEFCONFIG}\`
⚙️ Toolchain : \`${TOOLCHAIN}\`
🧵 Jobs      : \`${JOBS}\`
📅 Time      : \`$(date '+%Y-%m-%d %H:%M:%S')\`
━━━━━━━━━━━━━━━━━━━
_Preparing environment…_"
}

# ── Upload zip + log after build ─────────────────────────────────────────────
tg_upload_artifacts() {
    _tg_enabled || return 0

    tg_upload_file "$ZIP_PATH" \
        "🔥 *${ZIP_NAME}*
📦 \`${KERNEL_VERSION}\` | ⚙️ \`${TOOLCHAIN}\` | ⏱ $(( BUILD_ELAPSED/60 ))m $(( BUILD_ELAPSED%60 ))s"

    if [[ -n "${BUILD_LOG:-}" && -f "${BUILD_LOG:-}" ]]; then
        tg_upload_log "$BUILD_LOG" "Build log — ${ZIP_NAME}"
    fi
}

# ── Final done message ────────────────────────────────────────────────────────
tg_notify_done() {
    _tg_enabled || return 0

    local gh_line=""
    [[ -n "${GH_RELEASE_URL:-}" ]] && gh_line="\n🔗 GitHub  : ${GH_RELEASE_URL}"

    tg_send_or_edit "🎉 *Build Complete!*
━━━━━━━━━━━━━━━━━━━
📦 Version  : \`${KERNEL_VERSION}\`
🗜  ZIP     : \`${ZIP_NAME}\`
⏱  Time    : $(( BUILD_ELAPSED/60 ))m $(( BUILD_ELAPSED%60 ))s
⚙️ Toolchain: \`${TOOLCHAIN}\`${gh_line}
━━━━━━━━━━━━━━━━━━━"
}
