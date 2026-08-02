# Uniformity grid and text reports

## 1. Role

**`luxscale/uniformity_calculator.py`** computes **point-by-point horizontal illuminance** on a work plane using **Type C candela** data from **`IESData`**, then:

- **U₀** = **E_min / E_avg**
- **U₁** = **E_min / E_max**

This is **not** the same as the lumen-method average alone; it reflects **distribution** (spacing, height, photometry).

---

## 2. Grid density

**`uniformity_grid_n_for_room(length, width)`** returns N for **N×N** sample points:

- Larger floor areas → **smaller N** (performance — O(N² × fixtures × candela sum)).

---

## 3. Fixture and sample layout (symmetric)

- **Fixture centres:** **`fixture_positions_symmetric_grid(length, width, best_x, best_y)`** — full room, centres at **(i+½)L/nx**, **(j+½)W/ny**.
- **Work-plane samples:** **`work_plane_grid_symmetric`** — same half-bay inset rule as fixtures.
- **Height:** Ceiling = **`ceiling_height_m`**; work plane default **`0.75 m`** (`DEFAULT_WORK_PLANE_HEIGHT_M`).

---

## 4. Flux per grid slot

Total installed lumens distributed across **`best_x * best_y`** grid positions with **`best_x * best_y = num_fixtures`** (exact factorization); **`phi_each = lumens_per_fixture`** per cell (**see** `geometry.calculate_spacing`, calculation-engine).

Candela is scaled by **`phi_each / phi_ies`**. The ratio **design lumens / IES header lumens** is **clamped** (defaults **0.25…4** in `constants.py`) so placeholder or wrong IES lumens cannot blow up grid **lx** far above the lumen-method average (**`ies_scale_note`** records when clamping applies).

For each grid point, sum **illuminance_at_point_horizontal** over all fixture positions (candela scaled by design lumens vs file lumens).

---

## 5. Text report files

**`format_uniformity_report_txt`** builds a human-readable chunk per option.

**`write_uniformity_session_txt(header, body_chunks)`** writes:

- **Directory:** **`uniformity_reports/`** (under project root)
- **Filename:** **`uniformity_calc_YYYYMMDD_HHMMSS.txt`**
- **Content:** Header (room, required lux/U₀, grid size) + concatenated option chunks

Invoked from **`calculate_lighting`** after results are finalized (**`log_step("uniformity: report file", path)`**).

---

## 6. Session chunk sync

**`_sync_uniformity_report_chunks`** rebuilds or aligns uniformity text chunks with **`results`** list (including placeholders when IES missing).

---

## 7. Relation to compliance

Compliance uses **`U0_calculated`** from this module vs **`required_uniformity`** from the standard row — see [compliance-and-standards.md](./compliance-and-standards.md).

---

Next: [logging-and-artifacts.md](./logging-and-artifacts.md)
