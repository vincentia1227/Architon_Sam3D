# `run_full_pipeline.py` — PLY → OBJ → Rhino cleanup → JSON

From the folder that contains the script, this pipeline turns point clouds (`.ply`) under **`Output_Modeling`** into meshes, cleans them for Rhino, and writes a single **`Output_JSON/furniture_data.json`** with furniture metadata.

## Prerequisites

- **Python 3.10+** recommended (e.g. `list[Path]` type hints)
- Install the following packages:

| Package   | Role |
|-----------|------|
| `open3d`  | Load PLY, Poisson meshing, OBJ/STL I/O, Step 2 mesh cleanup |
| `numpy`   | Numerical operations |
| `plyfile` | Read `f_dc_*` colors from PLY (e.g. Gaussian Splat) in `ply_to_obj_open3d` |
| `trimesh` | Load OBJ and compute bounds/dimensions in Step 3 (`convert_obj_to_json`) |

Example install:

```bash
pip install open3d numpy plyfile trimesh
```

## Folder layout

The pipeline uses **`base_dir`** = the directory where **`run_full_pipeline.py`** lives.

- **Input**: `base_dir/Output_Modeling/` and its **immediate subfolders** (one level only). Each such folder’s `*.ply` files are processed.
- **Intermediate outputs**: `.obj` and `.stl` next to each PLY → after Step 2, `*_rhino.obj` and `*_rhino.stl` are added.
- **Final JSON**: `base_dir/Output_JSON/furniture_data.json`

If `Output_Modeling` is missing or nothing is found, the script may print a warning and exit.

## How to run

From the project root:

```bash
python run_full_pipeline.py
```

There are no CLI arguments; paths are always relative to the script’s location.

## Pipeline steps

### Step 1 — PLY → OBJ / STL (`ply_to_obj_open3d`)

- Finds `*.ply` in `Output_Modeling` and in each one-level subfolder.
- Reads the point cloud with Open3D and builds a triangle mesh (e.g. Poisson).
- If the PLY has `f_dc_0`, `f_dc_1`, `f_dc_2`, colors can be applied.
- Writes matching `.obj` and `.stl` files **in the same folder as the PLY**.

### Step 2 — Clean OBJ (`clean_obj_for_rhino`)

- Reads **every** `*.obj` in each target folder and cleans it (remove invalid vertices, duplicate/degenerate faces, non-manifold edges, recenter at origin, etc.).
- Saves `<original_stem>_rhino.obj` and `<original_stem>_rhino.stl`.

> **Note:** This step targets all `.obj` files in the folder. If leftover `*_rhino.obj` files from a previous run are still there, they will be processed again and you may get names like `*_rhino_rhino.obj`. Clean the folder first if you need to avoid that.

### Step 3 — Rhino OBJ → merged JSON (`convert_obj_to_json`)

- Recursively under `Output_Modeling`, collects only **`*_rhino.obj`** files.
- Converts each to a furniture entry and merges them into one list.
- `furniture_data.json` shape:
  - `furniture`: array of items (`id` like `f01`, `f02`, …)
  - `metadata`: `created` (ISO timestamp), `total_items`, `version` (`1.0`)
- If one OBJ fails, it logs the error and continues with the rest.

## Related modules

| File | Role |
|------|------|
| `run_full_pipeline.py` | Orchestrates the full sequence |
| `ply_to_obj_open3d.py` | Step 1 conversion |
| `clean_obj_for_rhino.py` | Step 2 mesh cleanup |
| `convert_obj_to_json.py` | Step 3 JSON (`obj_to_furniture_json`) |

## Troubleshooting

- **No `Output_Modeling`**: Create it and place `.ply` files inside it (or one level down in a subfolder).
- **No JSON in Step 3**: Check that `*_rhino.obj` exists under `Output_Modeling` (Step 2 must have run successfully).
- **Import / dependency errors**: Ensure all packages in the table above are installed.
