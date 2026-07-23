"""
pipeline/generate_voice.py
TTS 생성 모듈 — 프리미엄 TTS 파이프라인(stock-briefing-step1/step2 이식)

provider_priority(config/audio.yml, 기본 azure→elevenlabs→openai) 순서로
합성한다. ELEVENLABS_API_KEY + ELEVENLABS_VOICE_ID가 등록되면 STEP-1/STEP-2와
동일한 클론 목소리를 자동으로 쓴다(브랜드 일관성 — 세 영상 모두 같은 목소리).
"""
import os
import json
import shutil
import time
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from config_audio import (
    apply_pronunciation_rules, build_providers,
    LOUDNESS_TARGET_LUFS, LOUDNESS_TRUE_PEAK, LOUDNESS_RANGE,
)
from assets.tts_providers import synthesize_with_fallback
from assets.audio_post import (
    apply_post_processing, measure_duration, measure_loudness,
    detect_advice_language, build_audio_report,
)


def _build_jobs(sections: list, lang: str) -> list:
    jobs = []
    audio_base = f"output/{lang}/audio"
    for section in sections:
        sid = section.get("id", "")
        label = section.get("label", sid)
        narration = section.get("narration", "")
        if sid and narration:
            jobs.append((narration, f"{audio_base}/{sid}.mp3", label))
    return jobs


def _synthesize_job(providers, text: str, out_path: str, job_id: str) -> dict:
    warnings = detect_advice_language(text)
    processed_text = apply_pronunciation_rules(text)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    raw_path = out_path + ".raw.mp3"
    ok, provider_name = synthesize_with_fallback(providers, processed_text, raw_path)

    if not ok:
        return {
            "id": job_id, "provider": "", "duration_seconds": 0.0,
            "speed": 1.0, "loudness_lufs": None, "warnings": warnings, "success": False,
        }

    post_ok = apply_post_processing(
        raw_path, out_path, speed=1.0,
        target_lufs=LOUDNESS_TARGET_LUFS, true_peak=LOUDNESS_TRUE_PEAK,
        loudness_range=LOUDNESS_RANGE,
    )
    if not post_ok:
        print("    ⚠️ 후처리(loudnorm) 실패 → 원본 합성 파일 그대로 사용")
        shutil.move(raw_path, out_path)
    elif os.path.isfile(raw_path):
        os.remove(raw_path)

    duration = measure_duration(out_path)
    loudness = measure_loudness(out_path)
    return {
        "id": job_id, "provider": provider_name, "duration_seconds": round(duration, 2),
        "speed": 1.0, "loudness_lufs": loudness, "warnings": warnings, "success": True,
    }


def run(lang: str = "KO"):
    lang = lang.upper()

    providers = build_providers()
    configured = [p.name for p in providers if p.is_configured()]
    if not configured:
        raise EnvironmentError(
            "❌ 사용 가능한 TTS provider가 없습니다. OPENAI_API_KEY(또는 "
            "AZURE_SPEECH_KEY/AZURE_SPEECH_REGION, ELEVENLABS_API_KEY) 환경변수를 "
            "설정하세요."
        )

    print(f"🎙️ TTS provider 우선순위: {[p.name for p in providers]} (사용 가능: {configured})")

    script_path = f"output/{lang}/scripts/script.json"
    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    sections = script.get("sections", [])
    jobs = _build_jobs(sections, lang)
    total = len(jobs)
    print(f"\n🎙️ TTS 생성 시작 — 총 {total}개 작업\n")

    success_count = 0
    audio_files = []
    report_entries = []

    for i, (text, out_path, label) in enumerate(jobs, 1):
        print(f"  [{i}/{total}] {label}")
        job_id = os.path.splitext(os.path.basename(out_path))[0]
        entry = _synthesize_job(providers, text, out_path, job_id)
        success = entry.pop("success")

        if success:
            print(f"    ✅ 완료 → {out_path} (provider={entry['provider']}, "
                  f"{entry['duration_seconds']:.1f}s)")
            success_count += 1
            audio_files.append({"label": label, "path": out_path})
        else:
            print(f"    ❌ 실패 → {out_path}")

        report_entries.append(entry)
        time.sleep(0.3)

    summary = {"total": total, "success": success_count, "failed": total - success_count, "files": audio_files}
    summary_path = f"output/{lang}/audio/summary.json"
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    audio_report = build_audio_report(report_entries)
    with open(f"output/{lang}/audio_report.json", "w", encoding="utf-8") as f:
        json.dump(audio_report, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*40}\n🎉 TTS 완료! 성공: {success_count}/{total}개\n{'='*40}\n")


if __name__ == "__main__":
    lang = sys.argv[1] if len(sys.argv) > 1 else "KO"
    run(lang)
