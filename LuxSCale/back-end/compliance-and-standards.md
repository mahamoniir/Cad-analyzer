# Compliance and standards logic

## 1. Source of requirements

| Mode | Average illuminance | Uniformity U₀ |
|------|---------------------|---------------|
| **`standard_row` from `standards_cleaned.json`** | **`Em_r_lx`** | **`Uo`** (parsed as float) |
| **Legacy `place`** | **`define_places[place]["lux"]`** | **`define_places[place]["uniformity"]`** |

Standard rows include **`ref_no`**, **`category`**, **`task_or_activity`**, **`Em_u_lx`**, **`Ez_lx`**, walls/ceiling, CRI, UGR — the **solver enforces** **(Em,r lux, U₀)** using **IES work-plane `E_avg` when the grid ran**, and **lumen-method average only if no grid**; other columns are informational for PDF/UI.

**Why:** The lumen-method **Average Lux** can be much higher than the **spatial mean illuminance** from the IES integration (e.g. backlight / wide distribution). Lux compliance therefore uses **`E_avg_grid_lx`** when present so pass/fail matches what **U₀** is based on. **`Lux compliance basis`** on each row records **`IES work plane E_avg`** vs **`lumen method (no IES grid)`**.

---

## 2. Row-level compliance (`_row_with_compliance_metrics`)

Implemented in **`luxscale/lighting_calc/calculate.py`**.

### 2.1 Average illuminance

- **`Average Lux`** = lumen-method value (still returned for reference).
- **Lux compliance** uses **`_avg_lux_for_compliance`**: **`E_avg_grid_lx`** if the IES grid ran, else **`Average Lux`**.

**Lux gap:**

```text
avg = E_avg_grid_lx  (if present)  else  Average Lux
lux_gap = max(0, required_lux - avg)
```

Compliance requires **`lux_gap <= 1e-9`** → work-plane spatial average (or lumen fallback) **≥** required.

### 2.2 Uniformity U₀

- **`U0_calculated`** from **`compute_uniformity_metrics`** when IES run succeeds (**`E_min / E_avg`** on the work-plane grid).

**U₀ gap:**

```text
u0_gap = required_u0                    if U0_calculated is missing
u0_gap = max(0, required_u0 - U0_calculated)   otherwise
```

Compliance: **`u0_gap <= 1e-9`** → calculated U₀ **≥** required.

### 2.3 Combined flag

```text
is_compliant = (lux_gap <= 1e-9) and (u0_gap <= 1e-9)
```

---

## 3. Accepting a solution

In the main fixture loop, a row is **accepted** when **`lux_ok and u0_ok`**:

- Sets **`Selection`** = **`least_fixture_count_compliant`**.
- Appends to **`results`** until **`max_solutions_cap`** (from **`get_max_solutions_total`** / fast cap).
- Stops further search for that luminaire/power line when first compliant found (**`break`** inner loop).

---

## 4. When no row passes: closest candidate + fallback

### 4.1 Closest non-compliant

If no compliant row in the inner sweep, the code keeps the **best** candidate by sort key **`(U0 gap, Lux gap, total power, fixture count)`** — used as **seed** for fallback.

### 4.2 Uniformity fixture sweep fallback (`_uniformity_fallback_sweep_rows`)

- Triggered if **`results`** empty but **`closest_candidates`** non-empty.
- Sweeps **upward** in fixture count with **relaxed** average lux cap (**`max_avg_lux_mult`** ~1.65) to tighten spacing and improve U₀.
- Still requires lumen average **≥** required lux.
- Outputs rows with **`Selection`** = **`uniformity_fixture_sweep_fallback`** — may still be **non-compliant**; **`calculation_meta.no_compliant_options`** reflects whether **any** row has **`is_compliant`**.

---

## 5. `calculation_meta` (returned to client)

Populated at end of **`calculate_lighting`** (see code for full keys), including:

- **`total_solutions_returned`**, **`max_solutions_cap`**, **`calc_mode`** (`fast` / `full`).
- **`used_uniformity_sweep_fallback`**, **`no_compliant_options`**, **`had_non_compliant_closest`**.
- **`interior_height_threshold_m`** for UI copy.

---

## 6. Standards JSON loading on server

**`app.py`:** **`load_standards_file`** caches **`standards_cleaned.json`** / **`standards_keywords_upgraded.json`** from **`standards/`** next to `app.py`.

**Ref resolution:** **`cleaned_row_by_ref(ref_no)`** linear search — OK for moderate file size.

---

Next: [ies-catalog-and-resolution.md](./ies-catalog-and-resolution.md)
