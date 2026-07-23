# pipeline/assets/builders.py
"""
KBS 머니올라 쇼츠 — 세로형(9:16) 방송 비주얼 빌더.
매 프레임이 전체화면 사진(연합뉴스/KBS 검색, pipeline/generate_media.py) 위에
큼직한 텍스트 카드 하나만 얹는 "포스터형" 레이아웃 — 가로형 본편의 카드
나열형 레이아웃과 다르다(쇼츠는 스크롤 중 0.5초 안에 시선을 붙잡아야 하므로
텍스트 밀도를 최소화).
"""
import os

from .render import render_html_to_png
from .html_theme import (
    esc, scene_shell, text_plate, kbs_badge, rank_badge, stat_pill, PALETTE,
)


def _find_section(sections, sid):
    return next((s for s in sections if s.get("id") == sid), {})


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

    media = _media_entry(media_map, "hook")
    bg_path = media.get("image_path")
    credit = media.get("credit", "")

    kw_html = "".join(
        f'<span class="pill" style="background:#fff2;color:#fff;border:2px solid #fff8;'
        f'font-size:24px;">{esc(k)}</span>'
        for k in keywords
    )

    headline = text_plate(
        '<div style="font-size:26px;font-weight:700;color:#ffe066;">오늘의 관심종목</div>'
        '<div style="font-size:64px;font-weight:800;line-height:1.25;color:#fff;margin-top:10px;">'
        '관심종목<br>TOP 3</div>'
    )
    content = f"""
{kbs_badge()}
{headline}
<div style="display:flex;gap:12px;flex-wrap:wrap;justify-content:center;">{kw_html}</div>
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
    sections = data.get("sections", [])
    top1 = _find_section(sections, "top_1")
    name = top1.get("name", "")

    media = _media_entry(media_map, "top_1")
    bg_path = media.get("image_path")
    credit = media.get("credit", "")

    stock_html = (
        f'<div class="pill" style="background:#fff2;color:#fff;border:3px solid #fff;'
        f'font-size:36px;font-weight:800;">{esc(name)}</div>'
        if name else ""
    )
    title_html = text_plate(
        f'<div style="font-size:80px;font-weight:800;line-height:1.2;color:#fff;">{esc(title)}</div>'
    )
    content = f"""
{kbs_badge()}
{title_html}
{stock_html}
"""
    html = scene_shell(content, background_image=bg_path, credit=credit)
    return render_html_to_png(html, out_path)
