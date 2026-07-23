import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta

from config_schedule import DURATION

TARGET_MIN_SECONDS = int(os.environ.get("TARGET_MIN_SECONDS", str(DURATION.get("min_seconds", 45))))
TARGET_MAX_SECONDS = int(os.environ.get("TARGET_MAX_SECONDS", str(DURATION.get("max_seconds", 60))))

KST = timezone(timedelta(hours=9))
REQUIRED_METADATA_FIELDS = [
    "briefing_type", "briefing_date", "status", "title", "description", "tags",
]


def check_metadata(root: str = ".") -> None:
    today_dir = os.path.join(root, "output", datetime.now(KST).strftime("%Y-%m-%d"))
    meta_path = os.path.join(today_dir, "metadata.json")
    if not os.path.isfile(meta_path):
        raise SystemExit(f"metadata.json 없음: {meta_path}")

    meta = json.load(open(meta_path, encoding="utf-8"))
    missing = [f for f in REQUIRED_METADATA_FIELDS if not meta.get(f)]
    if missing:
        raise SystemExit(f"metadata.json 필수 필드 누락: {missing} ({meta_path})")

    if meta.get("status") not in ("success", "partial"):
        raise SystemExit(f"metadata.json status={meta.get('status')!r} — 실패로 표시됨 ({meta_path})")

    if "#Shorts" not in meta.get("title", "") and "#Shorts" not in meta.get("description", ""):
        print("⚠️  제목/설명에 #Shorts 태그가 없습니다 — YouTube가 Shorts로 인식하지 못할 수 있습니다.")

    duration = meta.get("duration_seconds", 0)
    if duration and not (TARGET_MIN_SECONDS <= duration <= TARGET_MAX_SECONDS):
        print(f"⚠️  duration_seconds={duration}가 목표 범위({TARGET_MIN_SECONDS}~{TARGET_MAX_SECONDS}s)를 벗어남 — 경고만 출력")
    if duration and duration > 180:
        raise SystemExit(f"❌ 영상 길이가 180초를 초과({duration}s) — YouTube Shorts 요건(3분 이하)을 벗어남")

    print(f"✅ metadata.json 검증 통과 ({meta_path}, status={meta['status']})")


def media_duration(path: str) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def main(lang: str = "KO"):
    base = os.path.join("output", lang.upper())
    asset_map = os.path.join(base, "asset_map.json")
    audio_dir = os.path.join(base, "audio")
    video_path = os.path.join(base, "video", "final.mp4")

    if not os.path.isfile(asset_map):
        raise SystemExit(f"asset_map.json 없음: {asset_map}")

    from generate_subtitles import _frame_stem_to_audio_id

    frames = json.load(open(asset_map, encoding="utf-8")).get("frames", [])
    missing = []
    for frame in frames:
        stem = os.path.splitext(os.path.basename(frame))[0]
        audio_id = _frame_stem_to_audio_id(stem)
        mp3 = os.path.join(audio_dir, f"{audio_id}.mp3")
        if not os.path.isfile(mp3):
            missing.append(mp3)

    if missing:
        print("누락 오디오:")
        for m in missing:
            print(m)
        raise SystemExit(1)

    if not os.path.isfile(video_path):
        raise SystemExit(f"final.mp4 없음: {video_path}")

    duration = media_duration(video_path)
    print(f"final.mp4 duration={duration:.2f}s")
    if duration > 180:
        raise SystemExit(f"❌ 영상 길이가 180초를 초과({duration:.1f}s) — YouTube Shorts 요건(3분 이하)을 벗어남")
    if not (TARGET_MIN_SECONDS <= duration <= TARGET_MAX_SECONDS):
        print(f"⚠️  목표 범위({TARGET_MIN_SECONDS}~{TARGET_MAX_SECONDS}s)를 벗어남: {duration:.2f}s — 경고만 출력(180초 이내이므로 Shorts 자격은 유지)")

    check_metadata()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "KO")
