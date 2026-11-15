#!/usr/bin/env bash
# Installs the external tools swe-metrics uses, always at their latest release (tools.list), for macOS and
# Linux (arm64, x86_64). No root, no package manager: everything goes into one directory, with links in a bin
# directory. Uninstall by deleting both.
#
# A tool that fails to install doesn't stop the others; the script then exits 1 and names it.
#
# Usage: scripts/install-tools.sh [--prefix DIR] [--bin-dir DIR] [--only TOOL]... [--check | --check-urls] [--list FILE]
#   --prefix      where the tools go          (default: ~/.local/share/swe-metrics/tools)
#   --bin-dir     where the links go          (default: ~/.local/bin)
#   --only        install or check only TOOL  (repeatable)
#   --check       report the installed versions, install nothing (exit 1 when a tool is missing)
#   --check-urls  resolve every download URL of the latest releases, for every platform (exit 1 naming the broken)
#   --list        the tool list               (default: tools.list next to this script's directory)
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
LIST="$ROOT/tools.list"
PREFIX="$HOME/.local/share/swe-metrics/tools"
BIN_DIR="$HOME/.local/bin"
ONLY=()
CHECK=0
CHECK_URLS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --prefix) PREFIX=$2; shift 2 ;;
    --bin-dir) BIN_DIR=$2; shift 2 ;;
    --only) ONLY+=("$2"); shift 2 ;;
    --check) CHECK=1; shift ;;
    --check-urls) CHECK_URLS=1; shift ;;
    --list) LIST=$2; shift 2 ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

case "$(uname -s)" in Darwin) OS=darwin ;; Linux) OS=linux ;; *) echo "unsupported OS: $(uname -s)" >&2; exit 2 ;; esac
case "$(uname -m)" in arm64|aarch64) ARCH=arm64 ;; x86_64|amd64) ARCH=amd64 ;; *) echo "unsupported CPU: $(uname -m)" >&2; exit 2 ;; esac
PLATFORM="$OS-$ARCH"

wanted() {  # is this tool selected by --only (or is there no --only)?
  [ ${#ONLY[@]} -eq 0 ] && return 0
  local t; for t in "${ONLY[@]}"; do [ "$t" = "$1" ] && return 0; done; return 1
}

installed_version() {  # the version a tool on PATH reports, or empty
  local out
  case "$1" in
    gitleaks) out=$(gitleaks version 2>/dev/null) ;;
    terraform) out=$(terraform version 2>/dev/null | head -1) ;;
    node) out=$("$PREFIX/node/bin/node" --version 2>/dev/null) ;;
    dependency-cruiser) out=$(depcruise --version 2>/dev/null) ;;
    typescript|typescript-eslint|@eslint/js)   # libraries with no command: the version in their package.json
      out=$(sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' "$PREFIX/npm/lib/node_modules/$1/package.json" 2>/dev/null | head -1) ;;
    *) out=$("$1" --version 2>&1 | head -3) ;;
  esac
  printf '%s' "$out" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true
}

check() {  # report every selected tool's installed version; exit 1 when one is missing
  local failed=0 tool latest platform rest found
  while IFS=$'\t' read -r tool latest platform rest; do
    [[ -z "$tool" || "$tool" == \#* ]] && continue
    [[ "$platform" != "any" && "$platform" != "$PLATFORM" ]] && continue
    wanted "$tool" || continue
    found=$(installed_version "$tool")
    if [ -n "$found" ]; then echo "ok        $tool $found"; else echo "MISSING   $tool"; failed=1; fi
  done < "$LIST"
  command -v jdeps >/dev/null || echo "note      jdeps not found: install a JDK to measure Java class files (--report classes=PATH)"
  return $failed
}

need() {  # the commands this script itself needs
  local missing=() c
  for c in curl tar unzip python3 "$@"; do command -v "$c" >/dev/null || missing+=("$c"); done
  if command -v python3 >/dev/null && ! python3 -c 'import venv, ensurepip' 2>/dev/null; then
    missing+=("python3-venv")
  fi
  if [ ${#missing[@]} -gt 0 ]; then
    echo "missing: ${missing[*]}" >&2
    echo "  Debian/Ubuntu: sudo apt-get install -y curl unzip xz-utils python3-venv" >&2
    echo "  Amazon Linux / Fedora: sudo dnf install -y curl unzip xz python3" >&2
    exit 2
  fi
}

latest() {  # the newest release of a tool, from its `latest` column: prints "<tag> <version>"
  local spec=$1 tag
  case "$spec" in
    gh:*)        tag=$(curl -fsSL -o /dev/null -w '%{url_effective}' "https://github.com/${spec#gh:}/releases/latest"); tag=${tag##*/} ;;
    hashicorp:*) tag=$(curl -fsSL "https://checkpoint-api.hashicorp.com/v1/check/${spec#hashicorp:}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["current_version"])') ;;
    node)        tag=$(curl -fsSL https://nodejs.org/dist/index.json | python3 -c 'import json,sys; print(next(r["version"] for r in json.load(sys.stdin) if r["lts"]))') ;;
    *)           tag="" ;;
  esac
  printf '%s %s' "$tag" "$(printf '%s' "$tag" | sed -E 's/^[^0-9]*//')"
}

fetch() {  # url -> $WORK/download
  curl -fsSL --retry 3 -o "$WORK/download" "$1"
}

link() {  # make $2 in the bin directory run $1
  ln -sf "$1" "$BIN_DIR/$2"
}

node_wrapper() {  # Node tools run on the Node installed here, never on whatever Node the system has
  printf '#!/bin/sh\nPATH="%s/node/bin:$PATH" exec "%s/npm/bin/%s" "$@"\n' "$PREFIX" "$PREFIX" "$1" > "$BIN_DIR/$1"
  chmod 755 "$BIN_DIR/$1"
}

install_one() {  # tool latest kind source
  local tool=$1 spec=$2 kind=$3 url=$4 bin tag version
  read -r tag version <<< "$(latest "$spec")"
  url=${url//\{tag\}/$tag}; url=${url//\{v\}/$version}
  echo "installing $tool ${version:-latest}"
  case "$kind" in
    tar:*|zip:*) bin=${kind#*:}; fetch "$url"; rm -rf "$WORK/x"; mkdir -p "$WORK/x"
                 if [ "${kind%%:*}" = tar ]; then tar -xf "$WORK/download" -C "$WORK/x"; else unzip -q "$WORK/download" -d "$WORK/x"; fi
                 install -m 755 "$(find "$WORK/x" -type f -name "$bin" | head -1)" "$PREFIX/bin/$bin"; link "$PREFIX/bin/$bin" "$bin" ;;
    bin:*)       bin=${kind#bin:}; fetch "$url"; install -m 755 "$WORK/download" "$PREFIX/bin/$bin"; link "$PREFIX/bin/$bin" "$bin" ;;
    node)        fetch "$url"; rm -rf "$PREFIX/node"; mkdir -p "$PREFIX/node"
                 tar -xJf "$WORK/download" -C "$PREFIX/node" --strip-components 1 ;;
    npm)         [ -x "$PREFIX/node/bin/npm" ] || { echo "node must be installed first (it is listed before npm packages)" >&2; exit 1; }
                 PATH="$PREFIX/node/bin:$PATH" npm install -g --prefix "$PREFIX/npm" --no-fund --no-audit --loglevel=error "$url" >/dev/null
                 for bin in "$PREFIX"/npm/bin/*; do node_wrapper "$(basename "$bin")"; done ;;
    pip)         python3 -m venv "$PREFIX/$tool" && "$PREFIX/$tool/bin/pip" install -q --upgrade --disable-pip-version-check "$url"
                 link "$PREFIX/$tool/bin/$tool" "$tool" ;;
    *)           echo "unknown kind $kind for $tool" >&2; exit 1 ;;
  esac
}

check_urls() {  # resolve every selected download URL, for every platform; exit 1 naming those that fail
  local broken=() tool spec platform kind url tag version
  while IFS=$'\t' read -r tool spec platform kind url; do
    [[ -z "$tool" || "$tool" == \#* || "$url" != http* ]] && continue
    wanted "$tool" || continue
    read -r tag version <<< "$(latest "$spec")"
    url=${url//\{tag\}/$tag}; url=${url//\{v\}/$version}
    if curl -fsIL --retry 3 -o /dev/null "$url"; then echo "ok        $tool $platform"
    else echo "BROKEN    $tool $platform $url"; broken+=("$tool/$platform"); fi
  done < "$LIST"
  [ ${#broken[@]} -eq 0 ] || { echo "broken download URLs: ${broken[*]}" >&2; return 1; }
}

needs_node() {  # does any selected tool run on Node?
  local tool latest platform kind rest
  while IFS=$'\t' read -r tool latest platform kind rest; do
    [ "$kind" = npm ] && wanted "$tool" && return 0
  done < <(grep -v '^#' "$LIST")
  return 1
}

if [ "$CHECK" -eq 1 ]; then PATH="$BIN_DIR:$PATH" check; exit $?; fi
if [ "$CHECK_URLS" -eq 1 ]; then check_urls; exit $?; fi

if [ "$OS" = linux ]; then need xz; else need; fi   # Node ships as .tar.xz; macOS tar reads xz by itself
mkdir -p "$PREFIX/bin" "$BIN_DIR"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
FAILED=()
while IFS=$'\t' read -r tool latest platform kind url; do
  [[ -z "$tool" || "$tool" == \#* ]] && continue
  [[ "$platform" != "any" && "$platform" != "$PLATFORM" ]] && continue
  if wanted "$tool" || { [ "$kind" = node ] && needs_node && [ ! -x "$PREFIX/node/bin/node" ]; }; then
    # in the background, so `set -e` stops this tool's install at its first error (it is off in a tested
    # subshell) and the loop goes on with the next tool
    install_one "$tool" "$latest" "$kind" "$url" &
    wait $! || { echo "FAILED to install $tool" >&2; FAILED+=("$tool"); }
  fi
done < "$LIST"

echo
PATH="$BIN_DIR:$PATH" check || true
case ":$PATH:" in *":$BIN_DIR:"*) ;; *) echo; echo "Add the tools to your PATH:  export PATH=\"$BIN_DIR:\$PATH\"" ;; esac
if [ ${#FAILED[@]} -gt 0 ]; then echo; echo "failed to install: ${FAILED[*]}" >&2; exit 1; fi
