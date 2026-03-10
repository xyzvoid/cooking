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
    # Use python3 to safely build JSON — avoids shell quoting fragility
    local tag_json
    tag_json=$(python3 - <<PYEOF
import json
print(json.dumps({"ref": "refs/tags/${tag}", "sha": "${sha}"}))
PYEOF
)
    curl -fsSL -X POST \
        -H "Authorization: token ${GH_TOKEN}" \
        -H "Accept: application/vnd.github.v3+json" \
        -H "Content-Type: application/json" \
        "${api_base}/git/refs" \
        -d "$tag_json" \
        -o /dev/null 2>/dev/null \
        || log_warn "Tag creation failed (may already exist) — continuing"

    # ── Build release body (plain text, python will JSON-encode it) ───────────
    local changelog
    changelog=$(git -C "$KERNEL_DIR" log --oneline -10 2>/dev/null || echo "N/A")

    local body_text
    body_text="## ${release_name}

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
${changelog}"

    # ── Create the release (python3 handles all JSON encoding safely) ─────────
    log "Publishing release: ${release_name}…"
    local release_json
    release_json=$(python3 - <<PYEOF
import json, sys

body = sys.stdin.read()
payload = {
    "tag_name":         "${tag}",
    "name":             "${release_name}",
    "body":             body,
    "draft":            False,
    "prerelease":       False,
    "target_commitish": "${GH_RELEASE_BRANCH}"
}
print(json.dumps(payload))
PYEOF
<<< "$body_text")

    local release_resp
    release_resp=$(curl -fsSL -X POST \
        -H "Authorization: token ${GH_TOKEN}" \
        -H "Accept: application/vnd.github.v3+json" \
        -H "Content-Type: application/json" \
        "${api_base}/releases" \
        -d "$release_json") \
        || die "GitHub release API call failed"

    # ── Parse upload URL and html URL ─────────────────────────────────────────
    local upload_url html_url
    upload_url=$(python3 -c \
        "import sys,json; d=json.load(sys.stdin); print(d.get('upload_url','').split('{')[0])" \
        <<< "$release_resp" 2>/dev/null || true)
    html_url=$(python3 -c \
        "import sys,json; print(json.load(sys.stdin).get('html_url',''))" \
        <<< "$release_resp" 2>/dev/null || true)

    if [[ -z "$upload_url" ]]; then
        log_warn "Could not parse upload_url from GitHub response"
        log_warn "Response: $(echo "$release_resp" | head -c 400)"
        return 1
    fi

    # ── Upload zip asset ──────────────────────────────────────────────────────
    log "Uploading ${ZIP_NAME} to GitHub release…"
    # URL-encode the zip name for the query string
    local encoded_name
    encoded_name=$(python3 -c \
        "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1]))" \
        "${ZIP_NAME}")

    curl -fsSL -X POST \
        -H "Authorization: token ${GH_TOKEN}" \
        -H "Content-Type: application/zip" \
        --data-binary "@${ZIP_PATH}" \
        "${upload_url}?name=${encoded_name}&label=${encoded_name}" \
        -o /dev/null \
        || log_warn "Asset upload failed"

    GH_RELEASE_URL="$html_url"
    log_ok "Release published: ${GH_RELEASE_URL}"
}
