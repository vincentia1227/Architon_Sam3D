import json
from pathlib import Path
from datetime import datetime
import trimesh
import glob


def obj_to_furniture_json(
    obj_file_path: str,
    furniture_id: str = None,
    furniture_type: str = "furniture",
    label: str = None,
    material: str = "unknown",
    weight: float = None,
    preferred_room: str = "bedroom",
    scale_to_mm: float = 1000,  # meter to mm로 변환할 때 사용
):
    """
    OBJ 파일을 지정된 JSON 포맷으로 변환합니다.
    
    Args:
        obj_file_path: OBJ 파일 경로
        furniture_id: 가구 ID (기본값: 파일명 기반)
        furniture_type: 가구 타입 (예: "bed_q", "closet", "table")
        label: 가구 라벨 (기본값: 파일명)
        material: 재료 (기본값: "unknown")
        weight: 무게 kg (기본값: 계산되지 않음)
        preferred_room: 추천 방 (기본값: "bedroom")
        scale_to_mm: 스케일 변환 계수 (기본값: 1000 = meter to mm)
    
    Returns:
        dict: 변환된 JSON 데이터
    """
    
    obj_path = Path(obj_file_path)
    
    # 파일 존재 여부 확인
    if not obj_path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없음: {obj_path}")
    
    # 1) OBJ 메시 로드
    mesh = trimesh.load(obj_path, process=False)
    print(f"[로드됨] {obj_path.name}")
    print(f"  메시 타입: {type(mesh)}")
    
    # 2) Scene인 경우 처리
    if isinstance(mesh, trimesh.Scene):
        print(f"  Scene으로 로드됨 (geometry 수: {len(mesh.geometry)})")
        valid_meshes = [g for g in mesh.geometry.values() 
                       if g is not None and len(g.vertices) > 0]
        if not valid_meshes:
            raise ValueError(f"유효한 메시가 없음: {obj_path}")
        mesh = trimesh.util.concatenate(tuple(valid_meshes))
    
    # 3) 메시 검증
    if mesh is None or len(mesh.vertices) == 0:
        raise ValueError(f"메시에 정점이 없음: {obj_path}")
    
    # 4) 기본 정보
    num_vertices = len(mesh.vertices)
    num_faces = len(mesh.faces) if (hasattr(mesh, 'faces') and mesh.faces is not None) else 0
    print(f"  정점: {num_vertices}, 면: {num_faces}")
    
    # 5) Bounding box & 크기 계산
    bounds = mesh.bounds  # [[min_x, min_y, min_z], [max_x, max_y, max_z]]
    dimensions = mesh.extents  # [width, depth, height]
    
    # mm 단위로 변환
    width = int(round(dimensions[0] * scale_to_mm))
    depth = int(round(dimensions[1] * scale_to_mm))
    height = int(round(dimensions[2] * scale_to_mm))
    
    print(f"  크기: {width}mm x {depth}mm x {height}mm")
    
    # 6) ID 및 라벨 설정
    if furniture_id is None:
        furniture_id = obj_path.stem  # 확장자 제외한 파일명
    
    if label is None:
        label = obj_path.stem.replace('_', '-')
    
    # 7) JSON 구조 생성
    furniture_data = {
        "id": furniture_id,
        "type": furniture_type,
        "label": label,
        "mesh_file": obj_path.name,
        "dimensions": {
            "w": width,
            "d": depth,
            "h": height
        },
        "attributes": {
            "material": material,
            "weight": weight,
            "preferred_room": preferred_room
        },
        "constraints": {
            "mustAgainstWall": True,
            "windowAffinity": True,
            "avoidDoor": True,
            "clearance": {
                "front": 800,
                "back": 0,
                "left": 600,
                "right": 600
            },
            "priority": 1
        }
    }
    
    return furniture_data


def convert_all_obj_files(
    folder_path: str = ".",
    output_file: str = "furniture_data.json",
    furniture_configs: dict = None
):
    """
    폴더 내의 모든 OBJ 파일을 JSON으로 변환합니다.
    
    Args:
        folder_path: OBJ 파일이 있는 폴더 경로
        output_file: 출력 JSON 파일 경로
        furniture_configs: 각 파일별 설정 딕셔너리
                          {파일명: {type, label, material, weight, preferred_room, ...}}
    """
    
    folder_path = Path(folder_path)
    obj_files = list(folder_path.glob("*.obj"))
    
    if not obj_files:
        print(f"경고: {folder_path}에서 OBJ 파일을 찾을 수 없음")
        return
    
    print(f"\n변환 시작: {len(obj_files)}개의 OBJ 파일")
    print("=" * 60)
    
    furniture_list = []
    
    for idx, obj_file in enumerate(obj_files, 1):
        try:
            # 각 파일별 설정 가져오기
            file_config = {}
            if furniture_configs and obj_file.stem in furniture_configs:
                file_config = furniture_configs[obj_file.stem]
            
            # 기본 설정
            furniture_id = file_config.get("id", f"f{idx:02d}")
            furniture_type = file_config.get("type", obj_file.stem)
            label = file_config.get("label", obj_file.stem.replace('_', '-'))
            material = file_config.get("material", "wood")
            weight = file_config.get("weight", None)
            preferred_room = file_config.get("preferred_room", "bedroom")
            
            # 변환
            furniture_json = obj_to_furniture_json(
                str(obj_file),
                furniture_id=furniture_id,
                furniture_type=furniture_type,
                label=label,
                material=material,
                weight=weight,
                preferred_room=preferred_room
            )
            
            furniture_list.append(furniture_json)
            print(f"✓ [{idx}/{len(obj_files)}] {obj_file.name} -> {furniture_id}\n")
            
        except Exception as e:
            print(f"✗ [{idx}/{len(obj_files)}] {obj_file.name} 변환 실패")
            print(f"  오류: {str(e)}\n")
    
    # 5) JSON 파일로 저장
    output_data = {
        "furniture": furniture_list,
        "metadata": {
            "created": datetime.now().isoformat(),
            "total_items": len(furniture_list),
            "version": "1.0"
        }
    }
    
    output_path = folder_path / output_file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print("=" * 60)
    print(f"✓ 완료! 저장됨: {output_path}")
    print(f"  총 {len(furniture_list)}개 가구 항목")
    
    return output_path


if __name__ == "__main__":
    # 현재 폴더의 모든 OBJ 파일 변환
    # 각 파일별 커스텀 설정 (선택사항)
    configs = {
        "Sample_bed": {
            "type": "bed_q",
            "label": "queen-size-bed",
            "material": "wood",
            "weight": 80,
            "preferred_room": "bedroom"
        },
        "Sample_closet": {
            "type": "closet",
            "label": "wardrobe-closet",
            "material": "wood",
            "weight": 120,
            "preferred_room": "bedroom"
        },
        "Sample_table": {
            "type": "table",
            "label": "dining-table",
            "material": "wood",
            "weight": 60,
            "preferred_room": "living_room"
        }
    }
    
    # 변환 실행
    convert_all_obj_files(
        folder_path=".",
        output_file="furniture_data.json",
        furniture_configs=configs
    )
