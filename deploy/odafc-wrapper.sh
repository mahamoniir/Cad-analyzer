#!/bin/bash
# Runs the real ODAFileConverter binary inside a virtual X display so it
# doesn't try (and fail) to open a real GUI on a headless server.
#
# NOTE: update the path below if `dpkg -c deploy/ODAFileConverter.deb`
# shows the binary living somewhere other than /usr/bin/ODAFileConverter.
set -e

REAL_BIN="${ODA_REAL_BIN:-/usr/bin/ODAFileConverter}"

exec xvfb-run -a --server-args="-screen 0 1024x768x24" "$REAL_BIN" "$@"
