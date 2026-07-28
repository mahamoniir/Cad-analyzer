FROM python:3.11-slim

# --- System libs the ODA File Converter (Qt6) needs, plus Xvfb to run it headless ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    libqt6core6 libqt6gui6 libqt6widgets6 \
    libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
    libxcb-randr0 libxcb-render-util0 libxcb-xinerama0 libxcb-xkb1 \
    libxkbcommon-x11-0 fontconfig ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# --- Install ODA File Converter from the .deb you committed to the repo ---
COPY deploy/ODAFileConverter.deb /tmp/oda.deb
RUN apt-get update \
    && apt-get install -y --no-install-recommends /tmp/oda.deb \
    && rm /tmp/oda.deb \
    && rm -rf /var/lib/apt/lists/*

# Newer Debian ships libxcb-util.so.1 but ODA looks for .so.0 — symlink fix
RUN ln -sf /usr/lib/x86_64-linux-gnu/libxcb-util.so.1 \
           /usr/lib/x86_64-linux-gnu/libxcb-util.so.0 || true

ENV DISPLAY=:99

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p uploads output

# Xvfb provides the fake display ODAFileConverter needs even in "headless" mode,
# then gunicorn runs the Flask app on Railway's assigned $PORT
CMD sh -c "Xvfb :99 -screen 0 1024x768x16 & exec gunicorn -b 0.0.0.0:$PORT app:app"