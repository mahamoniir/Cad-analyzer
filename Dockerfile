# syntax=docker/dockerfile:1
FROM python:3.11-slim

# ------------------------------------------------------------
# System dependencies:
#   xvfb            -> fake display so ODA File Converter's GUI can run headless
#   wget            -> fetch the installer at build time
#   libxrender1 etc -> Qt/X11 runtime libs ODA File Converter needs
# ------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    wget \
    ca-certificates \
    libxrender1 \
    libxext6 \
    libsm6 \
    libglib2.0-0 \
    libfontconfig1 \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ------------------------------------------------------------
# Download ODA File Converter here instead of committing it to git —
# the installer is 50+ MB, which is awkward to keep in a repo and not
# something ODA's terms clearly permit you to redistribute yourself.
#
# Before building, confirm the current filename/version at:
#   https://www.opendesign.com/guestfiles/oda_file_converter
# and update ODA_DEB_URL below if it has changed.
# ------------------------------------------------------------
ARG ODA_DEB_URL="https://www.opendesign.com/guestfiles/get?filename=ODAFileConverter_QT6_lnxX64_8.3dll_25.11.deb"
RUN wget -q -O /tmp/ODAFileConverter.deb "$ODA_DEB_URL" \
    && apt-get update \
    && apt-get install -y /tmp/ODAFileConverter.deb \
    && rm /tmp/ODAFileConverter.deb \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------
# IMPORTANT — verify this path matches the installed package.
# See the build-log discovery trick in the chat if unsure.
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
CMD gunicorn -w 2 -b 0.0.0.0:${PORT} app:app
