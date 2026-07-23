# pipeline/generate_assets.py
"""
쇼츠 에셋 생성 진입점. 사용법: python pipeline/generate_assets.py [KO|ko|en]
훅 → TOP3 → TOP2 → TOP1 → 클로징 순으로 5개 프레임을 렌더링한다.
"""
import os, sys, json

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from assets.builders import build_hook, build_rank_card, build_closing
from assets.render import close_renderer


def run(lang: str = "KO"):
    lang = lang.upper()

    root = os.path.join(_HERE, "..")
    script_path = os.path.join(root, "output", lang, "scripts", "script.json")
    out_dir = os.path.join(root, "output", lang, "frames")
    media_map_path = os.path.join(root, "output", lang, "media", "media_map.json")

    os.makedirs(out_dir, exist_ok=True)

    if not os.path.isfile(script_path):
        print(f"❌ script.json을 찾을 수 없습니다: {script_path}")
        sys.exit(1)

    with open(script_path, encoding="utf-8") as f:
        data = json.load(f)

    sections = data.get("sections", [])
    print(f"📂 script.json 로드 완료 (섹션 수: {len(sections)})")

    media_map = {}
    if os.path.isfile(media_map_path):
        with open(media_map_path, encoding="utf-8") as f:
            media_map = json.load(f)
        resolved = sum(1 for v in media_map.values() if v.get("source") != "fallback")
        print(f"🖼️ media_map.json 로드 완료 ({resolved}/{len(media_map)}개 실사진 확보)")
    else:
        print("⚠️ media_map.json 없음 — 사진 없이 그라디언트 배경으로 진행")

    asset_map = {"frames": [], "lang": lang}

    try:
        asset_map["frames"].append(build_hook(data, out_dir, media_map=media_map))
        rank_sections = sorted(
            (s for s in sections if s.get("id", "").startswith("top_")),
            key=lambda s: s.get("rank", 0), reverse=True,  # 3위→2위→1위 카운트다운 순서
        )
        for sec in rank_sections:
            asset_map["frames"].append(build_rank_card(sec, out_dir, media_map=media_map))
        asset_map["frames"].append(build_closing(data, out_dir))
    finally:
        close_renderer()

    map_path = os.path.join(root, "output", lang, "asset_map.json")
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(asset_map, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 완료: {len(asset_map['frames'])}개 프레임 → {out_dir}")
    return asset_map


if __name__ == "__main__":
    lang = sys.argv[1] if len(sys.argv) > 1 else "KO"
    run(lang)
