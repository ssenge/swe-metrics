#!/usr/bin/env bash
# Installs the tools listed in tools.lock for this machine's architecture; any checksum mismatch aborts.
# Usage: install-tools.sh <tools.lock>   (run as root while building the image)
set -euo pipefail
LOCK=$1
ARCH=$(dpkg --print-architecture)          # arm64 | amd64
BIN=/usr/local/bin
WORK=$(mktemp -d)
cd "$WORK"

fetch() {  # url sha256 -> ./download, verified
  curl -fsSL --retry 3 -o download "$1"
  echo "$2  download" | sha256sum -c - >/dev/null
}

while IFS=$'\t' read -r tool version arch kind sha url; do
  [[ -z "$tool" || "$tool" == \#* ]] && continue
  [[ "$arch" != "any" && "$arch" != "$ARCH" ]] && continue
  echo "installing $tool $version ($kind)"
  case "$kind" in
    tar:*) fetch "$url" "$sha"; mkdir -p x && tar -xf download -C x
           install -m 755 "$(find x -type f -name "${kind#tar:}" | head -1)" "$BIN/${kind#tar:}"; rm -rf x ;;
    zip:*) fetch "$url" "$sha"; mkdir -p x && unzip -q download -d x
           install -m 755 "x/${kind#zip:}" "$BIN/${kind#zip:}"; rm -rf x ;;
    bin:*) fetch "$url" "$sha"; install -m 755 download "$BIN/${kind#bin:}" ;;
    jar:*) fetch "$url" "$sha"; install -D -m 644 download "/opt/${kind#jar:}/${kind#jar:}.jar"
           printf '#!/bin/sh\nexec java -jar /opt/%s/%s.jar "$@"\n' "${kind#jar:}" "${kind#jar:}" > "$BIN/${kind#jar:}"
           chmod 755 "$BIN/${kind#jar:}" ;;
    node)  fetch "$url" "$sha"; mkdir -p /opt/node && tar -xJf download -C /opt/node --strip-components 1 ;;
    npm)   /opt/node/bin/npm install -g --no-fund --no-audit "$url@$version" >/dev/null ;;
    pip)   python -m venv "/opt/$tool" && "/opt/$tool/bin/pip" install -q --no-cache-dir "$url==$version"
           ln -sf "/opt/$tool/bin/$tool" "$BIN/$tool" ;;
    *)     echo "unknown kind $kind for $tool" >&2; exit 1 ;;
  esac
  rm -f download
done < "$LOCK"
rm -rf "$WORK"
