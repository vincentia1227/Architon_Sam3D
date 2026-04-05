from pathlib import Path

import numpy as np
import open3d as o3d


def clean_mesh_for_rhino(mesh: o3d.geometry.TriangleMesh) -> o3d.geometry.TriangleMesh:
    vertices = np.asarray(mesh.vertices)
    triangles = np.asarray(mesh.triangles)

    if vertices.size == 0:
        return mesh

    # NaN/Inf가 들어있는 버텍스 제거
    valid_mask = np.isfinite(vertices).all(axis=1)
    if not valid_mask.all():
        print(f"  Removing invalid vertices: {np.count_nonzero(~valid_mask)}")
        index_map = -np.ones(len(vertices), dtype=int)
        index_map[valid_mask] = np.arange(valid_mask.sum())

        new_vertices = vertices[valid_mask]
        new_triangles = index_map[triangles]
        new_triangles = new_triangles[(new_triangles >= 0).all(axis=1)]

        mesh.vertices = o3d.utility.Vector3dVector(new_vertices)
        mesh.triangles = o3d.utility.Vector3iVector(new_triangles)

    mesh.remove_unreferenced_vertices()
    mesh.remove_degenerate_triangles()
    mesh.remove_duplicated_triangles()
    mesh.remove_duplicated_vertices()
    mesh.remove_non_manifold_edges()
    mesh.compute_vertex_normals()

    # 원점 주변으로 이동
    center = mesh.get_center()
    mesh.translate(-center)

    return mesh


def clean_all_obj_in_folder(folder: Path) -> None:
    obj_files = sorted(folder.glob("*.obj"))
    if not obj_files:
        print(f"No OBJ files found in {folder}")
        return

    print(f"Found {len(obj_files)} OBJ files:")
    for f in obj_files:
        print(f"  - {f.name}")

    for obj_path in obj_files:
        print(f"\n[LOAD] {obj_path.name}")
        mesh = o3d.io.read_triangle_mesh(str(obj_path))
        if len(mesh.vertices) == 0:
            print(f"  [WARN] Mesh has no vertices, skipped.")
            continue

        print(f"  Original vertices: {len(mesh.vertices)}, faces: {len(mesh.triangles)}")

        mesh = clean_mesh_for_rhino(mesh)

        print(f"  Cleaned vertices: {len(mesh.vertices)}, faces: {len(mesh.triangles)}")

        clean_obj = obj_path.with_name(obj_path.stem + "_rhino.obj")
        clean_stl = obj_path.with_name(obj_path.stem + "_rhino.stl")

        o3d.io.write_triangle_mesh(str(clean_obj), mesh)
        print(f"[OK] Saved OBJ: {clean_obj.name}")

        o3d.io.write_triangle_mesh(str(clean_stl), mesh)
        print(f"[OK] Saved STL: {clean_stl.name}")


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    clean_all_obj_in_folder(base_dir)

