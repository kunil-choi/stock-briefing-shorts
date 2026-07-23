"""
pipeline/generate_subtitles.py
================================
ASS(Advanced SubStation Alpha) 자막 파일 생성 모듈 — 세로형(1080x1920) 전용.

프레임 파일명 → 오디오 ID 매핑:
  00_hook.png    → hook.mp3
  01_top3.png    → top_3.mp3
  02_top2.png    → top_2.mp3
  03_top1.png    → top_1.mp3
  99_closing.png → closing.mp3
"""
import os
import sys
import json
import re
import subprocess
import math

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from assets.config import W, H

ASS_HEADER = f"""\
[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
Title: KBS 머니올라 쇼츠 자막

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,NotoSansCJK,52,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,30,30,60,1
Style: Warning,NotoSansCJK,40,&H004040FF,&H000000FF,&H00000000,&HAA000000,-1,0,0,0,100,100,0,0,1,2,1,2,30,30,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

CHARS_PER_LINE = 22   # 세로 화면은 가로폭이 좁으므로 한 줄 최대 글자 수를 줄임
MAX_LINES      = 3
SILENT_DURATION = 3.0

FRAME_TO_AUDIO_ID = {
    "00_hook": "hook",
    "01_top3": "top_3",
    "02_top2": "top_2",
    "03_top1": "top_1",
    "99_closing": "closing",
}


def _frame_stem_to_audio_id(stem: str, sections: list = None) -> str:
    return FRAME_TO_AUDIO_ID.get(stem, stem)


def _ts(seconds: float) -> str:
    total = max(0.0, seconds)
    h = int(total // 3600)
    m = int((total % 3600) // 60)
    s = int(total % 60)
    cs = int((total - int(total)) * 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def _get_audio_duration(mp3_path: str) -> float:
    if not mp3_path or not os.path.isfile(mp3_path):
        return SILENT_DURATION
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", mp3_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        dur = float(result.stdout.strip())
        return dur if dur > 0 else SILENT_DURATION
    except Exception:
        return SILENT_DURATION


_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?。])(?!\d)\s*')


def _split_into_sentences(text: str) -> list:
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text.strip()) if s.strip()]


def _wrap_words(text: str, width: int) -> list:
    words = [w for w in text.split(" ") if w]
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}" if current else word
        if len(candidate) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        if len(word) <= width:
            current = word
        else:
            for i in range(0, len(word), width):
                piece = word[i:i + width]
                if len(piece) == width:
                    lines.append(piece)
                else:
                    current = piece
    if current:
        lines.append(current)
    return lines


def _split_subtitle_text(text: str) -> list:
    if not text:
        return []
    sentences = _split_into_sentences(text)
    chunks, current = [], ""
    for sent in sentences:
        test = (current + " " + sent).strip()
        lines_needed = math.ceil(len(test) / CHARS_PER_LINE)
        if lines_needed > MAX_LINES and current:
            chunks.append(current)
            current = sent
        else:
            current = test
    if current:
        chunks.append(current)
    final = []
    max_len = CHARS_PER_LINE * MAX_LINES
    for chunk in chunks:
        if len(chunk) <= max_len:
            final.append(chunk)
        else:
            final.extend(_wrap_words(chunk, max_len))
    return final if final else _wrap_words(text, max_len)


def _format_ass_text(text: str) -> str:
    lines = _wrap_words(text, CHARS_PER_LINE)
    return r"\N".join(lines[:MAX_LINES])


def _make_dialogue_events(narration_text: str, subtitle_text: str,
                           start_time: float, duration: float, style: str = "Default") -> list:
    if not subtitle_text or duration <= 0:
        return []

    narr_sentences = _split_into_sentences(narration_text)
    sub_sentences = _split_into_sentences(subtitle_text)

    if narr_sentences and sub_sentences and len(narr_sentences) == len(sub_sentences):
        pairs = list(zip((len(s) for s in narr_sentences), sub_sentences))
    else:
        pairs = [(len(s), s) for s in (sub_sentences or [subtitle_text])]

    total_weight = sum(w for w, _ in pairs) or 1
    events = []
    t_cursor = start_time

    for weight, sub_sentence in pairs:
        seg_duration = duration * (weight / total_weight)
        chunks = _split_subtitle_text(sub_sentence)
        if not chunks:
            t_cursor += seg_duration
            continue
        chunk_total_len = sum(len(c) for c in chunks) or 1
        for chunk in chunks:
            chunk_duration = seg_duration * (len(chunk) / chunk_total_len)
            t_start = t_cursor
            t_end = t_start + chunk_duration - 0.08
            ass_text = _format_ass_text(chunk)
            events.append(f"Dialogue: 0,{_ts(t_start)},{_ts(t_end)},{style},,0,0,0,,{ass_text}")
            t_cursor += chunk_duration

    return events


def _build_subtitle_map(sections: list) -> dict:
    subtitle_map = {}
    for section in sections:
        sid = section.get("id", "")
        if sid == "closing":
            continue  # 클로징은 화면에 유의사항 전문이 이미 텍스트로 표시됨
        narr = section.get("narration", "")
        sub = section.get("subtitle", "")
        if sid and sub:
            subtitle_map[sid] = (narr, sub)
    return subtitle_map


def generate_ass(sections: list, lang: str, out_path: str, frame_order: list = None,
                  time_scale: float = 1.0) -> str:
    """time_scale: 최종 영상이 배속 조정(atempo/setpts)된 경우의 보정 계수.
    예) 영상을 1.05배속으로 줄였다면 1/1.05를 전달해 자막 타임라인도 동일
    비율로 줄여야 나레이션과 어긋나지 않는다(step1/step2와 동일한 패턴)."""
    subtitle_map = _build_subtitle_map(sections)
    audio_base = os.path.join("output", lang, "audio")

    events = []
    current_time = 0.0

    if not frame_order:
        print("  [subtitle] ⚠️ frame_order 없음 — subtitle_map 순서로 처리")
        for audio_id, (narration_text, subtitle_text) in subtitle_map.items():
            mp3_path = os.path.join(audio_base, f"{audio_id}.mp3")
            duration = _get_audio_duration(mp3_path) * time_scale
            style = "Warning" if "closing" in audio_id else "Default"
            slide_events = _make_dialogue_events(narration_text, subtitle_text, current_time, duration, style)
            events.extend(slide_events)
            current_time += duration
    else:
        for frame_path in frame_order:
            stem = os.path.splitext(os.path.basename(frame_path))[0]
            audio_id = _frame_stem_to_audio_id(stem)
            mp3_path = os.path.join(audio_base, f"{audio_id}.mp3")
            duration = _get_audio_duration(mp3_path) * time_scale

            narration_text, subtitle_text = subtitle_map.get(audio_id, ("", ""))
            style = "Warning" if "closing" in audio_id else "Default"

            if subtitle_text:
                slide_events = _make_dialogue_events(narration_text, subtitle_text, current_time, duration, style)
                events.extend(slide_events)
                print(f"  [subtitle] {stem} → {audio_id}: {duration:.1f}s, {len(slide_events)}개 이벤트")
            else:
                print(f"  [subtitle] {stem} → {audio_id}: {duration:.1f}s, 자막 없음")

            current_time += duration

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8-sig") as f:
        f.write(ASS_HEADER)
        f.write("\n".join(events))
        f.write("\n")

    print(f"\n✅ ASS 자막 생성 완료: {out_path} | 총 길이: {current_time:.1f}초")
    return out_path


def run(lang: str = "KO"):
    lang = lang.upper()
    script_path = f"output/{lang}/scripts/script.json"
    asset_map_path = f"output/{lang}/asset_map.json"
    out_path = f"output/{lang}/subtitles/subtitle.ass"

    if not os.path.isfile(script_path):
        print(f"❌ script.json 없음: {script_path}")
        sys.exit(1)

    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)
    sections = script.get("sections", [])

    frame_order = None
    if os.path.isfile(asset_map_path):
        with open(asset_map_path, encoding="utf-8") as f:
            asset_map = json.load(f)
        frame_order = asset_map.get("frames", [])

    generate_ass(sections, lang, out_path, frame_order)


if __name__ == "__main__":
    lang = sys.argv[1] if len(sys.argv) > 1 else "KO"
    run(lang)
