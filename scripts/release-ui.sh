#!/usr/bin/env bash
# Build the browser UI locally and publish it to GitHub Pages.
#
# No CI involved: GitHub Pages happily serves a branch you push by hand.
# Run this whenever you want to release the UI:
#
#     ./scripts/release-ui.sh
#
# What it does:
#   1. trunk-builds ui/ in release mode with the Pages subpath baked in
#      (the site lives at https://<org>.github.io/<repo>/, so asset URLs
#      must be rooted at /<repo>/ — that's the --public-url flag)
#   2. snapshots ui/dist onto the `gh-pages` branch (orphan history,
#      force-pushed — the branch is a build artifact, not source)
#
# One-time repo setting (after the first push of gh-pages):
#   GitHub → repo → Settings → Pages → "Build and deployment" →
#   Source: "Deploy from a branch" → Branch: gh-pages, folder: / (root)
set -euo pipefail
cd "$(dirname "$0")/.."

# rustup toolchain, NOT homebrew cargo (homebrew's lacks the wasm target)
export PATH="$HOME/.cargo/bin:$PATH"

REPO_SLUG="$(basename -s .git "$(git remote get-url origin)")"

# Every release bumps the UI patch version. The version is compiled into the
# app (footer: "build vX.Y.Z"), and trunk content-hashes all assets, so a
# fresh deploy is visibly and mechanically distinct from any cached one —
# the only residual staleness is GitHub Pages' ~10-minute index.html TTL.
NEW_VERSION=$(python3 - <<'PY'
import pathlib, re
path = pathlib.Path("ui/Cargo.toml")
text = path.read_text()
m = re.search(r'^version = "(\d+)\.(\d+)\.(\d+)"', text, re.M)
major, minor, patch = map(int, m.groups())
new = f"{major}.{minor}.{patch + 1}"
path.write_text(text.replace(m.group(0), f'version = "{new}"', 1))
print(new)
PY
)
echo "==> release version: v${NEW_VERSION}"

echo "==> building ui/ (public-url /${REPO_SLUG}/)"
(cd ui && trunk build --release --public-url "/${REPO_SLUG}/")

echo "==> committing version bump"
git add ui/Cargo.toml ui/Cargo.lock
git commit -qm "Release UI v${NEW_VERSION}"
git push -q origin HEAD

echo "==> publishing ui/dist to gh-pages"
TMP=$(mktemp -d)
cleanup() { git worktree remove --force "$TMP" 2>/dev/null || rm -rf "$TMP"; }
trap cleanup EXIT

git worktree add --detach "$TMP" >/dev/null
# --orphan refuses if the branch already exists locally (e.g. from a prior
# release) — drop the stale local ref first; the push below recreates it.
git branch -D gh-pages >/dev/null 2>&1 || true
git -C "$TMP" checkout --orphan gh-pages >/dev/null 2>&1
git -C "$TMP" rm -rfq . 2>/dev/null || true
cp -R ui/dist/. "$TMP/"
touch "$TMP/.nojekyll"   # disable Jekyll so every generated file is served as-is
git -C "$TMP" add -A
git -C "$TMP" commit -qm "Deploy UI $(date -u +%Y-%m-%dT%H:%MZ) (source: $(git rev-parse --short HEAD))"
git -C "$TMP" push -f origin gh-pages

echo "==> published: https://$(git remote get-url origin \
  | sed -E 's#(https://github.com/|git@github.com:)([^/]+)/.*#\2#' \
  | tr '[:upper:]' '[:lower:]').github.io/${REPO_SLUG}/"
