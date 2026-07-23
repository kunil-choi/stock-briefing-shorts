# pipeline/assets/ranking.py
"""
관심종목 TOP3 선정 — stock-briefing-step1의 "주도주 랭킹형"(Phase F)
compute_ranking_score() 산식을 이식하되, 거래량 점수(volume_score,
pykrx OHLCV 조회 필요)는 뺐다. 이 레포는 v3-1의 briefing_data.json(원본
수집 데이터, LLM 스크립트 생성 전)을 직접 소비하는데, 거래량은 이미 v3-1이
아니라 시세 API 재조회가 필요해 이 가벼운 쇼츠 전용 레포에 pykrx 의존성을
새로 들이는 비용이 크다. "관심종목 쇼츠"의 취지 자체가 "얼마나 많이
언급됐는가"이므로, 뉴스/방송 언급 점수 + 증권사 언급 점수 2팩터만으로도
목적에 부합한다.
"""
from typing import Optional

DEFAULT_WEIGHTS = (0.6, 0.4)  # (news, report)

_AGGREGATE_STOCK_IDS = {"stock_추가관심종목", "stock_오늘의픽", "stock_증권사리포트"}
_NEWS_CHANNEL_TYPES = {"유튜브", "경제방송"}


def is_stock_candidate(section_id: str) -> bool:
    if section_id in _AGGREGATE_STOCK_IDS:
        return False
    return section_id.startswith("stock_") or section_id.startswith("hidden_")


def compute_news_score(section: dict) -> float:
    """channel_summaries 중 유튜브/경제방송 카테고리 등장 개수 + 출처 수를
    0~1로 정규화한다(stock-briefing-step1의 ranking.py와 동일 산식)."""
    summaries = section.get("channel_summaries") or []
    hit = 0
    total_sources = 0
    for cs in summaries:
        if cs.get("channel_type") in _NEWS_CHANNEL_TYPES:
            hit += 1
            total_sources += len(cs.get("sources") or [])
    if hit == 0:
        return 0.0
    score = 0.3 * hit + 0.1 * min(total_sources, 4)
    return max(0.0, min(1.0, score))


def compute_report_score(section: dict) -> float:
    """channel_summaries 중 증권사 카테고리의 출처(증권사) 수를 0~1로 정규화한다."""
    summaries = section.get("channel_summaries") or []
    for cs in summaries:
        if cs.get("channel_type") == "증권사":
            n = len(cs.get("sources") or [])
            return max(0.0, min(1.0, 0.4 + 0.2 * n))
    return 0.0


def compute_ranking_score(news_score: float, report_score: float,
                           weights: tuple = DEFAULT_WEIGHTS) -> float:
    wn, wr = weights
    return round(wn * news_score + wr * report_score, 4)


def build_ranking(briefing_data: dict, top_n: int = 3,
                   weights: tuple = DEFAULT_WEIGHTS) -> list:
    """v3-1 briefing_data.json(원본 sections 구조, script.json과 동일 스키마)에서
    종목 후보를 뽑아 ranking_score 상위 top_n개를 반환한다."""
    from .config import normalize_stock_name, STOCK_CODES, get_stock_sector

    sections = briefing_data.get("sections") or []
    candidates = []
    for sec in sections:
        sid = sec.get("id", "")
        if not is_stock_candidate(sid):
            continue
        name = sid.replace("stock_", "").replace("hidden_", "")
        normalized = normalize_stock_name(name)

        news_score = compute_news_score(sec)
        report_score = compute_report_score(sec)
        ranking_score = compute_ranking_score(news_score, report_score, weights)

        candidates.append({
            "rank": 0,  # 정렬 후 채움
            "id": sid,
            "name": normalized,
            "code": STOCK_CODES.get(normalized, ""),
            "sector": get_stock_sector(normalized),
            "price": sec.get("price", ""),
            "change": sec.get("change", ""),
            "change_positive": sec.get("change_positive", True),
            "news_score": round(news_score, 3),
            "report_score": round(report_score, 3),
            "ranking_score": ranking_score,
            "summary": sec.get("summary", ""),
            "catalysts": sec.get("catalysts", []),
        })

    candidates.sort(key=lambda c: c["ranking_score"], reverse=True)
    top = candidates[:top_n]
    # rank는 랭킹 순위 그대로(1위가 rank=1) 부여한다. 영상에서의 등장 순서
    # (카운트다운 3위→2위→1위)는 generate_script.py가 이 리스트를 reversed로
    # 순회해서 정한다.
    for i, c in enumerate(top, 1):
        c["rank"] = i

    return top
