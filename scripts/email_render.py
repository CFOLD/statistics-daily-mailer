from __future__ import annotations

import json
import subprocess
from functools import lru_cache
from pathlib import Path

try:
    from markdown_it import MarkdownIt
except Exception:
    MarkdownIt = None

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

SCRIPT_DIR = Path(__file__).resolve().parent
MATH_RENDERER = SCRIPT_DIR / "render_math.js"


def md_to_html(md: str) -> str:
    if not md:
        return ""
    md = _render_math(md)
    if MarkdownIt:
        html = MarkdownIt("commonmark", {"html": True, "breaks": True}).enable("table").render(md)
    else:
        parts = [p.strip() for p in md.split("\n\n") if p.strip()]
        html = "".join(f"<p>{p.replace(chr(10), '<br/>')}</p>" for p in parts)
    return _style_html(html)


def _render_math(md: str) -> str:
    if not _can_render_math():
        return md
    payload = json.dumps({"text": md}, ensure_ascii=False)
    try:
        proc = subprocess.run(
            ["node", str(MATH_RENDERER)],
            input=payload,
            text=True,
            capture_output=True,
            check=True,
            cwd=str(SCRIPT_DIR.parent),
        )
    except Exception:
        return md
    try:
        data = json.loads(proc.stdout)
    except Exception:
        return md
    return str(data.get("html") or md)


@lru_cache(maxsize=1)
def _can_render_math() -> bool:
    if not MATH_RENDERER.exists():
        return False
    try:
        proc = subprocess.run(
            ["node", "-e", "require('katex'); process.stdout.write('ok')"],
            text=True,
            capture_output=True,
            cwd=str(SCRIPT_DIR.parent),
            check=True,
        )
        return proc.stdout.strip() == "ok"
    except Exception:
        return False


def _style_html(html: str) -> str:
    if not BeautifulSoup:
        return html

    soup = BeautifulSoup(f"<div>{html}</div>", "html.parser")

    for tag in soup.find_all():
        if not tag.get_text(strip=True) and not tag.find(True):
            tag.decompose()

    for table in soup.find_all("table"):
        table["role"] = "presentation"
        table["style"] = (
            "width:100%; border-collapse:collapse; margin:16px 0; "
            "font-size:14px; line-height:1.6; border:1px solid #d9e2ec;"
        )
        for th in table.find_all("th"):
            _append_style(
                th,
                "border:1px solid #d9e2ec; padding:10px 12px; background:#f8fafc; font-weight:700;",
            )
        for td in table.find_all("td"):
            _append_style(
                td,
                "border:1px solid #d9e2ec; padding:10px 12px; vertical-align:top;",
            )
        for thead in table.find_all("thead"):
            thead["style"] = "display:table-header-group;"
        for tbody in table.find_all("tbody"):
            tbody["style"] = "display:table-row-group;"

    for code in soup.find_all("code"):
        code["style"] = (
            "background:#f3f4f6; padding:2px 5px; border-radius:4px; "
            "font-family:Consolas, Monaco, monospace;"
        )
    for pre in soup.find_all("pre"):
        pre["style"] = "background:#0f172a; color:#e5e7eb; padding:14px; border-radius:8px; overflow:auto;"
    for ul in soup.find_all("ul"):
        ul["style"] = "margin:12px 0; padding-left:22px;"
    for ol in soup.find_all("ol"):
        ol["style"] = "margin:12px 0; padding-left:22px;"
    for blockquote in soup.find_all("blockquote"):
        blockquote["style"] = "margin:16px 0; padding:8px 16px; border-left:4px solid #cbd5e1; color:#475569;"
    for span in soup.find_all("span", class_="katex"):
        _append_style(span, "white-space:nowrap;")
    for span in soup.find_all("span", class_="katex-display"):
        _append_style(span, "display:block; overflow-x:auto; overflow-y:hidden; margin:12px 0;")
        if span.parent and getattr(span.parent, "name", None) == "p":
            _append_style(span.parent, "text-align:center;")
    for span in soup.find_all("span", class_="base"):
        _append_style(span, "display:inline-block;")

    return "".join(str(child) for child in soup.div.contents)


def _append_style(tag, style: str) -> None:
    base = tag.get("style", "")
    tag["style"] = f"{base}; {style}" if base else style
