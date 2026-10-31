#!/usr/bin/env bash
# ============================================================================
# (SheepFox) Zen browser — brand and patch the fetched upstream source tree
#
#   ./mozbuild/scripts/apply-patches.sh [--source DIR] [--no-patches] [--force]
#
# Steps:
#   1. Recompiles config/modules/*.js -> config/user.js + config/autoconfig/sheepfox.cfg
#   2. Verifies the generated artifacts are in sync (fails loudly if not)
#   3. Injects branding/sheepfox into <source>/browser/branding/sheepfox
#   4. Stages the runtime config (AutoConfig + SheepShields policies) for packaging
#   5. Applies patches/series in order with `git apply`, falling back to `patch`
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SOURCE_DIR="${SHEEPFOX_SRC_DIR:-${REPO_ROOT}/mozbuild/firefox-src}"
STAGING_DIR="${REPO_ROOT}/mozbuild/staging"
PATCH_DIR="${REPO_ROOT}/patches"
SERIES_FILE="${PATCH_DIR}/series"
MARKER="${SOURCE_DIR}/.sheepfox-patched"

APPLY_PATCHES=1
FORCE=0

step() { printf '\n==> %s\n' "$*"; }
info() { printf '  [info]  %s\n' "$*"; }
warn() { printf '  [warn]  %s\n' "$*"; }
die()  { printf '  [error] %s\n' "$*" >&2; exit 1; }

while [ "$#" -gt 0 ]; do
  case "$1" in
    --source)     SOURCE_DIR="${2:-}"; shift ;;
    --no-patches) APPLY_PATCHES=0 ;;
    --force)      FORCE=1 ;;
    -h|--help)    sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown argument: $1 (try --help)" ;;
  esac
  shift
done

[ -n "$SOURCE_DIR" ] || die "--source requires a directory"
[ -d "$SOURCE_DIR" ] || die "source tree not found: ${SOURCE_DIR} (run: make fetch-source)"
[ -x "${SOURCE_DIR}/mach" ] || die "${SOURCE_DIR} does not look like a Firefox tree (no ./mach)"

# ---------------------------------------------------------------- 1. configs
step "Compiling modular preferences"
python3 "${REPO_ROOT}/mozbuild/scripts/build-configs.py"

step "Verifying generated configuration is in sync"
python3 "${REPO_ROOT}/mozbuild/scripts/build-configs.py" --check

# ---------------------------------------------------------------- 2. branding
step "Injecting SheepFox branding"
BRAND_SRC="${REPO_ROOT}/branding/sheepfox"
BRAND_DEST="${SOURCE_DIR}/browser/branding/sheepfox"
[ -d "$BRAND_SRC" ] || die "branding assets missing: ${BRAND_SRC}"
rm -rf "$BRAND_DEST"
mkdir -p "$BRAND_DEST"
cp -R "${BRAND_SRC}/." "$BRAND_DEST/"
chmod +x "${BRAND_DEST}/configure.sh" 2>/dev/null || true
info "branding -> ${BRAND_DEST}"

# ---------------------------------------------------------------- 3. staging
step "Staging runtime configuration (AutoConfig + SheepShields)"
rm -rf "$STAGING_DIR"
mkdir -p "${STAGING_DIR}/defaults/pref" "${STAGING_DIR}/distribution"
cp "${REPO_ROOT}/config/autoconfig/sheepfox.cfg"                      "${STAGING_DIR}/sheepfox.cfg"
cp "${REPO_ROOT}/config/autoconfig/defaults/pref/local-settings.js"   "${STAGING_DIR}/defaults/pref/local-settings.js"
cp "${REPO_ROOT}/config/distribution/policies.json"                   "${STAGING_DIR}/distribution/policies.json"
info "staged -> ${STAGING_DIR}"

# ---------------------------------------------------------------- 4. patches
if [ "$APPLY_PATCHES" -eq 0 ]; then
  info "patch application skipped (--no-patches)"
  exit 0
fi

if [ -f "$MARKER" ] && [ "$FORCE" -ne 1 ]; then
  info "patches already applied ($(cat "$MARKER")); use --force to re-apply"
  exit 0
fi

[ -f "$SERIES_FILE" ] || die "patch series file missing: ${SERIES_FILE}"

step "Applying patch series"
applied=0
while IFS= read -r raw_line; do
  line="${raw_line%%#*}"
  line="$(printf '%s' "$line" | tr -d '[:space:]')"
  [ -n "$line" ] || continue
  patch_path="${PATCH_DIR}/${line}"
  [ -f "$patch_path" ] || die "series lists a missing patch: ${line}"

  if git -C "$SOURCE_DIR" apply --check -p1 "$patch_path" 2>/dev/null; then
    git -C "$SOURCE_DIR" apply -p1 "$patch_path"
  elif command -v patch >/dev/null 2>&1 \
       && patch -d "$SOURCE_DIR" -p1 --forward --batch --silent --dry-run < "$patch_path"; then
    patch -d "$SOURCE_DIR" -p1 --forward --batch --silent < "$patch_path"
  else
    die "failed to apply ${line}.
       The tree in ${SOURCE_DIR} does not match the pinned version in
       mozbuild/firefox-version.json. Delete it and run 'make fetch-source'."
  fi
  info "applied ${line}"
  applied=$((applied + 1))
done < "$SERIES_FILE"

printf 'applied %s patches at %s\n' "$applied" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$MARKER"

step "Done"
info "patched tree : ${SOURCE_DIR}"
info "next         : make build-browser"
