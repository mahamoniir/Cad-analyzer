# syntax=docker/dockerfile:1
FROM python:3.11-slim

# ------------------------------------------------------------
# System dependencies:
#   xvfb            -> fake display so ODA File Converter's GUI can run headless
#   wget            -> fetch the installer at build time
#   libxrender1 etc -> Qt/X11 runtime libs ODA File Converter needs
#   libxcb-util1     -> modern Debian ships libxcb-util.so.1; ODA's package
#                        expects libxcb-util.so.0, so we symlink it below
# ------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    xvfb-run \
    xauth \
    wget \
    ca-certificates \
    libxrender1 \
    libxext6 \
    libsm6 \
    libglib2.0-0 \
    libfontconfig1 \
    fontconfig \
    libxcb-util1 \
    libxkbcommon0 \
    libxkbcommon-x11-0 \
    libxcb-cursor0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-xinerama0 \
    && rm -rf /var/lib/apt/lists/*

# Compat symlink: ODA's package looks for libxcb-util.so.0, which no longer
# ships by default on modern Debian/Ubuntu (only .so.1 exists).
RUN lib_dir="/usr/lib/x86_64-linux-gnu" \
    && if [ -f "$lib_dir/libxcb-util.so.1" ] && [ ! -e "$lib_dir/libxcb-util.so.0" ]; then \
         ln -s "$lib_dir/libxcb-util.so.1" "$lib_dir/libxcb-util.so.0"; \
       fi

WORKDIR /app

# ------------------------------------------------------------
# Download ODA File Converter from a GitHub Release asset you control,
# instead of ODA's site (whose versioned filename changes over time and
# isn't reliable to hardcode) or committing the 50+ MB file to git.
#
# 1. Download the current .deb manually from:
#    https://www.opendesign.com/guestfiles/oda_file_converter
# 2. Upload it as a Release asset in your GitHub repo.
# 3. Put that asset's direct download URL below.
# ------------------------------------------------------------
ARG ODA_DEB_URL="https://github.com/mahamoniir/Cad-analyzer/releases/download/deps-v1/ODAFileConverter.deb"
RUN wget -q -O /tmp/ODAFileConverter.deb "$ODA_DEB_URL" \
    && apt-get update \
    && apt-get install -y /tmp/ODAFileConverter.deb \
    && rm /tmp/ODAFileConverter.deb \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------
# IMPORTANT — verify this path matches the installed package.
# ------------------------------------------------------------
ENV ODA_REAL_BIN=/usr/bin/ODAFileConverter

# Headless wrapper: shadows the real "ODAFileConverter" command on PATH
# (/usr/local/bin comes before /usr/bin in the default PATH) so ezdxf's
# odafc.readfile(), which just calls "ODAFileConverter", runs it under xvfb.
COPY deploy/odafc-wrapper.sh /usr/local/bin/ODAFileConverter
RUN chmod +x /usr/local/bin/ODAFileConverter

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway sets $PORT at runtime
ENV PORT=8080
CMD gunicorn -w 2 -b 0.0.0.0:${PORT} --timeout 300 app:app
