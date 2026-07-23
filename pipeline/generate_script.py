# pipeline/generate_script.py
"""
AI 주식 브리핑 — stock-briefing-shorts 스크립트 생성 모듈

STEP-1(morning_core) 본편과 별도로 매일 발행하는 45~60초 세로형 쇼츠.
STEP-1 본편을 재분석하지 않고, STEP-1과 같은 원본 데이터
(stock-briefing-v3-1의 data/briefing_data.json)에서 "오늘 유튜브·경제방송·
증권사에서 가장 많이 언급된 관심종목 TOP3"를 직접 뽑아 카운트다운 형식으로
빠르게 전달한다 — STEP-1 본편(8분, 종목별 심층 분석)의 예고편/발견(discovery)
채널 역할.

- 데이터 소스: stock-briefing-v3-1의 data/briefing_data.json
  (raw.githubusercontent.com) — STEP-1 본편과 동일 원본
- 랭킹: pipeline/assets/ranking.py(뉴스·방송 언급 + 증권사 언급 2팩터)
- 목표 길이: 45~60초 고정
- 오프닝: 카운트다운 훅(고정 템플릿) → 3위 → 2위 → 1위 → 클로징(CTA)
"""
import os
import sys
import json
import urllib.request
from datetime import datetime
from openai import OpenAI

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from assets.ranking import build_ranking

SCRIPT_MOCK = os.environ.get("SCRIPT_MOCK") == "1"

_api_key = os.environ.get("OPENAI_API_KEY")
if not _api_key and not SCRIPT_MOCK:
    raise EnvironmentError("❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
client = OpenAI(api_key=_api_key or "sk-mock-dry-run")

UPSTREAM_REPO = "kunil-choi/stock-briefing-v3-1"

TODAY = datetime.now().strftime("%Y년 %m월 %d일")

HOOK_NARRATION = "오늘 유튜브와 경제 방송에서 가장 뜨거웠던 관심종목 TOP3, 지금 공개합니다!"
HOOK_SUBTITLE  = HOOK_NARRATION

CLOSING_NARRATION = (
    "더 자세한 분석은 오늘 아침 KBS 머니올라 정규 브리핑에서 확인하세요. "
    "구독과 좋아요는 큰 힘이 됩니다. "
    "본 영상은 AI가 공개 데이터를 분석한 참고용 정보이며, 투자 판단과 책임은 본인에게 있습니다."
)
CLOSING_SUBTITLE = CLOSING_NARRATION
DISCLAIMER = (
    "⚠️ 본 영상은 AI 분석 참고자료이며 투자 권유가 아닙니다. 투자 책임은 본인에게 있습니다."
)


def fetch_briefing_data() -> dict:
    url = f"https://raw.githubusercontent.com/{UPSTREAM_REPO}/main/data/briefing_data.json"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"⚠️ {UPSTREAM_REPO} briefing_data.json 로드 실패: {e}")
        return {}


_RULES = """
## narration/subtitle 규칙
- narration(TTS 낭독용): 숫자는 한글로 풀어 읽는다(6,700→육천칠백, 12.5%→십이쩜오퍼센트,
  소수점은 반드시 "쩜"). SK→에스케이, LG→엘지, AI→에이아이 등 약어도 한글 발음으로.
- subtitle(화면 자막용): 숫자·영문 약어는 원래 표기 그대로(6,700 / 12.5% / SK / AI).
- narration과 subtitle은 문장 수·내용이 1:1로 대응해야 한다(표기만 다름).
"""

_SYSTEM_PROMPT = """
너는 KBS 머니올라 "관심종목 쇼츠" 대본 작성 전문가입니다. 45~60초 세로형
쇼츠 영상에 들어갈, 오늘 가장 많이 언급된 관심종목 3개 각각에 대한 짧고
임팩트 있는 한 줄 코멘트를 작성하세요. 제공된 요약(summary)·투자포인트
(catalysts) 데이터 안에서만 작성하고, 없는 사실을 지어내지 마세요. 특정
종목의 매수·매도를 권유하는 어조는 쓰지 마세요 — "왜 오늘 화제였는지"를
전달하는 역할만 합니다.

{rules}

## 분량 요구사항
- 종목당 narration 40~60자(공백 포함). 카운트다운 쇼츠 특성상 임팩트 있게
  핵심 한 가지만 짧게 전달하세요(나열 금지).

## 출력 JSON 구조
{{
  "stocks": [
    {{"name": "종목명", "narration": "...", "subtitle": "..."}},
    ...
  ]
}}
입력으로 주어진 종목 순서와 동일한 순서로, 동일한 개수만큼 반환하세요.
"""


def _mock_response(candidates: list) -> dict:
    return {
        "stocks": [
            {"name": c["name"], "narration": f"[MOCK] {c['name']} 오늘 언급 급증했습니다.",
             "subtitle": f"[MOCK] {c['name']} 오늘 언급 급증했습니다."}
            for c in candidates
        ]
    }


def _call_stocks(candidates: list) -> dict:
    system_prompt = _SYSTEM_PROMPT.format(rules=_RULES)
    user_content = json.dumps(
        [{"name": c["name"], "sector": c["sector"], "summary": c["summary"], "catalysts": c["catalysts"]}
         for c in candidates],
        ensure_ascii=False, indent=2,
    )
    if SCRIPT_MOCK:
        return _mock_response(candidates)
    last_err = None
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=1200,
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            last_err = e
            print(f"  ⚠️ API 호출 실패(시도 {attempt + 1}/2): {e}")
    # SCRIPT_MOCK이 아닌 실제 운영에서 두 번 다 실패하면 [MOCK] 플레이스홀더
    # 문구가 실제 발행 영상에 그대로 노출될 위험이 있으므로, 조용히 폴백하지
    # 않고 파이프라인을 중단시킨다.
    raise RuntimeError(f"❌ 종목 나레이션 생성 최종 실패: {last_err}")


def generate_shorts_script(briefing_data: dict) -> dict:
    candidates = build_ranking(briefing_data, top_n=3)
    if not candidates:
        print("❌ 랭킹에 포함할 관심종목 후보가 없습니다(언급 데이터 부족). 종료합니다.")
        sys.exit(1)

    print("🏆 관심종목 TOP3 (언급 점수 기준):")
    for c in candidates:
        print(f"  {c['rank']}위 {c['name']} — ranking_score={c['ranking_score']} "
              f"(뉴스/방송 {c['news_score']} / 증권사 {c['report_score']})")

    llm_result = _call_stocks(candidates)
    narration_by_name = {s["name"]: s for s in llm_result.get("stocks", [])}

    sections = [{
        "id": "hook", "label": "훅",
        "narration": HOOK_NARRATION, "subtitle": HOOK_SUBTITLE,
        "keywords": [c["name"] for c in candidates],
    }]

    # 카운트다운 연출: 3위 → 2위 → 1위 순으로 등장(랭킹 내림차순 리스트를 뒤집어서 순회)
    for c in sorted(candidates, key=lambda x: x["rank"], reverse=True):
        llm = narration_by_name.get(c["name"], {})
        narration = llm.get("narration", c.get("summary", "")) or f"{c['name']}, 오늘 화제의 종목입니다."
        subtitle = llm.get("subtitle", narration)
        sections.append({
            "id": f"top_{c['rank']}", "label": f"TOP{c['rank']}",
            "rank": c["rank"], "name": c["name"],
            "price": c.get("price", ""), "change": c.get("change", ""),
            "change_positive": c.get("change_positive", True),
            "narration": narration, "subtitle": subtitle,
        })

    sections.append({
        "id": "closing", "label": "클로징",
        "narration": CLOSING_NARRATION, "subtitle": CLOSING_SUBTITLE,
        "disclaimer": DISCLAIMER,
    })

    result = {"title": f"{TODAY} 관심종목 TOP3", "date": TODAY, "sections": sections}
    total_chars = sum(len(s.get("narration", "") or "") for s in sections)
    print(f"\n📏 쇼츠 나레이션 글자 수 합계: {total_chars:,}자 (목표: 45~60초)")
    return result


def run(lang: str = "KO"):
    global TODAY
    lang = lang.upper()

    briefing_data = fetch_briefing_data()
    if not briefing_data:
        print(f"❌ {UPSTREAM_REPO}의 briefing_data.json을 가져오지 못했습니다. 종료합니다.")
        sys.exit(1)

    briefing_date_str = briefing_data.get("briefing_date", "")
    if briefing_date_str:
        TODAY = briefing_date_str
        print(f"📅 브리핑 날짜: {TODAY} (V3-1 데이터 기준)")

    script = generate_shorts_script(briefing_data)

    root = os.path.join(_HERE, "..")
    out_dir = os.path.join(root, "output", lang, "scripts")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "script.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 스크립트 생성 완료! 섹션 수: {len(script['sections'])}개 → {out_path}")
    return script


if __name__ == "__main__":
    lang = sys.argv[1] if len(sys.argv) > 1 else "KO"
    run(lang)
