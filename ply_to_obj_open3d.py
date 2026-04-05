from pathlib import Path

import open3d as o3d
import numpy as np
from plyfile import PlyData


def pointcloud_to_mesh(
    pcd: o3d.geometry.PointCloud,
    *,
    estimate_normals: bool = True,
    normal_radius: float = 0.05,
    normal_max_nn: int = 50,
    poisson_depth: int = 10,
    density_quantile: float = 0.02,
) -> o3d.geometry.TriangleMesh:
    if estimate_normals or not pcd.has_normals():
        pcd.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(
                radius=normal_radius,
                max_nn=normal_max_nn,
            )
        )
        pcd.orient_normals_consistent_tangent_plane(normal_max_nn)

    # Try Poisson with decreasing depth if it fails
    mesh = None
    densities = None
    depths_to_try = [poisson_depth, max(6, poisson_depth - 2), max(6, poisson_depth - 4), 6]
    
    for depth in depths_to_try:
        try:
            mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
                pcd,
                depth=depth,
            )
            if mesh is not None and len(mesh.vertices) > 0:
                print(f"    Successfully created mesh with depth={depth}")
                break
            else:
                print(f"    Depth {depth}: returned None or empty mesh, retrying...")
                mesh = None
                densities = None
        except Exception as e:
            print(f"    Depth {depth} failed: {e}")
            mesh = None
            densities = None
            continue
    
    if mesh is None or densities is None:
        raise ValueError("Poisson surface reconstruction failed with all depth values")

    densities = np.asarray(densities)
    if 0.0 < density_quantile < 1.0:
        threshold = float(np.quantile(densities, density_quantile))
        mask = densities < threshold
        
        # Check if we would remove too many vertices
        percent_to_remove = (mask.sum() / len(mask)) * 100
        if percent_to_remove > 30:
            print(f"    [SKIP] Density filter would remove {percent_to_remove:.1f}% of vertices, skipping")
        else:
            result = mesh.remove_vertices_by_mask(mask)
            if result is None:
                print(f"    [WARN] Density filter removed all vertices, using original mesh")
            else:
                mesh = result
                print(f"    [OK] Removed {mask.sum()} vertices by density filter")

    # NaN/Inf가 포함된 버텍스를 제거하고, 해당 버텍스를 참조하는 face도 제거
    if mesh is None:
        raise ValueError("Mesh is None after density filtering")
    
    vertices = np.asarray(mesh.vertices)
    triangles = np.asarray(mesh.triangles)

    if vertices.size > 0:
        valid_mask = np.isfinite(vertices).all(axis=1)
        if not valid_mask.all():
            print(f"  Cleaning invalid vertices: {np.count_nonzero(~valid_mask)} removed")
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

    # Final validation
    if len(mesh.vertices) == 0 or len(mesh.triangles) == 0:
        raise ValueError(f"Final mesh is invalid: {len(mesh.vertices)} vertices, {len(mesh.triangles)} triangles")

    # 포인트 클라우드에 색상이 있으면 메시에 할당
    if pcd.has_colors():
        pcd_points = np.asarray(pcd.points)
        pcd_colors = np.asarray(pcd.colors)
        mesh_vertices = np.asarray(mesh.vertices)
        
        # KD-tree를 사용해서 메시의 각 vertex를 가장 가까운 포인트 클라우드 포인트에 매칭
        pcd_tree = o3d.geometry.KDTreeFlann(pcd)
        mesh_colors = np.zeros((len(mesh_vertices), 3), dtype=np.float64)
        
        for i, vertex in enumerate(mesh_vertices):
            k, idx, _ = pcd_tree.search_knn_vector_3d(vertex, 1)
            if k > 0:
                mesh_colors[i] = pcd_colors[idx[0]]
        
        mesh.vertex_colors = o3d.utility.Vector3dVector(mesh_colors)
        print(f"    Applied vertex colors from point cloud")

    return mesh


def convert_ply_folder_to_obj(
    folder: Path,
    *,
    pattern: str = "*.ply",
    overwrite: bool = True,
) -> None:
    ply_files = sorted(folder.glob(pattern))
    if not ply_files:
        print(f"No PLY files found in {folder}")
        return

    print(f"Found {len(ply_files)} PLY files:")
    for f in ply_files:
        print(f"  - {f.name}")

    for ply_path in ply_files:
        obj_path = ply_path.with_suffix(".obj")
        stl_path = ply_path.with_suffix(".stl")
        if obj_path.exists() and not overwrite:
            print(f"[SKIP] {obj_path.name} already exists (use overwrite=True to replace).")
            continue

        print(f"\n[LOAD] {ply_path.name}")
        pcd = o3d.io.read_point_cloud(str(ply_path))
        if len(pcd.points) == 0:
            print(f"[WARN] Point cloud has no points, skipped: {ply_path.name}")
            continue

        print(f"  Points: {len(pcd.points)}")
        
        # f_dc_0, f_dc_1, f_dc_2를 RGB로 변환
        try:
            ply_data = PlyData.read(str(ply_path))
            vertex_data = ply_data['vertex']
            
            # f_dc 속성 확인
            if 'f_dc_0' in vertex_data and 'f_dc_1' in vertex_data and 'f_dc_2' in vertex_data:
                f_dc_0 = np.asarray(vertex_data['f_dc_0'])
                f_dc_1 = np.asarray(vertex_data['f_dc_1'])
                f_dc_2 = np.asarray(vertex_data['f_dc_2'])
                
                # Gaussian Splat SH 0차 계수: c0 = 0.28209479177387814
                c0 = 0.28209479177387814
                rgb = np.stack([f_dc_0, f_dc_1, f_dc_2], axis=1) * c0
                
                # [0, 1] 범위로 정규화
                rgb_min = rgb.min()
                rgb_max = rgb.max()
                if rgb_max > rgb_min:
                    rgb = (rgb - rgb_min) / (rgb_max - rgb_min)
                else:
                    rgb = np.clip(rgb, 0, 1)
                
                # 포인트 클라우드에 색상 추가
                pcd.colors = o3d.utility.Vector3dVector(rgb)
                print(f"  Applied f_dc RGB colors to point cloud")
        except Exception as e:
            print(f"  [WARN] Failed to extract f_dc colors: {e}")

        try:
            mesh = pointcloud_to_mesh(pcd, density_quantile=0.05)
        except (ValueError, RuntimeError) as e:
            print(f"  [ERROR] Failed to create mesh: {e}")
            continue

        print(f"  Mesh vertices: {len(mesh.vertices)}, faces: {len(mesh.triangles)}")

        # 원점 주변으로 이동해서 너무 멀리 떨어진 좌표를 피함
        center = mesh.get_center()
        if np.all(np.isfinite(center)):
            mesh.translate(-center)
        else:
            print("  [WARN] Mesh center contained NaN/Inf. Skipping recentering.")

        # 내보내기 전에 한 번 더 NaN/Inf 검증 및 정리
        vertices = np.asarray(mesh.vertices)
        triangles = np.asarray(mesh.triangles)

        if vertices.size == 0 or triangles.size == 0:
            print(f"  [WARN] Mesh has no valid geometry after processing, skipped: {ply_path.name}")
            continue

        valid_mask = np.isfinite(vertices).all(axis=1)
        if not valid_mask.all():
            invalid_count = int((~valid_mask).sum())
            print(f"  [FIX] Removing {invalid_count} vertices with NaN/Inf before export.")

            index_map = -np.ones(len(vertices), dtype=int)
            index_map[valid_mask] = np.arange(valid_mask.sum())

            new_vertices = vertices[valid_mask]
            new_triangles = index_map[triangles]
            new_triangles = new_triangles[(new_triangles >= 0).all(axis=1)]

            if new_vertices.size == 0 or new_triangles.size == 0:
                print(f"  [WARN] All geometry became invalid after cleanup, skipped: {ply_path.name}")
                continue

            mesh.vertices = o3d.utility.Vector3dVector(new_vertices)
            mesh.triangles = o3d.utility.Vector3iVector(new_triangles)

        # 법선에도 NaN/Inf가 있을 수 있으므로 0으로 강제
        if mesh.has_vertex_normals():
            normals = np.asarray(mesh.vertex_normals)
            if normals.size > 0 and not np.isfinite(normals).all():
                print("  [FIX] Cleaning NaN/Inf in vertex normals.")
                normals[~np.isfinite(normals)] = 0.0
                mesh.vertex_normals = o3d.utility.Vector3dVector(normals)

        # OBJ 내보낼 때는 법선을 쓰지 않도록 해서 NaN 법선 문제를 한 번 더 방지
        # vertex color가 있으면 포함해서 저장
        has_colors = mesh.has_vertex_colors()
        o3d.io.write_triangle_mesh(
            str(obj_path),
            mesh,
            write_vertex_normals=False,
            write_vertex_colors=has_colors,
        )
        print(f"[OK] Saved OBJ: {obj_path.name}" + (" (with vertex colors)" if has_colors else ""))

        o3d.io.write_triangle_mesh(str(stl_path), mesh, write_vertex_colors=has_colors)
        print(f"[OK] Saved STL: {stl_path.name}" + (" (with vertex colors)" if has_colors else ""))


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    convert_ply_folder_to_obj(base_dir)

