#!/usr/bin/env bash
# ============================================================================
# (SheepFox) Firefox — fetch and verify the pinned upstream Firefox sources
#
#   ./mozbuild/scripts/fetch-source.sh [--force] [--dry-run]
#
# * Reads the pinned release from mozbuild/firefox-version.json
# * Downloads source/firefox-<version>.source.tar.xz and Mozilla's SHA512SUMS
# * Verifies the tarball against SHA512SUMS (or SHEEPFOX_EXPECTED_SHA512)
# * Extracts it to mozbuild/firefox-src/
#
# Environment:
#   SHEEPFOX_MIRROR            alternate mirror root (same layout)
#   SHEEPFOX_EXPECTED_SHA512   pin a literal digest instead of trusting the sums
#   SHEEPFOX_SRC_DIR           extraction directory (default: mozbuild/firefox-src)
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
MANIFEST="${REPO_ROOT}/mozbuild/firefox-version.json"
CACHE_DIR="${REPO_ROOT}/mozbuild"
SRC_DIR="${SHEEPFOX_SRC_DIR:-${REPO_ROOT}/mozbuild/firefox-src}"
MIRROR="${SHEEPFOX_MIRROR:-https://archive.mozilla.org/pub/firefox/releases}"

FORCE=0
DRY_RUN=0

info() { printf '  [info]  %s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }
die()  { printf '  [error] %s\n' "$*" >&2; exit 1; }

usage() {
  sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --force)   FORCE=1 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1 (try --help)" ;;
  esac
  shift
done

[ -f "$MANIFEST" ] || die "manifest not found: $MANIFEST"
command -v python3 >/dev/null 2>&1 || die "python3 is required"

step "Reading pinned release manifest"
eval "$(
  python3 - "$MANIFEST" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    data = json.load(handle)
def emit(key, value):
    if value is None:
        value = ""
    print(f"{key}={json.dumps(str(value))}")
emit("VERSION", data["version"])
emit("ARCHIVE_NAME", data["source_archive_name"].replace("{version}", data["version"]))
emit("SOURCE_ROOT", data["source_root"].replace("{version}", data["version"]))
emit("SOURCE_URL", data["source_url_template"].replace("{version}", data["version"]))
emit("SUMS_URL", data["sha512sums_url_template"].replace("{version}", data["version"]))
emit("PINNED_SHA", data.get("source_sha512") or "")
emit("MIN_DISK_GB", data.get("min_free_disk_gb") or 0)
PY
)"

info "version      : Firefox ${VERSION}"
info "archive      : ${ARCHIVE_NAME}"
info "source URL   : ${SOURCE_URL}"
info "destination  : ${SRC_DIR}"

# ---------------------------------------------------------------- disk space
if [ "${MIN_DISK_GB}" -gt 0 ] && command -v df >/dev/null 2>&1; then
  FREE_GB="$(df -Pk "${CACHE_DIR}" 2>/dev/null | awk 'NR==2 {print int($4/1048576)}')"
  if [ -n "${FREE_GB:-}" ] && [ "${FREE_GB}" -lt "${MIN_DISK_GB}" ]; then
    die "only ${FREE_GB} GB free; a Firefox build needs ~${MIN_DISK_GB} GB"
  fi
fi

if [ -f "${SRC_DIR}/.sheepfox-source" ] && [ "$FORCE" -ne 1 ]; then
  EXISTING="$(cat "${SRC_DIR}/.sheepfox-source")"
  if [ "$EXISTING" = "$VERSION" ]; then
    info "already fetched (${SRC_DIR}); use --force to re-download"
    exit 0
  fi
  info "existing tree is ${EXISTING}, re-fetching ${VERSION}"
fi

# ---------------------------------------------------------------- downloader
fetch() {
  local url="$1" dest="$2"
  if [ "$DRY_RUN" -eq 1 ]; then
    info "would download ${url} -> ${dest}"
    return 0
  fi
  if command -v curl >/dev/null 2>&1; then
    curl --fail --location --retry 3 --retry-delay 2 --progress-bar -o "$dest" "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget --tries=3 --show-progress -O "$dest" "$url"
  else
    die "curl or wget is required"
  fi
}

TARBALL="${CACHE_DIR}/${ARCHIVE_NAME}"
SUMS_FILE="${CACHE_DIR}/SHA512SUMS"

mkdir -p "$CACHE_DIR"

step "Downloading source archive"
DEFAULT_MIRROR="https://archive.mozilla.org/pub/firefox/releases"
if [ "$MIRROR" != "$DEFAULT_MIRROR" ]; then
  SOURCE_URL="${MIRROR}${SOURCE_URL#"$DEFAULT_MIRROR"}"
  SUMS_URL="${MIRROR}${SUMS_URL#"$DEFAULT_MIRROR"}"
  info "mirror       : ${MIRROR}"
fi

if [ "$FORCE" -eq 1 ] || [ ! -f "$TARBALL" ]; then
  fetch "$SOURCE_URL" "$TARBALL"
else
  info "using cached ${TARBALL} (use --force to re-download)"
fi

if [ "$DRY_RUN" -eq 1 ]; then
  info "dry-run: would verify SHA-512 against ${SUMS_URL} and extract to ${SRC_DIR}"
  exit 0
fi

step "Verifying SHA-512"
EXPECTED="${SHEEPFOX_EXPECTED_SHA512:-${PINNED_SHA}}"
if [ -z "$EXPECTED" ]; then
  fetch "$SUMS_URL" "$SUMS_FILE"
  EXPECTED="$(awk -v want="$ARCHIVE_NAME" '$2 ~ want {print $1; exit}' "$SUMS_FILE" || true)"
fi
[ -n "$EXPECTED" ] || die "could not resolve a SHA-512 for ${ARCHIVE_NAME} from ${SUMS_URL}"

case "$(uname -s)" in
  Darwin) ACTUAL="$(shasum -a 512 "$TARBALL" | awk '{print $1}')" ;;
  *)      ACTUAL="$(sha512sum "$TARBALL" | awk '{print $1}')" ;;
esac

if [ "$ACTUAL" != "$EXPECTED" ]; then
  rm -f "$TARBALL"
  die "SHA-512 mismatch for ${ARCHIVE_NAME}
       expected: ${EXPECTED}
       actual  : ${ACTUAL}
       The download was corrupt or tampered with; the archive has been deleted."
fi
info "SHA-512 OK (${ACTUAL:0:16}…)"

step "Extracting"
TMP_DIR="$(mktemp -d "${CACHE_DIR}/extract.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT
tar -xf "$TARBALL" -C "$TMP_DIR"
[ -d "${TMP_DIR}/${SOURCE_ROOT}" ] || die "unexpected archive layout: ${SOURCE_ROOT}/ not found"
[ -x "${TMP_DIR}/${SOURCE_ROOT}/mach" ] || die "extracted tree has no ./mach; refusing to continue"

rm -rf "$SRC_DIR"
mkdir -p "$(dirname "$SRC_DIR")"
mv "${TMP_DIR}/${SOURCE_ROOT}" "$SRC_DIR"
printf '%s\n' "$VERSION" > "${SRC_DIR}/.sheepfox-source"

step "Done"
info "sources : ${SRC_DIR}"
info "next    : make patch-source"
