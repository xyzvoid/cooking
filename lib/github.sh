#!/usr/bin/env bash
# lib/github.sh — Create GitHub release and upload zip asset
# Sourced by build.sh — do not execute directly.

GH_RELEASE_URL=""

gh_create_release() {
    if [[ -z "${GH_TOKEN:-}" ]]; then
        log_warn "GH_TOKEN not set — skipping GitHub release"
        return 0
    fi

    log_step "Creating GitHub release"

    local tag="kernel-${KERNEL_VERSION}-${DATETIME}"
    local release_name="${KERNEL_NAME}-${KERNEL_VERSION}-${DATETIME}"
    local api_base="https://api.github.com/repos/${GH_RELEASE_REPO}"

    # ── Get HEAD commit SHA ───────────────────────────────────────────────────
    local sha
    sha=$(git -C "$KERNEL_DIR" rev-parse HEAD 2>/dev/null) \
        || die "Could not determine HEAD SHA"

    # ── Create the tag ref ────────────────────────────────────────────────────
    log "Creating tag: ${tag}…"
    local tag_resp
    tag_resp=$(curl -fsSL -X POST \
        -H "Authorization: token ${GH_TOKEN}" \
        -H "Accept: application/vnd.github.v3+json" \
        "${api_base}/git/refs" \
        -d "{\"ref\":\"refs/tags/${tag}\",\"sha\":\"${sha}\"}" \
        2>/dev/null) || log_warn "Tag may already exist — continuing"

    # ── Build the release body ────────────────────────────────────────────────
    local body
    body=$(cat <<BODY
## ${release_name}

| Field | Value |
|---|---|
| **Kernel Version** | \`${KERNEL_VERSION}\` |
| **Defconfig** | \`${DEFCONFIG}\` |
| **Toolchain** | \`${TOOLCHAIN}\` |
| **Arch** | \`${ARCH}\` |
| **Build Time** | $(( BUILD_ELAPSED/60 ))m $(( BUILD_ELAPSED%60 ))s |
| **Built At** | $(date -u '+%Y-%m-%d %H:%M:%S UTC') |

### Installation
Flash via TWRP or any AnyKernel3-compatible recovery.

### Changelog
$(git -C "$KERNEL_DIR" log --oneline -10 2>/dev/null || echo "N/A")
BODY
)

    # ── Create the release ────────────────────────────────────────────────────
    log "Publishing release: ${release_name}…"
    local release_resp
    release_resp=$(curl -fsSL -X POST \
        -H "Authorization: token ${GH_TOKEN}" \
        -H "Accept: application/vnd.github.v3+json" \
        "${api_base}/releases" \
        -d "$(python3 -c "
import json, sys
print(json.dumps({
    'tag_name':         '${tag}',
    'name':             '${release_name}',
    'body':             sys.stdin.read(),
    'draft':            False,
    'prerelease':       False,
    'target_commitish': '${GH_RELEASE_BRANCH}'
}))" <<< "$body")") || die "GitHub release creation failed"

    # ── Parse upload URL and release URL ─────────────────────────────────────
    local upload_url html_url
    upload_url=$(python3 -c \
        "import sys,json; d=json.load(sys.stdin); print(d['upload_url'].split('{')[0])" \
        <<< "$release_resp" 2>/dev/null || echo "")
    html_url=$(python3 -c \
        "import sys,json; print(json.load(sys.stdin)['html_url'])" \
        <<< "$release_resp" 2>/dev/null || echo "")

    if [[ -z "$upload_url" ]]; then
        log_warn "Could not parse upload_url from GitHub API response"
        log_warn "Response snippet: $(echo "$release_resp" | head -c 500)"
        return 1
    fi

    # ── Upload zip asset ──────────────────────────────────────────────────────
    log "Uploading ${ZIP_NAME} to GitHub release…"
    curl -fsSL -X POST \
        -H "Authorization: token ${GH_TOKEN}" \
        -H "Content-Type: application/zip" \
        --data-binary "@${ZIP_PATH}" \
        "${upload_url}?name=${ZIP_NAME}&label=${ZIP_NAME}" \
        -o /dev/null || log_warn "Asset upload failed"

    GH_RELEASE_URL="$html_url"
    log_ok "Release published: ${GH_RELEASE_URL}"
}
