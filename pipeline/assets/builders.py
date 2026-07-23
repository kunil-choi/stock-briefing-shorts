# pipeline/assets/builders.py
"""
KBS 머니올라 쇼츠 — 세로형(9:16) 방송 비주얼 빌더.
매 프레임이 전체화면 사진(연합뉴스/KBS 검색, pipeline/generate_media.py) 위에
큼직한 텍스트 카드 하나만 얹는 "포스터형" 레이아웃 — 가로형 본편의 카드
나열형 레이아웃과 다르다(쇼츠는 스크롤 중 0.5초 안에 시선을 붙잡아야 하므로
텍스트 밀도를 최소화).
"""
import os
import re

from .render import render_html_to_png
from .html_theme import (
    esc, scene_shell, text_plate, kbs_badge, rank_badge, stat_pill, PALETTE,
)


def _find_section(sections, sid):
    return next((s for s in sections if s.get("id") == sid), {})


def _kdate_to_dashed(date_str: str) -> str:
    """'2026년 07월 23일' → '2026-07-23'. 매칭 실패 시 원본 그대로 반환."""
    m = re.match(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", date_str or "")
    if not m:
        return date_str or ""
    y, mo, d = m.groups()
    return f"{y}-{int(mo):02d}-{int(d):02d}"


def _headline_block(date_str: str) -> str:
    """훅/썸네일 공통 헤드라인 카드 — [개장전 브리핑] {날짜} / 주식시장 오늘의
    관심종목은? / KBS 머니올라 3줄 고정 구성. 어떤 종목이 TOP인지는 이 화면에서
    미리 공개하지 않고 카운트다운(TOP3→TOP1)에서 드러내 궁금증을 유지한다."""
    date_dashed = _kdate_to_dashed(date_str)
    return text_plate(
        f'<div style="font-size:28px;font-weight:700;color:{PALETTE["highlight"]};">'
        f'[개장전 브리핑] {esc(date_dashed)}</div>'
        f'<div style="font-size:48px;font-weight:800;color:#fff;line-height:1.4;margin-top:14px;">'
        f'주식시장 오늘의 관심종목은?</div>'
        f'<div style="font-size:30px;font-weight:700;color:#fff;margin-top:20px;">KBS 머니올라</div>',
        extra_style="text-align:center;",
    )


def _media_entry(media_map: dict, key: str) -> dict:
    if not media_map:
        return {}
    entry = media_map.get(key) or {}
    image_path = entry.get("image_path")
    if not image_path or not os.path.isfile(image_path):
        return {}
    return entry


# ── 훅(오프닝) ───────────────────────────────────────────────────────────

def build_hook(data, out_dir, media_map=None):
    sec = _find_section(data.get("sections", []), "hook")
    keywords = sec.get("keywords", [])[:3]
    date_str = data.get("date", "")

    media = _media_entry(media_map, "hook")
    bg_path = media.get("image_path")
    credit = media.get("credit", "")

    kw_html = "".join(
        f'<span class="pill" style="background:#fff2;color:#fff;border:2px solid #fff8;'
        f'font-size:24px;">{esc(k)}</span>'
        for k in keywords
    )

    content = f"""
{_headline_block(date_str)}
<div style="display:flex;gap:12px;flex-wrap:wrap;justify-content:center;margin-top:8px;">{kw_html}</div>
"""
    html = scene_shell(content, background_image=bg_path, credit=credit)
    return render_html_to_png(html, os.path.join(out_dir, "00_hook.png"))


# ── 카운트다운 카드(TOP3 → TOP1) ────────────────────────────────────────

def build_rank_card(section, out_dir, media_map=None):
    rank = section.get("rank", 0)
    name = section.get("name", "")
    price = section.get("price", "")
    change = section.get("change", "")
    positive = section.get("change_positive", True)

    media = _media_entry(media_map, f"top_{rank}")
    bg_path = media.get("image_path")
    credit = media.get("credit", "")

    price_html = (
        f'<div style="font-size:34px;font-weight:800;color:#fff;margin-top:6px;">₩ {esc(price)}</div>'
        if price else ""
    )
    change_wrap = f'<div style="margin-top:12px;">{stat_pill("", change, positive)}</div>' if change else ""

    body = text_plate(
        f'<div style="font-size:22px;font-weight:700;color:#ffe066;">TOP {rank}</div>'
        f'<div style="font-size:56px;font-weight:800;color:#fff;margin-top:8px;">{esc(name)}</div>'
        f'{price_html}'
        f'{change_wrap}',
        extra_style="text-align:center;",
    )

    content = f"""
{kbs_badge()}
{rank_badge(rank)}
{body}
"""
    html = scene_shell(content, background_image=bg_path, credit=credit)
    return render_html_to_png(html, os.path.join(out_dir, f"0{4 - rank}_top{rank}.png"))


# ── 클로징 ─────────────────────────────────────────────────────────────

def build_closing(data, out_dir):
    content = f"""
{kbs_badge()}
<div style="font-size:60px;font-weight:800;">더 자세한 분석은</div>
<div style="font-size:44px;font-weight:800;color:{PALETTE['highlight']};">정규 브리핑에서!</div>
<div class="pill" style="background:{PALETTE['accent']};color:#fff;font-size:30px;padding:14px 34px;">
  구독 &amp; 좋아요
</div>
<div style="font-size:18px;color:{PALETTE['muted']};line-height:1.6;max-width:820px;margin-top:20px;">
  본 영상은 AI가 공개 데이터를 분석한 참고용 정보입니다. 투자 판단과 책임은 본인에게 있습니다.
</div>
"""
    html = scene_shell(content)
    return render_html_to_png(html, os.path.join(out_dir, "99_closing.png"))


# ── 썸네일 ─────────────────────────────────────────────────────────────

def build_thumbnail(data: dict, title: str, out_path: str, media_map=None) -> str:
    """썸네일도 첫 화면(build_hook)과 같은 3줄 헤드라인 카드를 쓴다 — YouTube
    메타 제목(title 인자, "#Shorts" 해시태그 등이 섞여 있어 화면용으로는
    지저분함)을 그대로 화면에 옮기지 않고, 방송 타이틀 카드용 문구를
    따로 렌더링한다. title 인자는 시그니처 호환을 위해 유지하되 화면에는
    쓰지 않는다."""
    sections = data.get("sections", [])
    top1 = _find_section(sections, "top_1")
    name = top1.get("name", "")
    date_str = data.get("date", "")

    media = _media_entry(media_map, "top_1")
    bg_path = media.get("image_path")
    credit = media.get("credit", "")

    stock_html = (
        f'<div class="pill" style="background:#fff2;color:#fff;border:3px solid #fff;'
        f'font-size:28px;font-weight:800;margin-top:8px;">{esc(name)}</div>'
        if name else ""
    )
    content = f"""
{_headline_block(date_str)}
{stock_html}
"""
    html = scene_shell(content, background_image=bg_path, credit=credit)
    return render_html_to_png(html, out_path)
