#!/usr/bin/env bash
# Installs the external tools swe-metrics uses, exactly as pinned in tools.lock, for macOS and Linux
# (arm64, x86_64). No root, no package manager: everything goes into one directory, with links in a bin
# directory. Uninstall by deleting both.
#
# Usage: scripts/install-tools.sh [--prefix DIR] [--bin-dir DIR] [--only TOOL]... [--check]
#   --prefix   where the tools go          (default: ~/.local/share/swe-metrics/tools)
#   --bin-dir  where the links go          (default: ~/.local/bin)
#   --only     install or check only TOOL  (repeatable)
#   --check    report installed versions against tools.lock, install nothing (exit 1 on a mismatch)
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
LOCK="$ROOT/tools.lock"
PREFIX="$HOME/.local/share/swe-metrics/tools"
BIN_DIR="$HOME/.local/bin"
ONLY=()
CHECK=0
while [ $# -gt 0 ]; do
  case "$1" in
    --prefix) PREFIX=$2; shift 2 ;;
    --bin-dir) BIN_DIR=$2; shift 2 ;;
    --only) ONLY+=("$2"); shift 2 ;;
    --check) CHECK=1; shift ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
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
    *) out=$("$1" --version 2>&1 | head -3) ;;
  esac
  printf '%s' "$out" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true
}

check() {  # compare every selected tool with the lock; exit 1 on a mismatch
  local failed=0 tool version platform rest found
  while IFS=$'\t' read -r tool version platform rest; do
    [[ -z "$tool" || "$tool" == \#* ]] && continue
    [[ "$platform" != "any" && "$platform" != "$PLATFORM" ]] && continue
    wanted "$tool" || continue
    found=$(installed_version "$tool")
    if [ "$found" = "$version" ]; then echo "ok        $tool $version"
    else echo "MISMATCH  $tool: installed ${found:-none}, lock pins $version"; failed=1; fi
  done < "$LOCK"
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

sha256() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }

fetch() {  # url sha256 -> $WORK/download, checksum verified
  curl -fsSL --retry 3 -o "$WORK/download" "$1"
  local got; got=$(sha256 "$WORK/download")
  if [ "$got" != "$2" ]; then echo "checksum mismatch for $1: got $got, expected $2" >&2; exit 1; fi
}

link() {  # make $2 in the bin directory run $1
  ln -sf "$1" "$BIN_DIR/$2"
}

node_wrapper() {  # Node tools run on the pinned Node, never on whatever Node the system has
  printf '#!/bin/sh\nPATH="%s/node/bin:$PATH" exec "%s/npm/bin/%s" "$@"\n' "$PREFIX" "$PREFIX" "$1" > "$BIN_DIR/$1"
  chmod 755 "$BIN_DIR/$1"
}

install_one() {  # tool version kind sha256 source
  local tool=$1 version=$2 kind=$3 sha=$4 url=$5 bin
  echo "installing $tool $version"
  case "$kind" in
    tar:*|zip:*) bin=${kind#*:}; fetch "$url" "$sha"; rm -rf "$WORK/x"; mkdir -p "$WORK/x"
                 if [ "${kind%%:*}" = tar ]; then tar -xf "$WORK/download" -C "$WORK/x"; else unzip -q "$WORK/download" -d "$WORK/x"; fi
                 install -m 755 "$(find "$WORK/x" -type f -name "$bin" | head -1)" "$PREFIX/bin/$bin"; link "$PREFIX/bin/$bin" "$bin" ;;
    bin:*)       bin=${kind#bin:}; fetch "$url" "$sha"; install -m 755 "$WORK/download" "$PREFIX/bin/$bin"; link "$PREFIX/bin/$bin" "$bin" ;;
    node)        fetch "$url" "$sha"; rm -rf "$PREFIX/node"; mkdir -p "$PREFIX/node"
                 tar -xJf "$WORK/download" -C "$PREFIX/node" --strip-components 1 ;;
    npm)         [ -x "$PREFIX/node/bin/npm" ] || { echo "node must be installed first (it is listed before npm packages)" >&2; exit 1; }
                 PATH="$PREFIX/node/bin:$PATH" npm install -g --prefix "$PREFIX/npm" --no-fund --no-audit --loglevel=error "$url@$version" >/dev/null
                 for bin in "$PREFIX"/npm/bin/*; do node_wrapper "$(basename "$bin")"; done ;;
    pip)         python3 -m venv "$PREFIX/$tool" && "$PREFIX/$tool/bin/pip" install -q --disable-pip-version-check "$url==$version"
                 link "$PREFIX/$tool/bin/$tool" "$tool" ;;
    *)           echo "unknown kind $kind for $tool" >&2; exit 1 ;;
  esac
}

needs_node() {  # does any selected tool run on Node?
  local tool version platform kind rest
  while IFS=$'\t' read -r tool version platform kind rest; do
    [ "$kind" = npm ] && wanted "$tool" && return 0
  done < <(grep -v '^#' "$LOCK")
  return 1
}

if [ "$CHECK" -eq 1 ]; then PATH="$BIN_DIR:$PATH" check; exit $?; fi

if [ "$OS" = linux ]; then need xz; else need; fi   # Node ships as .tar.xz; macOS tar reads xz by itself
mkdir -p "$PREFIX/bin" "$BIN_DIR"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
while IFS=$'\t' read -r tool version platform kind sha url; do
  [[ -z "$tool" || "$tool" == \#* ]] && continue
  [[ "$platform" != "any" && "$platform" != "$PLATFORM" ]] && continue
  if wanted "$tool" || { [ "$kind" = node ] && needs_node && [ ! -x "$PREFIX/node/bin/node" ]; }; then
    install_one "$tool" "$version" "$kind" "$sha" "$url"
  fi
done < "$LOCK"

echo
PATH="$BIN_DIR:$PATH" check || true
case ":$PATH:" in *":$BIN_DIR:"*) ;; *) echo; echo "Add the tools to your PATH:  export PATH=\"$BIN_DIR:\$PATH\"" ;; esac
