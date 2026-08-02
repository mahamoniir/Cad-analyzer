# Logging, traces, and on-disk artifacts

## 1. Application log: `luxscale_app.log`

**Module:** **`luxscale/app_logging.py`**

| Property | Value |
|----------|--------|
| **Path** | **`{project_root}/luxscale_app.log`** (`project_root()` from **`luxscale.paths`**) |
| **Logger name** | `luxscale` |
| **Level** | INFO (default) |
| **Handlers** | **File** (UTF-8) + **Stream** (console) |
| **Format** | `%(asctime)s \| %(levelname)s \| %(message)s` |

### 1.1 `log_step(step, result=None, **detail)`

- Builds a single INFO line: **`STEP: <name>`**, optional **`RESULT: repr`**, optional **`DETAIL: json.dumps(detail)`**.
- Used throughout **`app.py`** (e.g. `POST /calculate`, errors) and **`calculate_lighting`** (fixture sweep, IES parse, uniformity).

### 1.2 `log_exception(step, exc)`

- Logs **ERROR** with **`exc_info`** for stack traces.

### 1.3 Typical contents

- API receive/validation
- Per-luminaire sweep parameters (`min_fixtures`, `max_fixtures`)
- IES path resolved or parse failure
- Uniformity report path
- Admin save errors

**Production:** rotate or ship **`luxscale_app.log`** via log aggregator; file grows unbounded without external rotation.

---

## 2. Calculation traces: `calculation_logs/*.txt`

**Module:** **`luxscale/calculation_trace.py`**, class **`CalculationTrace`**.

| Property | Value |
|----------|--------|
| **Directory** | **`calculation_logs/`** under project root |
| **Filename pattern** | **`calculation_steps_YYYYMMDD_HHMMSS.txt`** |
| **Trigger** | **`trace.save()`** after **`POST /calculate`** in **`app.py`** |

**Content:**

- Title, start timestamp
- Table: **step name** | **delta_s** (since previous) | **sum_s** (cumulative)
- Optional **key: value** detail lines per step
- **TOTAL** wall time

**Response field:** API returns **`calculation_trace_file`** with the saved path (or omitted on failure).

---

## 3. Uniformity session reports: `uniformity_reports/*.txt`

**Module:** **`luxscale/uniformity_calculator.write_uniformity_session_txt`**

| Property | Value |
|----------|--------|
| **Directory** | **`uniformity_reports/`** |
| **Filename pattern** | **`uniformity_calc_YYYYMMDD_HHMMSS.txt`** |

**Content:**

- Header: room dimensions, ceiling height, required lux/U₀, grid N, symmetric layout description
- Per-option blocks: luminaire, power, IES path, E_min/E_avg/E_max, U₀/U₁, fixture coordinates, ASCII plan, sample grid lux matrix

**Logging:** **`log_step("uniformity: report file", rep_path)`** in **`calculate_lighting`**.

---

## 4. Study JSON (Flask submit)

**Path:** **`api/data/studies/<token>.json`** (Flask `_STUDIES_DIR` in `app.py`).

Wrapper structure includes **`token`**, **`saved_at`**, **`payload`** (full client body). **Not** the same as log files — **application data**.

**PHP** `api/submit.php` may use a parallel directory — see deployment doc.

---

## 5. Git and privacy

- **`calculation_logs/`**, **`uniformity_reports/`**, **`luxscale_app.log`**, and **`api/data/studies/*.json`** may contain **project dimensions and client metadata**. Add to **`.gitignore`** for public repos if needed (some repos ignore only part of `api/data`).

---

Next: [dependencies-and-python-libraries.md](./dependencies-and-python-libraries.md)
