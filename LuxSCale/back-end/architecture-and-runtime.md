# Architecture and runtime

## 1. Repository roles

| Path | Role |
|------|------|
| **`app.py`** | Flask application: HTTP API, CORS, admin routes, serves `assets/`, `admin/dashboard.html` |
| **`luxscale/`** | Python package: lighting calc, IES helpers, uniformity, logging, paths |
| **`ies-render/`** | IES files, `module/ies_parser.py`, manifests (`ies.json`), photometry JSON blobs |
| **`standards/`** | `standards_cleaned.json`, keywords, aliases — loaded by Flask and static front-end |
| **`assets/`** | `app_settings.json`, `fixture_map.json`, `fixture_ies_catalog.json` (snapshots) |
| **`api/`** | **PHP** `submit.php`, `get.php` for XAMPP stacks; `api/data/studies/*.json` stored payloads |
| **`calculation_logs/`** | Per-request **calculation trace** `.txt` (timing steps) |
| **`uniformity_reports/`** | Session **uniformity** `.txt` exports from calculator |
| **`luxscale_app.log`** | **Rolling** application log at repo root (see [logging-and-artifacts.md](./logging-and-artifacts.md)) |

---

## 2. Python package `luxscale`

| Module area | Responsibility |
|-------------|------------------|
| **`lighting_calc/`** | `calculate_lighting`, geometry (`calculate_spacing`, `determine_zone`), constants (`maintenance_factor`, `led_efficacy`) |
| **`uniformity_calculator.py`** | IES-based grid illuminance, U₀/U₁, report formatting |
| **`ies_fixture_params.py`** | Load IES → `IESData`, `resolve_ies_path`, `ies_params_for_file`, beam angle |
| **`fixture_ies_catalog.py`** | Merge legacy + `sc_ies_scan` → `(luminaire, power)` → relative path |
| **`fixture_catalog.py`** | Read **`assets/fixture_map.json`** for IES path + images |
| **`photometry_ies_adapter.py`** | Build `IESData` from catalog blob (fast path) |
| **`ies_json_loader.py`** | Read `ies-render/ies.json` + `ies_json/*.json` blobs |
| **`sc_ies_scan.py`** | Scan `ies-render/SC-ies/` folders → API names + wattage |
| **`app_settings.py`** | Merge defaults + `assets/app_settings.json`; validation helpers |
| **`app_logging.py`** | `log_step`, `log_exception` → `luxscale_app.log` |
| **`calculation_trace.py`** | `CalculationTrace` → `calculation_logs/calculation_steps_*.txt` |
| **`paths.py`** | `project_root()` for all file resolution |

---

## 3. Application entry

- **Development:** `python app.py` or `flask run` with `FLASK_APP=app.py`.
- **Port:** `PORT` env (default **5000**); `app.run(host="0.0.0.0", port=PORT)` at bottom of `app.py` for PaaS (e.g. Railway).

---

## 4. Environment variables (primary)

| Variable | Purpose |
|----------|---------|
| **`FLASK_SECRET_KEY`** | Flask session signing (change in production) |
| **`LUXSCALE_CORS_ORIGINS`** | Comma-separated allowed origins for `flask-cors` (empty → localhost defaults) |
| **`PORT`** | Listen port |
| **`LUXSCALE_DASHBOARD_API_BASE`** | Flask base URL written to `assets/dashboard_config.json` for static admin on XAMPP |
| **`LUXSCALE_ADMIN_USER`** / **`LUXSCALE_ADMIN_PASSWORD`** | Admin login (defaults exist — override in prod) |
| **`LUXSCALE_ADMIN_TOKEN_TTL_S`** | Bearer token lifetime for cross-origin admin API |

`.env` is loaded via **`python-dotenv`** from repo root when `app.py` starts.

---

## 5. Dual stack: Flask vs PHP

| Capability | Flask | PHP (`api/`) |
|------------|-------|----------------|
| Lighting calculation | **Yes** (`/calculate`) | No |
| Study storage | **Yes** (`/api/submit`, `/api/get`) | **Yes** (`submit.php`, `get.php`) |
| Same JSON contract | Intended parity | Front-end tries both |

Static HTML on **Apache (XAMPP)** can call **`http://127.0.0.1:5000`** for calc while using **PHP** on port 80 for submit if Flask submit is unavailable.

---

Next: [flask-api-and-routes.md](./flask-api-and-routes.md)
