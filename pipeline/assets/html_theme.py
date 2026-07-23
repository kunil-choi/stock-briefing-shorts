# pipeline/assets/html_theme.py
"""
KBS 머니올라 쇼츠 — 세로형(1080x1920, 9:16) HTML/CSS 디자인 시스템.
stock-briefing-step1/step2의 html_theme.py(가로 1920x1080, PPT 슬라이드 톤)와
같은 팔레트·브랜드 요소를 쓰되, 쇼츠는 매 프레임이 전체화면 사진 배경 위에
큼직한 텍스트 카드 하나만 얹는 "포스터형" 레이아웃이라 카드/표/차트 컴포넌트는
가져오지 않고 필요한 것만 새로 짰다.
"""
import os
import re
import base64
import mimetypes
import html as _he
from datetime import date

from .config import W, H, SUBTITLE_ZONE_TOP

SUBTITLE_BAR_H = H - SUBTITLE_ZONE_TOP

PALETTE = {
    "bg":           "#faf9f6",
    "ink":          "#16181d",
    "muted":        "#6b7280",
    "accent":       "#0e9f8e",
    "accent_soft":  "#e3f7f3",
    "highlight":    "#ffe066",
    "up":           "#e0393e",
    "down":         "#2f6fed",
    "card":         "#ffffff",
    "border":       "#e8e6df",
}

_RANK_COLOR = {3: "#a05bd6", 2: "#2f6fed", 1: "#e0393e"}  # 3위→1위로 갈수록 강렬하게(카운트다운)


def esc(s) -> str:
    return _he.escape(str(s or ""))


def file_uri(path: str) -> str:
    """로컬 이미지를 base64 data URI로 인라인한다(문서 오리진이 about:blank라
    file:// 스킴이 Chromium 보안 정책에 막히는 문제 회피 — step1/step2와 동일)."""
    try:
        with open(path, "rb") as f:
            data = f.read()
        mime, _ = mimetypes.guess_type(path)
        mime = mime or "image/png"
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return "file://" + os.path.abspath(path)


def background_layer(image_path, darkness: float = 0.72, credit: str = "") -> str:
    """전체화면 배경 사진 + 하단으로 갈수록 어두워지는 그라디언트. 이미지가
    없으면 빈 문자열(호출부가 은은한 그라디언트 배경으로 자연 폴백)."""
    if not image_path or not os.path.isfile(image_path):
        return ""
    uri = file_uri(image_path)
    credit_html = (
        f'<div style="position:absolute;right:20px;bottom:{SUBTITLE_BAR_H + 14}px;z-index:-1;'
        f'font-size:15px;color:rgba(255,255,255,.75);font-weight:600;'
        f'text-shadow:0 1px 3px rgba(0,0,0,.8);">{esc(credit)}</div>'
        if credit else ""
    )
    return f"""
<div style="position:absolute;inset:0;z-index:-3;background-image:url('{uri}');
  background-size:cover;background-position:center;"></div>
<div style="position:absolute;inset:0;z-index:-2;
  background:linear-gradient(180deg, rgba(5,7,13,.25) 0%, rgba(5,7,13,.45) 55%,
  rgba(5,7,13,{darkness}) 100%);"></div>
{credit_html}"""


def text_plate(inner_html: str, extra_style: str = "") -> str:
    """사진 위에서도 항상 읽히는 반투명 다크 판."""
    return (
        f'<div style="display:inline-block;background:rgba(5,7,13,.55);'
        f'border-radius:22px;padding:26px 32px;{extra_style}">{inner_html}</div>'
    )


def kbs_badge() -> str:
    return (f'<div class="pill" style="background:{PALETTE["accent"]};color:#fff;'
            f'font-size:24px;padding:10px 26px;">KBS 머니올라</div>')


BASE_CSS = f"""
*{{box-sizing:border-box;margin:0;padding:0;}}
html,body{{width:{W}px;height:{H}px;overflow:hidden;}}
body{{
  font-family:'Noto Sans KR','NanumGothic','Malgun Gothic',sans-serif;
  color:{PALETTE['ink']};
  background:{PALETTE['bg']};
  position:relative;
}}
.stage{{position:absolute; left:0; top:0; width:{W}px; height:{H}px;}}
.center-wrap{{
  position:absolute; left:0; top:0; width:{W}px; height:{H - SUBTITLE_BAR_H}px;
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  text-align:center; gap:26px; padding:0 64px;
}}
.subtitle-zone{{
  position:absolute; left:0; bottom:0; width:{W}px; height:{SUBTITLE_BAR_H}px;
}}
.pill{{
  display:inline-flex; align-items:center; gap:8px;
  border-radius:999px; padding:8px 20px; font-weight:700; font-size:22px;
}}
"""


def scene_shell(content_html: str, background_image=None, credit: str = "") -> str:
    """모든 쇼츠 프레임의 공통 뼈대. 전체화면 사진 배경(있으면) + 중앙 정렬
    콘텐츠. step1/step2의 centered_shell()과 동일한 패턴이나 세로 캔버스용."""
    bg_html = background_layer(background_image, credit=credit)
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{BASE_CSS}</style></head>
<body><div class="stage">
  {bg_html}
  <div class="center-wrap">{content_html}</div>
  <div class="subtitle-zone"></div>
</div></body></html>"""


def rank_badge(rank: int) -> str:
    """카운트다운용 대형 순위 배지(3→2→1). 숫자가 클수록 화면을 압도하도록
    크게 그려 "곧 1위가 나온다"는 긴장감을 준다."""
    color = _RANK_COLOR.get(rank, PALETTE["accent"])
    return (
        f'<div style="width:180px;height:180px;border-radius:50%;'
        f'background:{color};display:flex;align-items:center;justify-content:center;'
        f'box-shadow:0 12px 32px rgba(0,0,0,.35);">'
        f'<span style="font-size:96px;font-weight:800;color:#fff;">{rank}</span></div>'
    )


def stat_pill(label: str, value: str, positive: bool = True) -> str:
    if not value:
        return ""
    color = PALETTE["up"] if positive else PALETTE["down"]
    arrow = "▲" if positive else "▼"
    return (
        f'<span class="pill" style="background:{color}1a;color:{color};'
        f'font-size:26px;font-weight:800;">{arrow} {esc(label)} {esc(value)}</span>'
    )
