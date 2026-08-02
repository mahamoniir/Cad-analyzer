# IES catalog, merge, and path resolution

## 1. Overview

The back-end maps **(API luminaire name, wattage)** → **absolute path** to an **`.ies`** file under **`ies-render/`**. Two sources are merged:

1. **Legacy embedded map** — **`luxscale/fixture_ies_catalog.py`** `_LEGACY_IES_RELATIVE`
2. **Folder scan** — **`luxscale/sc_ies_scan.py`** walks **`ies-render/SC-ies/`** and overrides same keys

**`merged_ies_relative_map()`** returns `Dict[(luminaire_name, power_w), relative_path]`.

---

## 2. Generated JSON snapshot (not runtime-only)

**`write_fixture_ies_catalog_json()`** writes **`assets/fixture_ies_catalog.json`** for review/diff.  
**Runtime** uses **`merged_ies_direct_map()`** in memory (merge + scan), not only the file.

---

## 3. `sc_ies_scan` — folder naming

**`luxscale/sc_ies_scan.py`**:

- Root: **`ies-render/SC-ies`**
- Folder prefixes map to API strings, e.g. **`SC SPOT`** → **`SC downlight`**, **`SC PANEL`** → **`SC backlight`**, **`SC HIGHBAY`** → **`SC highbay`**
- Regex: **`NAME ###W`** extracts wattage; **SC PANEL 36W** style for panels
- Picks one **`.ies`** per folder (prefer filename containing **`{watt}W`**)

---

## 4. `fixture_map.json` (richer catalog)

**`luxscale/fixture_catalog.py`**:

- Loads **`assets/fixture_map.json`** (cached).
- Each **entry** includes **`api_luminaire_name`**, **`power_w`**, **`relative_ies_path`**, **`ies_file_exists`**, image URLs, optional **`online`** block.

**`resolve_ies_path`** order (**`luxscale/ies_fixture_params.py`**):

1. **`fixture_entry_for_api(name, power)`** — if **`ies_file_exists`** and file on disk → return absolute path under **`ies-render/`**.
2. Else **`merged_ies_relative_map().get((name, int(power)))`** + **`normalize_relative_ies_path`** + join with **`IES_RENDER_ROOT`**.

**`normalize_relative_ies_path`:** ensures paths under **`SC-Database/`** or **`SC-ies/`** convention.

---

## 5. `catalog_luminaire_power_options()`

Used by **`determine_luminaire`**: builds **`{ luminaire: sorted unique wattages }`** from all keys of **`merged_ies_relative_map()`**.

---

## 6. Admin updates

**`PUT /api/admin/fixture-map`** overwrites **`assets/fixture_map.json`** and calls **`clear_fixture_map_cache()`** so the next resolve picks up new IES links.

---

## 7. “Database” wording

There is **no SQL database**. The **IES database** in product terms is:

- **Merged in-memory map** + optional **`fixture_ies_catalog.json`** snapshot  
- **`ies.json`** index + **`ies_json/*.json`** photometry blobs (see next doc)

---

Next: [ies-parsing-and-photometry.md](./ies-parsing-and-photometry.md)
