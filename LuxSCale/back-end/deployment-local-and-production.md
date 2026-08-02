# Local development and production deployment

## 1. Local Flask (development)

| Step | Command / setting |
|------|-------------------|
| **Install** | `pip install -r requirements.txt` |
| **Env** | Copy **`.env.example`** if present, or create **`.env`** with `FLASK_SECRET_KEY`, optional `PORT=5000` |
| **Run** | From repo root: `python app.py` or `set FLASK_APP=app.py` and `flask run --host=127.0.0.1 --port=5000` |
| **Test calculate** | `curl -X POST http://127.0.0.1:5000/calculate -H "Content-Type: application/json" -d @payload.json` |

**Browser front-end** opened as **`file://`** or **XAMPP `http://localhost/...`** must use **absolute API URL** to Flask (**`http://127.0.0.1:5000`**) — see front-end `getCalculateApiUrl()`.

---

## 2. CORS (local)

Default **`LUXSCALE_CORS_ORIGINS`** empty → **`flask-cors`** allows a **built-in list** of localhost/127.0.0.1 origins on common ports.

If the HTML origin is **not** listed (e.g. custom hostname), set:

```env
LUXSCALE_CORS_ORIGINS=http://localhost,http://127.0.0.1:8080,https://yourdomain.com
```

---

## 3. XAMPP / Apache + PHP stack

| Component | Typical setup |
|-----------|----------------|
| **Static HTML** | `htdocs/LuxScaleAI/index3.html` served by Apache |
| **PHP submit/get** | **`api/submit.php`**, **`api/get.php`** write/read JSON under **`api/data/`** |
| **Flask** | Run separately on **port 5000**; front-end points calculate + optional Flask submit |

**`LUXSCALE_DASHBOARD_API_BASE`:** e.g. `http://127.0.0.1:5000` — **`_write_dashboard_config_json()`** mirrors this into **`assets/dashboard_config.json`** so **`admin/dashboard.html`** opened from **file:// or XAMPP** knows where to **`fetch`** admin API.

---

## 4. Production (PaaS / VPS)

| Topic | Guidance |
|-------|----------|
| **Host** | Any WSGI-capable host; `app.py` uses `app.run` for simplicity — production should use **gunicorn** + nginx reverse proxy (not shown in repo) |
| **Port** | **`PORT`** env (Railway/Heroku pattern) — see bottom of `app.py` |
| **Secret** | **`FLASK_SECRET_KEY`** strong random |
| **HTTPS** | Terminate TLS at proxy; set **`LUXSCALE_CORS_ORIGINS`** to real front-end origin |
| **Logs** | Ship **`luxscale_app.log`** or redirect stdout; rotate files |
| **Studies** | **`api/data/studies/`** on disk — persist volume or migrate to DB for multi-instance |

---

## 5. PythonAnywhere / remote API

Front-end defaults may point to **`mahamonir.pythonanywhere.com`** — ensure that deployment runs the **same** Flask code version and **`standards/`** files.

---

## 6. Admin dashboard cross-origin

When admin HTML is on **port 80** and Flask on **5000**:

- **Login** may set cookie on Flask origin **or** return **`X-Admin-Token`** bearer.
- **`_ADMIN_TOKENS`** is **in-memory** — **lost on process restart**; users re-login.
- For production, prefer **same-origin** nginx routing **`/api/*`** to Flask.

---

## 7. Environment checklist

| Variable | Local | Production |
|----------|-------|------------|
| `FLASK_SECRET_KEY` | Dev default OK | **Required** unique |
| `PORT` | 5000 | Set by platform |
| `LUXSCALE_CORS_ORIGINS` | Often default | **Set** to site URL |
| `LUXSCALE_ADMIN_*` | Default | **Change** |
| `LUXSCALE_DASHBOARD_API_BASE` | `http://127.0.0.1:5000` | Public API URL if dashboard static |

---

*End of back-end split documentation.*
