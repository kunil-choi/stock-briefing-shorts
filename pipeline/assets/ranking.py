# pipeline/assets/ranking.py
"""
관심종목 TOP3 선정.

★ 스키마 수정 이력: 최초 구현 시 v3-1의 briefing_data.json이 STEP-1의 후처리된
script.json과 같은 "sections"(id="stock_*") 구조일 것으로 가정하고 뉴스/증권사
언급 점수를 자체 계산했는데, 실제 라이브 v3-1 데이터로 검증해보니 완전히 다른
스키마였다(원본 수집 데이터는 LLM 가공 전이라 "sections"가 아예 없음):

  {
    "market_leaders": [{"rank", "name", "code", "weighted_score", "total_count",
                         "price", "change_pct", "summary", "catalyst", "risk",
                         "channel_mentions": [...], "channel_counts": {...}}, ...],
    "stocks": [... 위와 동일한 필드 ...],
    ...
  }

market_leaders(대형 주도주, 현재 통상 1~2개)와 stocks(관심종목, 통상 5~10개)가
분리돼 있고, 각 항목에 이미 v3-1이 계산해둔 weighted_score(뉴스/경제방송/유튜브
언급을 가중합산한 점수)가 있다. 이 레포가 "얼마나 많이 언급됐는가"를 자체
재계산할 필요가 없다 — v3-1의 weighted_score를 그대로 신뢰해 두 배열을 합쳐
정렬하면 된다(자체 산식을 재구현하면 v3-1이 이미 반영한 채널별 가중치·중복
보정 로직과 어긋날 위험만 생긴다).
"""
from typing import Optional


def _fmt_price(price) -> str:
    if price is None or price == "":
        return ""
    try:
        return f"{int(price):,}"
    except (TypeError, ValueError):
        return str(price)


def _fmt_change(change_pct) -> tuple:
    """(표시용 문자열, 상승여부) 반환. change_pct는 숫자(예: 1.91, -0.17)."""
    if change_pct is None or change_pct == "":
        return "", True
    try:
        val = float(change_pct)
    except (TypeError, ValueError):
        return "", True
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.2f}%", val >= 0


def build_ranking(briefing_data: dict, top_n: int = 3) -> list:
    """v3-1 briefing_data.json의 market_leaders + stocks를 합쳐
    weighted_score 내림차순 상위 top_n개를 반환한다."""
    pool = list(briefing_data.get("market_leaders") or []) + list(briefing_data.get("stocks") or [])

    candidates = []
    for item in pool:
        name = (item.get("name") or "").strip()
        if not name:
            continue
        change_str, positive = _fmt_change(item.get("change_pct"))
        candidates.append({
            "name": name,
            "code": item.get("code", ""),
            "price": _fmt_price(item.get("price")),
            "change": change_str,
            "change_positive": positive,
            "weighted_score": item.get("weighted_score", 0) or 0,
            "total_count": item.get("total_count", 0) or 0,
            "summary": item.get("summary", ""),
            "catalyst": item.get("catalyst", ""),
            "risk": item.get("risk", ""),
            "channel_counts": item.get("channel_counts", {}),
        })

    # 같은 종목이 market_leaders/stocks 양쪽에 중복 등장하는 경우는 없다는 게
    # v3-1의 설계 전제지만(대형 주도주 vs 그 외 관심종목으로 이미 배타적으로
    # 분리), 방어적으로 이름 기준 중복을 제거하고 더 높은 점수를 유지한다.
    dedup = {}
    for c in candidates:
        prev = dedup.get(c["name"])
        if prev is None or c["weighted_score"] > prev["weighted_score"]:
            dedup[c["name"]] = c

    ranked = sorted(dedup.values(), key=lambda c: c["weighted_score"], reverse=True)
    top = ranked[:top_n]
    for i, c in enumerate(top, 1):
        c["rank"] = i
    return top
