#!/bin/bash
# Runs the real ODAFileConverter binary inside a virtual X display so it
# doesn't try (and fail) to open a real GUI on a headless server.
set -e

# Qt requires XDG_RUNTIME_DIR to exist with mode 0700. Left unset, Qt
# auto-falls-back to /tmp/runtime-root but doesn't always set permissions
# correctly (especially running as root in a container), which can cause
# the conversion to silently produce no output.
export XDG_RUNTIME_DIR=/tmp/runtime-dir
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

REAL_BIN="${ODA_REAL_BIN:-/usr/bin/ODAFileConverter}"

exec xvfb-run -a --server-args="-screen 0 1024x768x24" "$REAL_BIN" "$@"