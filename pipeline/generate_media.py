# pipeline/generate_media.py
"""
media_map.json 생성 진입점 (stock-briefing-step1/step2의 연합뉴스/KBS 검색
파이프라인 이식판). 사용법: python pipeline/generate_media.py [KO|ko|en]

script.json의 top_1/top_2/top_3 섹션 종목명을 검색 키워드로 써서
AssetSearchService(연합뉴스/KBS/naver_discovery 검색 → 점수화 → 권리분류)로
장면별 사진을 고른다. 훅(hook) 장면은 TOP1 종목 사진을 재사용한다(쇼츠는
장면이 4개뿐이라 별도 검색을 하지 않고 임팩트가 가장 큰 1위 사진으로 오프닝을
장식).

MEDIA_MOCK=1 환경변수(또는 config/media.yml의 mock_mode: true)를 설정하면
실제 네트워크 요청 없이 MockProvider로 동작한다.
"""
import os
import sys
import json

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import config_media
from assets.asset_search_service import AssetSearchService


def build_scene_sections(script: dict) -> list:
    sections_out = []
    top1_name = ""
    for s in script.get("sections", []):
        sid = s.get("id", "")
        if not sid.startswith("top_"):
            continue
        name = (s.get("name") or "").strip()
        if not name:
            continue
        if sid == "top_1":
            top1_name = name
        sections_out.append({
            "id": sid,
            "visual_keywords": [name],
            "preferredSources": ["YONHAP", "KBS_WEBSITE"],
        })

    sections_out.insert(0, {
        "id": "hook",
        "visual_keywords": [top1_name] if top1_name else ["코스피"],
        "preferredSources": ["YONHAP", "KBS_WEBSITE"],
    })
    return sections_out


def run(lang: str = "KO"):
    lang = lang.upper()
    root = os.path.join(_HERE, "..")
    script_path = os.path.join(root, "output", lang, "scripts", "script.json")
    img_dir = os.path.join(root, "output", lang, "media")
    map_path = os.path.join(img_dir, "media_map.json")
    manifest_path = os.path.join(img_dir, "asset_manifest.json")
    log_path = os.path.join(root, "data", "media", "license_log.csv")

    if not os.path.isfile(script_path):
        print(f"❌ script.json을 찾을 수 없습니다: {script_path}")
        sys.exit(1)

    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    scene_plan = {"sections": build_scene_sections(script)}
    print(f"  [media] 검색 대상 섹션 {len(scene_plan['sections'])}개 (훅 1 + TOP1~3)")

    service = AssetSearchService(config_media.PROVIDER_NAMES, mock_mode=config_media.MOCK_MODE)
    if config_media.MOCK_MODE:
        print("  [media] MOCK_MODE=on → MockProvider만 사용")
    media_map, asset_manifest = service.build_for_scene_plan(
        scene_plan, img_dir, log_path,
        cache_dir=config_media.ASSET_CACHE_DIR,
        dedup_window_days=config_media.DEDUP_WINDOW_DAYS,
        dedup_threshold=config_media.DEDUP_HAMMING_THRESHOLD,
        max_candidates=config_media.MAX_CANDIDATES_PER_SECTION,
    )

    os.makedirs(img_dir, exist_ok=True)
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(media_map, f, ensure_ascii=False, indent=2)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(asset_manifest, f, ensure_ascii=False, indent=2)

    resolved = sum(1 for v in media_map.values() if v.get("source") != "fallback")
    print(f"✅ media_map 생성 완료! 총 {len(media_map)}개 섹션 (검색 성공 {resolved} / 폴백 {len(media_map) - resolved}) → {map_path}")
    return media_map


if __name__ == "__main__":
    lang = sys.argv[1] if len(sys.argv) > 1 else "KO"
    run(lang)
