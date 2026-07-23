"""
pipeline/voice_config.py
========================
목소리(TTS) 설정 관리 모듈. STEP-1/STEP-2와 동일한 ElevenLabs 클론 목소리를
쓰도록 DEFAULT_VOICE_PRESET="custom" + ELEVENLABS_VOICE_ID Secret 조합을
그대로 따른다(브랜드 일관성 — 세 영상 모두 같은 목소리).
"""

MODEL_ID = "eleven_multilingual_v2"
DEFAULT_VOICE_ID = ""

VOICE_SETTINGS = {
    "stability": 0.72,
    "similarity_boost": 0.88,
    "style": 0.10,
    "use_speaker_boost": True,
}

AUDIO_FORMAT = "mp3_44100_128"

VOICE_PRESETS = {
    "matilda": "XrExE9yKIg1WjnnlVkGX",
    "rachel": "21m00Tcm4TlvDq8ikWAM",
    "charlie": "IKne3meq5aSn9XLyUdCD",
    "daniel": "onwK4e9ZLuTAKqWW03F9",
    "custom": "",  # 커스텀 클론 목소리 ID (보통 Secret으로 주입)
}

DEFAULT_VOICE_PRESET = "custom"


def get_voice_id() -> str:
    """환경변수 → 프리셋 → 기본값 순으로 Voice ID 를 반환합니다."""
    import os
    env_id = os.environ.get("ELEVENLABS_VOICE_ID", "").strip()
    if env_id:
        return env_id
    preset_id = VOICE_PRESETS.get(DEFAULT_VOICE_PRESET, "").strip()
    if preset_id:
        return preset_id
    return DEFAULT_VOICE_ID


def apply_phoneme_rules(text: str) -> str:
    """narration 텍스트에 발음 교정 규칙을 적용합니다. 자막에는 사용하지 마세요."""
    from config_audio import apply_pronunciation_rules
    return apply_pronunciation_rules(text)
