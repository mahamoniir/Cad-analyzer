# IES parsing and photometry pipeline

## 1. LM-63 parser (Type C)

**`ies-render/module/ies_parser.py`** is loaded **dynamically** by **`luxscale/ies_fixture_params._get_ies_parser_class()`** via **`importlib.util`** so importing **`luxscale`** does not pull optional **Qt**/heavy **`ies-render/module/__init__.py`** dependencies.

**`IES_Parser(path).ies_data`** yields **`IESData`**:

- Vertical / horizontal angle arrays
- Candela values per horizontal angle
- **`lumens_per_lamp`**, **`multiplier`**, **`num_lamps`**
- Opening dimensions, shape, **`max_value`** (candela)

---

## 2. Fast path: catalog index + JSON blob

**`luxscale/photometry_ies_adapter.try_load_ies_data_via_catalog(abs_path)`:**

1. Convert absolute path → **relative** under **`ies-render/`** (`absolute_ies_path_to_relative`).
2. **`index_entry_by_relative_path(rel)`** reads **`ies-render/ies.json`** (`luxscale/ies_json_loader.py`).
3. If entry **`status == "ok"`** and **`photometry_json`** points to a file, **`load_photometry_blob`** loads **`ies_json/...json`**.
4. **`ies_data_from_index_and_blob`** constructs **`IESData`** from stored arrays — **same numerics** as parsing the **`.ies`** text (avoids LM-63 round-trip drift).

**If any step fails** → returns **`None`** → caller parses **`.ies`** with **`IES_Parser`**.

---

## 3. Caching

**`@lru_cache(maxsize=128)`** on **`_load_ies_data_cached(ies_path)`** in **`ies_fixture_params.py`**.

**`clear_ies_data_cache()`** — call after regenerating **`ies.json`** or blobs (documented in docstring).

---

## 4. `ies_params_for_file(ies_path)`

Returns a **dict** for calculator rows:

| Key | Source |
|-----|--------|
| **`lumens_per_lamp`** | `lumens_per_lamp * multiplier` from `IESData` |
| **`beam_angle_deg`** | **`approx_beam_angle_deg`** — 50% of peak candela on first horizontal slice, interpolated half-angle × 2 |
| **`max_candela`**, **`shape`**, openings | From `IESData` |

---

## 5. Beam angle algorithm (summary)

**`approx_beam_angle_deg`** in **`ies_fixture_params.py`** (aligned with **`ies_viewer`**):

- Uses vertical candela row at **`horizontal_angles[0]`**
- Finds first crossing below **threshold × peak** (default **0.5** = half-power)
- Linear interpolation between angle samples → **half-angle**, returns **2 × half-angle**

---

## 6. Uniformity calculator consumption

**`uniformity_calculator.compute_uniformity_metrics`** calls **`_load_ies_data_cached`** — same **`IESData`** as above, then **inverse-square** candela summation on a work-plane grid (see uniformity doc).

---

## 7. Invalid or negative lumens in file

If header lumens ≤ 0, **`calculate_lighting`** may treat IES as failed and use **rated** **W × lm/W** for flux scaling; uniformity still uses **`max(lumens_per_fixture, 1e-9)`** with notes in metrics (**`ies_scale_note`**).

---

**See also:** [../lighting/12-supporting-modules-catalog-and-settings.md](../lighting/12-supporting-modules-catalog-and-settings.md) (`photometry_ies_adapter`, `ies_json_loader`, resolution order).

---

Next: [uniformity-grid-and-reports.md](./uniformity-grid-and-reports.md)
