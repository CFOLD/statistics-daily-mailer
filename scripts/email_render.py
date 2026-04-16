from __future__ import annotations

import base64
import json
import subprocess
import sys
from dataclasses import dataclass, field
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
REPO_DIR = SCRIPT_DIR.parent
MATH_IMAGE_RENDERER = SCRIPT_DIR / "render_math_images.js"


@dataclass(frozen=True)
class InlineImage:
    cid: str
    filename: str
    mime_type: str
    content: bytes

    def as_data_uri(self) -> str:
        encoded = base64.b64encode(self.content).decode("ascii")
        return f"data:{self.mime_type};base64,{encoded}"


@dataclass
class RenderedFragment:
    html: str
    inline_images: list[InlineImage] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def preview_html(self) -> str:
        html = self.html
        for image in self.inline_images:
            html = html.replace(f"cid:{image.cid}", image.as_data_uri())
        return html


@dataclass
class _MathRenderResult:
    markdown: str
    inline_images: list[InlineImage] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def render_markdown(md: str) -> RenderedFragment:
    if not md:
        return RenderedFragment(html="")

    math_result = _render_math_images(md)
    rendered_md = math_result.markdown
    if MarkdownIt:
        html = MarkdownIt("commonmark", {"html": True, "breaks": True}).enable("table").render(rendered_md)
    else:
        parts = [p.strip() for p in rendered_md.split("\n\n") if p.strip()]
        html = "".join(f"<p>{p.replace(chr(10), '<br/>')}</p>" for p in parts)

    return RenderedFragment(
        html=_style_html(html),
        inline_images=math_result.inline_images,
        warnings=math_result.warnings,
    )


def _render_math_images(md: str) -> _MathRenderResult:
    if not _can_render_math_images():
        return _MathRenderResult(markdown=md, warnings=["Math image renderer unavailable; leaving LaTeX unchanged."])

    payload = json.dumps({"text": md}, ensure_ascii=False)
    try:
        proc = subprocess.run(
            ["node", str(MATH_IMAGE_RENDERER)],
            input=payload,
            text=True,
            capture_output=True,
            check=True,
            cwd=str(REPO_DIR),
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        msg = "Math image renderer failed; leaving LaTeX unchanged."
        if stderr:
            msg = f"{msg} Renderer stderr: {stderr}"
        return _MathRenderResult(markdown=md, warnings=[msg])
    except Exception as exc:
        return _MathRenderResult(markdown=md, warnings=[f"Math image renderer failed to start; leaving LaTeX unchanged. {exc}"])

    try:
        data = json.loads(proc.stdout)
    except Exception as exc:
        return _MathRenderResult(markdown=md, warnings=[f"Math image renderer returned invalid JSON; leaving LaTeX unchanged. {exc}"])

    markdown = str(data.get("markdown") or md)
    warnings = [str(item) for item in (data.get("warnings") or []) if str(item).strip()]
    inline_images: list[InlineImage] = []
    for item in data.get("images") or []:
        try:
            inline_images.append(
                InlineImage(
                    cid=str(item["cid"]),
                    filename=str(item["filename"]),
                    mime_type=str(item.get("mime_type") or "image/png"),
                    content=base64.b64decode(item["data_base64"]),
                )
            )
        except Exception as exc:
            warnings.append(f"Skipping invalid rendered math image payload. {exc}")

    return _MathRenderResult(markdown=markdown, inline_images=inline_images, warnings=warnings)


@lru_cache(maxsize=1)
def _can_render_math_images() -> bool:
    if not MATH_IMAGE_RENDERER.exists():
        return False
    try:
        proc = subprocess.run(
            ["node", "-e", "require('texsvg'); require('sharp'); process.stdout.write('ok')"],
            text=True,
            capture_output=True,
            cwd=str(REPO_DIR),
            check=True,
        )
        return proc.stdout.strip() == "ok"
    except Exception:
        return False


def _style_html(html: str) -> str:
    if not BeautifulSoup:
        return html

    soup = BeautifulSoup(f"<div>{html}</div>", "html.parser")

    for table in soup.find_all("table"):
        table["role"] = "presentation"
        table["style"] = (
            "width:100%; border-collapse:collapse; margin:16px 0; "
            "font-size:14px; line-height:1.6; border:1px solid #d9e2ec;"
        )
        for th in table.find_all("th"):
            if not th.get_text(strip=True) and not th.find(True):
                th.string = "\xa0"
            _append_style(
                th,
                "border:1px solid #d9e2ec; padding:10px 12px; background:#f8fafc; font-weight:700;",
            )
        for td in table.find_all("td"):
            if not td.get_text(strip=True) and not td.find(True):
                td.string = "\xa0"
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
    for img in soup.find_all("img"):
        _append_style(img, "border:0; outline:none; text-decoration:none;")

    return "".join(str(child) for child in soup.div.contents)


def _append_style(tag, style: str) -> None:
    base = tag.get("style", "")
    tag["style"] = f"{base}; {style}" if base else style


if __name__ == "__main__":
    sample = "Value: $x^2$\n\n$$\\frac{1}{2}$$"
    result = render_markdown(sample)
    sys.stdout.write(result.preview_html())
