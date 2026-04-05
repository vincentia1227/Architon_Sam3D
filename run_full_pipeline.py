from pathlib import Path
from datetime import datetime
import json

from ply_to_obj_open3d import convert_ply_folder_to_obj
from clean_obj_for_rhino import clean_all_obj_in_folder
from convert_obj_to_json import obj_to_furniture_json


def get_output_modeling_folders(base_dir: Path) -> list[Path]:
    """
    Output_Modeling 폴더와 그 하위 폴더(1단계)를 모두 반환.
    각 폴더 안의 .ply / .obj를 처리할 때 사용.
    """
    output_modeling = base_dir / "Output_Modeling"
    folders: list[Path] = []

    if output_modeling.exists():
        folders.append(output_modeling)
        for p in sorted(output_modeling.iterdir()):
            if p.is_dir():
                folders.append(p)

    return folders


def step1_ply_to_obj(folders: list[Path]) -> None:
    """
    각 폴더 안의 .ply 파일들을 OBJ/STL로 변환.
    결과는 동일한 폴더 안에 저장된다.
    """
    print("\n=== STEP 1: PLY → OBJ/STL (open3d) ===")
    for folder in folders:
        print(f"\n[PLY→OBJ] Folder: {folder}")
        convert_ply_folder_to_obj(folder)


def step2_clean_obj_for_rhino(folders: list[Path]) -> None:
    """
    각 폴더 안의 .obj 파일들을 정리해서 *_rhino.obj / *_rhino.stl 로 저장.
    """
    print("\n=== STEP 2: Clean OBJ for Rhino ===")
    for folder in folders:
        print(f"\n[Clean OBJ] Folder: {folder}")
        clean_all_obj_in_folder(folder)


def step3_obj_to_json(base_dir: Path, output_json_dir: Path) -> Path | None:
    """
    Output_Modeling 아래의 *_rhino.obj 파일들을 모두 수집해서
    하나의 furniture_data.json 으로 변환.

    JSON 파일은 Output_JSON 폴더 안에 저장.
    """
    print("\n=== STEP 3: OBJ → JSON ===")

    output_modeling = base_dir / "Output_Modeling"
    if not output_modeling.exists():
        print(f"[WARN] Output_Modeling 폴더가 없음: {output_modeling}")
        return None

    rhino_objs = sorted(output_modeling.rglob("*_rhino.obj"))
    if not rhino_objs:
        print(f"[WARN] *_rhino.obj 파일을 찾지 못했습니다: {output_modeling}")
        return None

    print(f"Found {len(rhino_objs)} cleaned OBJ files:")
    for p in rhino_objs:
        print(f"  - {p.relative_to(base_dir)}")

    furniture_list = []
    for idx, obj_path in enumerate(rhino_objs, 1):
        try:
            furniture_json = obj_to_furniture_json(
                str(obj_path),
                furniture_id=f"f{idx:02d}",
                furniture_type=obj_path.stem,
                label=obj_path.stem.replace("_", "-"),
            )
            furniture_list.append(furniture_json)
            print(f"✓ [{idx}/{len(rhino_objs)}] {obj_path.name}")
        except Exception as e:
            print(f"✗ [{idx}/{len(rhino_objs)}] {obj_path.name} 변환 실패: {e}")

    if not furniture_list:
        print("[WARN] 변환된 가구 항목이 없습니다.")
        return None

    output_json_dir.mkdir(exist_ok=True)
    output_path = output_json_dir / "furniture_data.json"

    output_data = {
        "furniture": furniture_list,
        "metadata": {
            "created": datetime.now().isoformat(),
            "total_items": len(furniture_list),
            "version": "1.0",
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] JSON 저장 완료: {output_path}")
    print(f"  총 {len(furniture_list)}개 가구 항목")
    return output_path


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    output_json_dir = base_dir / "Output_JSON"

    print("=== Full Pipeline: PLY → OBJ → Clean OBJ → JSON ===")
    print(f"Base dir        : {base_dir}")
    print(f"Output_Modeling : {base_dir / 'Output_Modeling'}")
    print(f"Output_JSON     : {output_json_dir}")

    folders = get_output_modeling_folders(base_dir)
    if not folders:
        print("\n[WARN] Output_Modeling 폴더 또는 내부 폴더를 찾지 못했습니다.")
        return

    # 1단계: PLY → OBJ/STL
    step1_ply_to_obj(folders)

    # 2단계: OBJ 정리 (Rhino용)
    step2_clean_obj_for_rhino(folders)

    # 3단계: 정리된 OBJ → JSON
    step3_obj_to_json(base_dir, output_json_dir)

    print("\n=== Pipeline 완료 ===")


if __name__ == "__main__":
    main()

