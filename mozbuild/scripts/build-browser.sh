#!/usr/bin/env bash
# ============================================================================
# (SheepFox) Zen browser — compile a standalone branded SheepFox build
#
#   ./mozbuild/scripts/build-browser.sh [--target TARGET] [--no-package]
#
# TARGET: auto (default) | linux-x86_64 | linux-aarch64 | windows-x86_64 |
#         macos-universal
#
# Requires: a patched source tree (make fetch-source && make patch-source),
#           the platform build prerequisites (./mach bootstrap), ~40 GB free,
#           and 16 GB+ RAM for cross-language LTO.
#
# Environment:
#   SHEEPFOX_PGO=1           two-stage cross-language PGO (slow, ~2x build time)
#   SHEEPFOX_PGO_PROFILE     reuse an existing merged.profdata (skips stage 1)
#   SHEEPFOX_MAC_TARGET      aarch64-apple-darwin (default) / x86_64-apple-darwin
#   SHEEPFOX_SRC_DIR         patched source tree (default: mozbuild/firefox-src)
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SOURCE_DIR="${SHEEPFOX_SRC_DIR:-${REPO_ROOT}/mozbuild/firefox-src}"
STAGING_DIR="${REPO_ROOT}/mozbuild/staging"
TARGET="auto"
DO_PACKAGE=1

PGO_URLS=(
  "about:blank"
  "https://example.com"
  "https://en.wikipedia.org/wiki/Firefox"
  "https://github.com/mozilla-firefox/firefox"
)

step() { printf '\n==> %s\n' "$*"; }
info() { printf '  [info]  %s\n' "$*"; }
warn() { printf '  [warn]  %s\n' "$*"; }
die()  { printf '  [error] %s\n' "$*" >&2; exit 1; }

while [ "$#" -gt 0 ]; do
  case "$1" in
    --target)     TARGET="${2:-}"; shift ;;
    --no-package) DO_PACKAGE=0 ;;
    --source)     SOURCE_DIR="${2:-}"; shift ;;
    -h|--help)    sed -n '2,22p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown argument: $1 (try --help)" ;;
  esac
  shift
done

# ---------------------------------------------------------------- target
detect_target() {
  local os arch
  os="$(uname -s)"
  arch="$(uname -m)"
  case "$os" in
    Linux)
      case "$arch" in
        x86_64|amd64)  printf 'linux-x86_64' ;;
        aarch64|arm64) printf 'linux-aarch64' ;;
        *) die "unsupported Linux architecture: ${arch}" ;;
      esac
      ;;
    Darwin) printf 'macos-universal' ;;
    MINGW*|MSYS*|CYGWIN*|Windows_NT) printf 'windows-x86_64' ;;
    *) die "unsupported host OS: ${os}" ;;
  esac
}

if [ "$TARGET" = "auto" ]; then
  TARGET="$(detect_target)"
fi

case "$TARGET" in
  linux-x86_64|linux-aarch64|windows-x86_64|macos-universal) ;;
  *) die "unknown target: ${TARGET}" ;;
esac

MOZCONFIG="${REPO_ROOT}/mozbuild/mozconfig.${TARGET}"
[ -f "$MOZCONFIG" ] || die "mozconfig not found: ${MOZCONFIG}"
[ -d "$SOURCE_DIR" ] || die "source tree not found: ${SOURCE_DIR} (run: make fetch-source)"
[ -x "${SOURCE_DIR}/mach" ] || die "${SOURCE_DIR} has no ./mach (run: make fetch-source)"
[ -f "${SOURCE_DIR}/.sheepfox-patched" ] || warn "patches are not applied yet (run: make patch-source)"

export MOZCONFIG

# ---------------------------------------------------------------- helpers
run_mach() { ( cd "$SOURCE_DIR" && ./mach "$@" ); }

find_objdir() {
  local candidate best="" best_time=0
  if [ -n "${MOZ_OBJDIR:-}" ] && [ -d "${MOZ_OBJDIR}" ]; then
    printf '%s' "$MOZ_OBJDIR"
    return 0
  fi
  for candidate in "$SOURCE_DIR"/obj-*; do
    [ -d "$candidate" ] || continue
    local stamp
    stamp="$(stat -c %Y "$candidate" 2>/dev/null || stat -f %m "$candidate" 2>/dev/null || echo 0)"
    if [ "$stamp" -ge "$best_time" ]; then
      best="$candidate"
      best_time="$stamp"
    fi
  done
  [ -n "$best" ] || die "no object directory found in ${SOURCE_DIR}; did ./mach configure run?"
  printf '%s' "$best"
}

inject_runtime_config() {
  local objdir="$1" bin="${1}/dist/bin"
  [ -d "$STAGING_DIR" ] || die "runtime config not staged (${STAGING_DIR}); run: make patch-source"
  [ -d "$bin" ] || { warn "no packaged output at ${bin}; skipping config injection"; return 0; }
  install -d "${bin}/defaults/pref" "${bin}/distribution"
  install -m 0644 "${STAGING_DIR}/sheepfox.cfg"                    "${bin}/sheepfox.cfg"
  install -m 0644 "${STAGING_DIR}/defaults/pref/local-settings.js" "${bin}/defaults/pref/local-settings.js"
  install -m 0644 "${STAGING_DIR}/distribution/policies.json"      "${bin}/distribution/policies.json"
  info "injected AutoConfig + SheepShields policies into ${bin}"
  info "object directory: ${objdir}"
}

binary_path() {
  local objdir="$1"
  if [ -x "${objdir}/dist/bin/firefox" ]; then
    printf '%s' "${objdir}/dist/bin/firefox"
  elif [ -x "${objdir}/dist/bin/firefox.exe" ]; then
    printf '%s' "${objdir}/dist/bin/firefox.exe"
  else
    printf ''
  fi
}

build_once() {
  step "mach configure"
  run_mach configure
  step "mach build"
  run_mach build
  if [ "$DO_PACKAGE" -eq 1 ]; then
    step "mach package"
    run_mach package
  fi
  local objdir
  objdir="$(find_objdir)"
  inject_runtime_config "$objdir"
  printf '%s' "$objdir" > "${REPO_ROOT}/mozbuild/.last-objdir"
}

# ---------------------------------------------------------------- PGO
train_profile() {
  local objdir="$1" binary profile_dir
  binary="$(binary_path "$objdir")"
  [ -n "$binary" ] || die "instrumented binary not found in ${objdir}/dist/bin"
  command -v llvm-profdata >/dev/null 2>&1 \
    || die "llvm-profdata not found; install llvm/clang or set SHEEPFOX_PGO_PROFILE manually"

  profile_dir="${REPO_ROOT}/mozbuild/pgo-profile"
  rm -rf "$profile_dir"
  mkdir -p "${profile_dir}/raw" "${profile_dir}/profile"

  step "PGO stage 1b: training the instrumented build"
  info "writing raw profiles to ${profile_dir}/raw"
  local url
  for url in "${PGO_URLS[@]}"; do
    info "loading ${url}"
    LLVM_PROFILE_FILE="${profile_dir}/raw/%p.profraw" \
      "$binary" --headless --no-remote --new-instance \
      --profile "${profile_dir}/profile" \
      --screenshot "${profile_dir}/shot.png" "$url" >/dev/null 2>&1 || warn "training run failed for ${url}"
  done

  shopt -s nullglob
  local raw=("${profile_dir}"/raw/*.profraw)
  shopt -u nullglob
  [ "${#raw[@]}" -gt 0 ] || die "no .profraw files produced; cannot continue with PGO"

  llvm-profdata merge -o "${profile_dir}/merged.profdata" "${raw[@]}"
  info "merged profile: ${profile_dir}/merged.profdata"
  printf '%s' "${profile_dir}/merged.profdata"
}

# ---------------------------------------------------------------- macOS
merge_universal() {
  local arm_dir="$1" x86_dir="$2" out_dir="$3"
  command -v lipo >/dev/null 2>&1 || die "lipo not found (install Xcode command line tools)"
  rm -rf "$out_dir"
  cp -R "$arm_dir" "$out_dir"

  local count=0
  while IFS= read -r -d '' candidate; do
    local rel counterpart
    rel="${candidate#"${out_dir}"/}"
    counterpart="${x86_dir}/${rel}"
    [ -f "$counterpart" ] || continue
    if file -b "$candidate" | grep -q 'Mach-O'; then
      if lipo -create "$candidate" "$counterpart" -output "${candidate}.universal" 2>/dev/null; then
        mv "${candidate}.universal" "$candidate"
        count=$((count + 1))
      else
        rm -f "${candidate}.universal"
      fi
    fi
  done < <(find "$out_dir" -type f -print0)
  info "lipo-merged ${count} Mach-O files into ${out_dir}"
}

build_macos_universal() {
  local slice
  for slice in aarch64-apple-darwin x86_64-apple-darwin; do
    step "macOS slice: ${slice}"
    export SHEEPFOX_MAC_TARGET="${slice}"
    export MOZ_OBJDIR="${SOURCE_DIR}/obj-${slice}"
    build_once
    info "slice built in ${MOZ_OBJDIR}"
  done

  step "Assembling universal2 app"
  merge_universal \
    "${SOURCE_DIR}/obj-aarch64-apple-darwin/dist/bin" \
    "${SOURCE_DIR}/obj-x86_64-apple-darwin/dist/bin" \
    "${SOURCE_DIR}/obj-universal/dist/bin"
  unset MOZ_OBJDIR
  printf '%s' "${SOURCE_DIR}/obj-universal" > "${REPO_ROOT}/mozbuild/.last-objdir"
}

# ---------------------------------------------------------------- main
step "SheepFox fork build"
info "target   : ${TARGET}"
info "mozconfig: ${MOZCONFIG}"
info "source   : ${SOURCE_DIR}"
info "package  : ${DO_PACKAGE}"

if [ "$TARGET" = "macos-universal" ]; then
  build_macos_universal
elif [ "${SHEEPFOX_PGO:-0}" = "1" ] && [ -z "${SHEEPFOX_PGO_PROFILE:-}" ]; then
  step "PGO stage 1/2: instrumented build"
  unset SHEEPFOX_PGO_PROFILE
  build_once
  PROFILE="$(train_profile "$(cat "${REPO_ROOT}/mozbuild/.last-objdir")")"

  step "PGO stage 2/2: profile-guided rebuild"
  run_mach clobber
  SHEEPFOX_PGO_PROFILE="$PROFILE" build_once
else
  build_once
fi

step "Build complete"
OBJDIR="$(cat "${REPO_ROOT}/mozbuild/.last-objdir" 2>/dev/null || echo "${SOURCE_DIR}")"
info "object dir : ${OBJDIR}"
info "binaries   : ${OBJDIR}/dist/bin"
if [ "$DO_PACKAGE" -eq 1 ]; then
  info "packages   : ${OBJDIR}/dist"
fi
info "install    : extract the package, then run ./sheepfox (or sheepfox.exe)"
