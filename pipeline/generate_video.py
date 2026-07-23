"""
pipeline/generate_video.py
===========================
KBS 머니올라 쇼츠 — 동영상 합성 모듈 (세로 1080x1920)
PNG 프레임 + MP3 오디오 + ASS 자막 → MP4 (45~60초 고정)
"""
import os
import sys
import json
import subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from generate_subtitles import _frame_stem_to_audio_id

TARGET_MIN = float(os.environ.get("TARGET_MIN_SECONDS", "45"))
TARGET_MAX = float(os.environ.get("TARGET_MAX_SECONDS", "60"))
TARGET_IDEAL = (TARGET_MIN + TARGET_MAX) / 2

BGM_VOLUME = 0.05  # 나레이션 대비 낮은 볼륨(쇼츠는 여백이 적어 더 낮게)


def get_audio_duration(mp3_path: str) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", mp3_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        dur = float(result.stdout.strip())
        return dur if dur > 0 else 2.0
    except Exception:
        return 2.0


def build_section_video(png_path: str, mp3_path: str, out_path: str) -> bool:
    duration = get_audio_duration(mp3_path)
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", png_path,
        "-i", mp3_path,
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest", "-t", f"{duration:.3f}",
        out_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ❌ 실패: {os.path.basename(out_path)}")
        print(result.stderr[-600:])
        return False
    print(f"  ✅ {os.path.basename(out_path)} ({duration:.1f}초)")
    return True


def concat_videos(video_list: list, out_path: str) -> bool:
    list_file = out_path.replace(".mp4", "_list.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for v in video_list:
            f.write(f"file '{os.path.abspath(v)}'\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", out_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    os.remove(list_file)
    if result.returncode != 0:
        print("  ❌ 영상 합치기 실패")
        print(result.stderr[-400:])
        return False
    print("  ✅ 합치기 완료")
    return True


def adjust_to_target_duration(input_path: str, output_path: str, current_duration: float) -> float:
    """45~60초 범위를 벗어나면 배속(최대 ±10%)으로 미세 조정한다. 그 이상
    벗어나면(예: TTS가 과하게 길어짐) 배속을 더 걸지 않고 그대로 두어 음질
    저하를 막는다 — 그 경우 quality_gate.py가 경고를 남긴다."""
    import shutil
    if TARGET_MIN <= current_duration <= TARGET_MAX:
        shutil.copy2(input_path, output_path)
        print(f"  ✅ 영상 길이 정상 ({current_duration:.1f}초)")
        return 1.0

    speed = current_duration / TARGET_IDEAL
    speed = max(0.9, min(1.1, speed))
    print(f"  ⏱ 길이 보정 ({current_duration:.1f}초) → {speed:.3f}배속")
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-filter_complex", f"[0:v]setpts={1/speed:.4f}*PTS[v];[0:a]atempo={speed:.4f}[a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-crf", "20", "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ❌ 길이 조정 실패: {result.stderr[-400:]}")
        shutil.copy2(input_path, output_path)
        return 1.0
    return speed


def burn_subtitles(video_path: str, ass_path: str, out_path: str) -> bool:
    if not os.path.isfile(ass_path):
        print(f"  ⚠️ ASS 자막 파일 없음: {ass_path}")
        return False
    ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")
    cmd = ["ffmpeg", "-y", "-i", video_path, "-vf", f"ass={ass_escaped}",
           "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-c:a", "copy", out_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ❌ 자막 합성 실패: {result.stderr[-400:]}")
        return False
    return True


def mix_bgm(video_path: str, bgm_path: str, out_path: str) -> bool:
    import shutil
    if not os.path.isfile(bgm_path):
        print("  ⚠️ BGM 없음 → BGM 없이 진행")
        shutil.copy2(video_path, out_path)
        return True
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-stream_loop", "-1", "-i", bgm_path,
        "-filter_complex",
        f"[1:a]volume={BGM_VOLUME}[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", out_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ⚠️ BGM 믹싱 실패({result.stderr[-300:]}) → BGM 없이 진행")
        shutil.copy2(video_path, out_path)
    return True


def run(lang: str = "KO"):
    lang = lang.upper()
    root = os.path.join(_HERE, "..")
    frames_dir = os.path.join(root, "output", lang, "frames")
    audio_dir = os.path.join(root, "output", lang, "audio")
    video_dir = os.path.join(root, "output", lang, "video")
    os.makedirs(video_dir, exist_ok=True)

    asset_map_path = os.path.join(root, "output", lang, "asset_map.json")
    with open(asset_map_path, encoding="utf-8") as f:
        frame_paths = json.load(f).get("frames", [])

    script_path = os.path.join(root, "output", lang, "scripts", "script.json")
    with open(script_path, encoding="utf-8") as f:
        sections = json.load(f).get("sections", [])

    print(f"🎯 방송 목표 길이: {TARGET_MIN:.0f}~{TARGET_MAX:.0f}초")

    section_clips = []
    for i, frame_path in enumerate(frame_paths):
        stem = os.path.splitext(os.path.basename(frame_path))[0]
        audio_id = _frame_stem_to_audio_id(stem, sections)
        mp3_path = os.path.join(audio_dir, f"{audio_id}.mp3")
        if not os.path.isfile(mp3_path):
            print(f"  ❌ 오디오 없음: {mp3_path}")
            sys.exit(1)
        clip_path = os.path.join(video_dir, f"clip_{i:02d}_{audio_id}.mp4")
        if not build_section_video(frame_path, mp3_path, clip_path):
            sys.exit(1)
        section_clips.append(clip_path)

    print("\n🔗 프레임 영상 합치는 중...")
    concat_path = os.path.join(video_dir, "concat.mp4")
    if not concat_videos(section_clips, concat_path):
        sys.exit(1)

    current_duration = get_audio_duration(concat_path)
    print(f"\n⏱ 합친 영상 길이: {current_duration:.1f}초")

    adjusted_path = os.path.join(video_dir, "adjusted.mp4")
    speed = adjust_to_target_duration(concat_path, adjusted_path, current_duration)

    ass_path = os.path.join(root, "output", lang, "subtitles", "subtitle.ass")
    with_subs_path = os.path.join(video_dir, "with_subtitles.mp4")
    print("\n📝 자막 처리 중...")
    if speed != 1.0:
        # 배속이 걸리면 자막 타임라인도 동일 비율로 줄여야 나레이션과 어긋나지
        # 않는다(time_scale=1/speed) — step1/step2와 동일한 보정 패턴.
        import generate_subtitles as gs
        gs.generate_ass(sections, lang, ass_path, frame_order=frame_paths, time_scale=1 / speed)
        print(f"  [subtitle] 배속 보정 적용: time_scale={1 / speed:.4f}")
    if not burn_subtitles(adjusted_path, ass_path, with_subs_path):
        with_subs_path = adjusted_path

    bgm_path = os.path.join(root, "assets", "music", "bgm.mp3")
    final_path = os.path.join(video_dir, "final.mp4")
    print("\n🎵 BGM 믹싱 중...")
    mix_bgm(with_subs_path, bgm_path, final_path)

    duration = get_audio_duration(final_path)
    size_mb = os.path.getsize(final_path) / (1024 * 1024)
    print(f"\n{'='*50}\n✅ 최종 쇼츠 완성!\n   파일: {final_path}\n   크기: {size_mb:.1f} MB\n"
          f"   길이: {duration:.1f}초 (목표: {TARGET_MIN:.0f}~{TARGET_MAX:.0f}초)\n{'='*50}")


if __name__ == "__main__":
    lang = sys.argv[1] if len(sys.argv) > 1 else "KO"
    run(lang)
