# stock-briefing-shorts

📺 **KBS 머니올라** 관심종목 쇼츠(세로 9:16, 45~60초) 전용 레포입니다.
[`stock-briefing-step1`](https://github.com/kunil-choi/stock-briefing-step1)
(morning_core, 관심종목 8분 미드폼 본편)과 같은 날 함께 발행하는 **발견
(discovery) 채널** 역할 — 쇼츠로 짧게 훅을 걸어 본편으로 유입을 유도한다.

## 왜 별도 레포인가 (STEP-1과의 관계)

STEP-1은 본편 제작 과정에서 개체명 추출·미디어 검색·서사 재정렬 등 무거운
파이프라인을 거치고, 최종 결과물(영상/프레임/오디오)은 GitHub Actions
아티팩트로만 남고 레포에 커밋되지 않는다(30일 보관 후 소멸). 그래서 이
레포가 STEP-1의 "완성된 영상"을 가져다 자르는 방식은 크로스 레포 아티팩트
다운로드에 의존하게 되어 취약하다.

대신 이 레포는 STEP-1과 **같은 원본 데이터**
([`stock-briefing-v3-1`](https://github.com/kunil-choi/stock-briefing-v3-1)의
`data/briefing_data.json`)를 직접 소비해서, STEP-1이 8분짜리 심층 분석으로
다루는 종목들 중 "오늘 가장 많이 언급된 TOP3"만 뽑아 자체적으로 45~60초
쇼츠를 새로 만든다 — v3-1/v3-2/v3, step1/step2가 이미 쓰고 있는 "각 레포가
상위 레포의 JSON을 raw.githubusercontent.com으로 직접 소비한다"는 패턴을
그대로 따른 것이다. STEP-1의 심층 분석을 다시 하지 않고, 대신 STEP-1이
아직 만들지 않는 "카운트다운 랭킹" 관점을 추가한다.

## 랭킹 산식

v3-1의 `briefing_data.json`은 STEP-1의 후처리된 `script.json`과 스키마가
다르다 — `{"market_leaders": [...], "stocks": [...], ...}` 구조이며, 각
종목 항목에 v3-1이 이미 채널별(뉴스/경제방송/유튜브) 언급을 가중합산해
계산해둔 `weighted_score`가 들어있다. `pipeline/assets/ranking.py`는 이
값을 자체 재계산하지 않고, `market_leaders`(대형 주도주) + `stocks`(관심
종목) 두 배열을 합쳐 `weighted_score` 내림차순 TOP3을 그대로 뽑는다 —
v3-1이 이미 반영한 채널별 가중치·중복 보정 로직과 어긋나는 걸 피하기
위함이다.

## 세로형(9:16) 레이아웃

`pipeline/assets/html_theme.py`/`builders.py`는 STEP-1/STEP-2(1920x1080
가로, 카드 나열형 "PPT 슬라이드")와 달리 매 프레임이 **전체화면 사진 배경 +
텍스트 카드 하나**만 있는 "포스터형" 레이아웃이다(1080x1920,
`pipeline/assets/config.py`). 쇼츠는 스크롤 중 찰나에 시선을 붙잡아야 해서
텍스트 밀도를 의도적으로 낮췄다.

프레임 구성(카운트다운 순서): `훅(TOP3 예고) → TOP3 → TOP2 → TOP1 → 클로징`

## 재사용한 컴포넌트 (STEP-1/STEP-2와 동일 소스)

| 컴포넌트 | 출처 |
|---|---|
| 클론 음성 provider 체인(`tts_providers.py`/`config_audio.py`) | STEP-1/STEP-2와 동일 — `ELEVENLABS_VOICE_ID`를 STEP-1/STEP-2와 같은 값으로 등록하면 세 영상이 같은 목소리를 쓴다(브랜드 일관성) |
| 연합뉴스/KBS 이미지 검색(`media_providers.py`/`media_pipeline.py`/`rights_review.py`) | STEP-2에서 이식 — 출처 워터마크(`사진: 연합뉴스`/`사진: KBS`) 포함 |
| 발음 교정 사전(`config/pronunciation_ko.yml`) | STEP-1과 동일 |
| 섹터 fallback 이미지(`assets/sector_fallback/`) | STEP-1과 동일 |

## 트리거 체인

```
(수동) workflow_dispatch → shorts.yml
  script(v3-1 데이터로 TOP3 선정) → voice / assets(media_map.json 생성 → 프레임 렌더링) → video → generate_metadata.py → quality_gate.py
```

과금(OpenAI/TTS) 방지를 위해 자동 dispatch를 걸지 않았다. `stock-briefing-v3-1`의
`docs/index.html`로 데이터가 준비됐는지 확인한 뒤 이 레포 Actions 탭에서 수동으로
`workflow_dispatch`를 실행한다. 운영이 안정되면 `stock-briefing-v3-1`의 cron
직후(v3-1→v3-2 자동 dispatch와 같은 패턴)에 이 레포도 자동 dispatch하도록
연결할 수 있다.

**권장 발행 순서**: 이 쇼츠를 STEP-1 본편보다 **먼저** 발행해 훅으로 쓰는 걸
권장한다(가로형 롱폼과 세로형 쇼츠는 유튜브의 서로 다른 추천 인벤토리라
자기잠식 없이 유입을 서로 밀어준다).

## YouTube Shorts 요건

- 세로/정사각 영상 + 재생시간 3분 이하 + 제목 또는 설명에 `#Shorts` — 이
  레포는 45~60초 고정 타깃(`config/schedule.yml`)이라 항상 요건을 만족한다.
  `pipeline/quality_gate.py`가 180초 초과 시 파이프라인을 중단시켜 실수로
  요건을 벗어나는 걸 방지한다.

## 필요 Secrets

| Secret | 용도 | 없을 때 |
|---|---|---|
| `OPENAI_API_KEY` | 스크립트 생성(필수) + TTS 폴백 | 필수 |
| `ELEVENLABS_API_KEY` / `ELEVENLABS_VOICE_ID` | 클론 목소리(STEP-1/STEP-2와 동일 값 권장) | OpenAI TTS로 폴백 |
| `AZURE_SPEECH_KEY` / `AZURE_SPEECH_REGION` | Azure TTS(선택) | 다음 provider로 폴백 |
| `YONHAP_API_KEY` / `KBS_API_KEY` | 이미지 검색(선택) | 공개 검색 경로로 동작 |
| `NAVER_SEARCH_CLIENT_ID` / `NAVER_SEARCH_CLIENT_SECRET` | 이미지 검색 보완(선택) | 해당 커넥터 비활성 |

## 로컬 실행

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=...
python pipeline/generate_script.py KO
python pipeline/generate_voice.py KO
python pipeline/generate_media.py KO
python pipeline/generate_assets.py KO
python pipeline/generate_subtitles.py KO
TARGET_MIN_SECONDS=45 TARGET_MAX_SECONDS=60 python pipeline/generate_video.py KO
python pipeline/generate_metadata.py KO
python pipeline/quality_gate.py KO
```

드라이런(과금 없이 구조만 검증): `SCRIPT_MOCK=1 TTS_MOCK=1 MEDIA_MOCK=1`을
위 각 단계에 붙여서 실행하거나, Actions 탭에서 `dry_run` 입력을 켜서 실행한다.

## 다음 단계 (이번 범위 아님)

- `stock-briefing-v3-1`의 cron 뒤에 자동 dispatch 연결(현재는 수동 실행만)
- STEP-1 본편으로 연결되는 링크를 설명란/최종 카드에 더 적극적으로 노출
- 트래픽 데이터가 쌓이면 market_leaders/stocks 가중치나 top_n을 조정
