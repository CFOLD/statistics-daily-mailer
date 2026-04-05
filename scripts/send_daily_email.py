#!/usr/bin/env python3
"""
Daily Statistics Question Email Sender

Renders a markdown question into email-friendly HTML and sends it via SMTP.

Rendering approach:
- `markdown-it-py` handles markdown structure such as tables, lists, and fences.
- math is extracted before markdown parsing so code blocks are not affected.
- `BeautifulSoup` applies email-safe inline styles after HTML generation.
"""

import os
import random
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString
from markdown_it import MarkdownIt


BASE_DIR = Path(__file__).resolve().parents[1]
QUESTIONS_DIR = BASE_DIR / "generated_questions"

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_RECIPIENTS = [email.strip() for email in os.getenv("EMAIL_RECIPIENTS", "").split(",") if email.strip()]

MARKDOWN_RENDERER = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False}).enable("table")
CODE_PATTERN = re.compile(r"(```[\s\S]*?```|`[^`\n]+`)")
DISPLAY_MATH_PATTERN = re.compile(r"\$\$(.+?)\$\$", flags=re.DOTALL)
INLINE_MATH_PATTERN = re.compile(r"(?<!\$)\$([^$\n]+?)\$(?!\$)")
PLACEHOLDER_PATTERN = re.compile(r"EMAILMATHPLACEHOLDER(\d+)TOKEN")


def get_random_question() -> dict:
    """Get a random question from the generated_questions directory."""
    md_files = list(QUESTIONS_DIR.glob("*.md"))
    if not md_files:
        raise FileNotFoundError(f"No question files found in {QUESTIONS_DIR}")

    selected_file = random.choice(md_files)
    return {"file": selected_file.name, "content": selected_file.read_text(encoding="utf-8")}


def parse_markdown_question(content: str) -> dict:
    """Parse markdown question into sections, tolerating heading variants."""
    sections = {"question": "", "explanation": "", "purpose": "", "date": ""}
    buffers = {"question": [], "explanation": [], "purpose": []}
    current_section = None

    heading_map = {
        "문항": "question",
        "문제": "question",
        "problem": "question",
        "questions": "question",
        "해설": "explanation",
        "정답 및 해설": "explanation",
        "solution": "explanation",
        "answer": "explanation",
        "answers": "explanation",
        "출제 의도": "purpose",
        "출제의도": "purpose",
        "purpose": "purpose",
    }

    for line in content.splitlines():
        stripped = line.strip()

        heading_match = re.match(r"^(#{2,6})\s+(.+?)\s*$", stripped)
        if heading_match:
            normalized = re.sub(r"\s+", " ", heading_match.group(2)).strip()
            mapped_section = heading_map.get(normalized)
            if mapped_section:
                current_section = mapped_section
                continue

        if re.match(r"^\s*---\s*$", stripped):
            continue

        generated_match = re.match(r"^\*?Generated on:\s*(.+?)\*?\s*$", stripped)
        if generated_match:
            sections["date"] = generated_match.group(1)
            continue

        if current_section:
            buffers[current_section].append(line)

    for key, lines in buffers.items():
        sections[key] = "\n".join(lines).strip()

    if not sections["question"] and not sections["explanation"]:
        solution_split = re.split(r"(?im)^#{2,6}\s+(?:solution|해설|정답 및 해설)\s*$", content, maxsplit=1)
        if len(solution_split) == 2:
            sections["question"] = re.sub(r"(?im)^#{2,6}\s+.*$", "", solution_split[0]).strip()
            sections["explanation"] = solution_split[1].strip()
        else:
            sections["question"] = content.strip()

    return sections


def parse_table_row(line: str, expected_cols: int) -> list[str]:
    """Parse a markdown table row while tolerating literal pipes inside cells."""
    row = line.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]

    parts = [part.strip() for part in row.split("|")]
    if len(parts) <= expected_cols:
        return parts

    while len(parts) > expected_cols:
        if len(parts) >= 2:
            parts[-2] = f"{parts[-2]}|{parts[-1]}"
            parts.pop()
        else:
            break

    return parts[:expected_cols]


def sanitize_markdown_tables(md_content: str) -> str:
    """Escape literal pipes inside markdown table cells so the parser keeps column structure."""
    lines = md_content.splitlines()
    sanitized: list[str] = []
    i = 0
    in_fence = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            in_fence = not in_fence
            sanitized.append(line)
            i += 1
            continue

        is_table_start = (
            not in_fence
            and stripped.startswith("|")
            and i + 1 < len(lines)
            and re.match(r"^\s*\|?[:\-| ]+\|?\s*$", lines[i + 1])
        )

        if not is_table_start:
            sanitized.append(line)
            i += 1
            continue

        separator = lines[i + 1].strip()
        if separator.startswith("|"):
            separator = separator[1:]
        if separator.endswith("|"):
            separator = separator[:-1]
        expected_cols = len(separator.split("|"))

        block: list[str] = []
        while i < len(lines) and lines[i].strip().startswith("|"):
            cells = parse_table_row(lines[i], expected_cols)
            escaped_cells = [cell.replace("|", r"\|") for cell in cells]
            block.append(f"| {' | '.join(escaped_cells)} |")
            i += 1

        sanitized.extend(block)

    return "\n".join(sanitized)


def extract_math_placeholders(md_content: str) -> tuple[str, list[dict]]:
    """Replace math outside code spans/fences with stable placeholders."""
    math_items: list[dict] = []
    parts: list[str] = []

    def add_math(kind: str, latex: str) -> str:
        placeholder = f"EMAILMATHPLACEHOLDER{len(math_items)}TOKEN"
        math_items.append({"kind": kind, "latex": latex.strip(), "placeholder": placeholder})
        return placeholder

    def protect_math(segment: str) -> str:
        segment = DISPLAY_MATH_PATTERN.sub(lambda match: add_math("display", match.group(1)), segment)
        segment = INLINE_MATH_PATTERN.sub(lambda match: add_math("inline", match.group(1)), segment)
        return segment

    last_end = 0
    for match in CODE_PATTERN.finditer(md_content):
        parts.append(protect_math(md_content[last_end:match.start()]))
        parts.append(match.group(0))
        last_end = match.end()

    parts.append(protect_math(md_content[last_end:]))
    return "".join(parts), math_items


def latex_to_html(latex: str) -> str:
    """Convert common LaTeX math into lightweight HTML suitable for email."""
    result = escape(latex.strip())

    text_commands = {
        r"\\text\{([^}]*)\}": r"\1",
        r"\\mathrm\{([^}]*)\}": r"\1",
        r"\\mathbf\{([^}]*)\}": r"\1",
        r"\\operatorname\{([^}]*)\}": r"\1",
    }
    for pattern, replacement in text_commands.items():
        result = re.sub(pattern, replacement, result)

    replacements = {
        r"\alpha": "&alpha;",
        r"\beta": "&beta;",
        r"\gamma": "&gamma;",
        r"\delta": "&delta;",
        r"\epsilon": "&epsilon;",
        r"\eta": "&eta;",
        r"\theta": "&theta;",
        r"\lambda": "&lambda;",
        r"\mu": "&mu;",
        r"\pi": "&pi;",
        r"\rho": "&rho;",
        r"\sigma": "&sigma;",
        r"\phi": "&phi;",
        r"\chi": "&chi;",
        r"\omega": "&omega;",
        r"\Delta": "&Delta;",
        r"\Gamma": "&Gamma;",
        r"\Lambda": "&Lambda;",
        r"\Sigma": "&Sigma;",
        r"\Pi": "&Pi;",
        r"\Phi": "&Phi;",
        r"\Omega": "&Omega;",
        r"\times": "&times;",
        r"\cdot": "&middot;",
        r"\pm": "&plusmn;",
        r"\approx": "&approx;",
        r"\leq": "&le;",
        r"\le": "&le;",
        r"\geq": "&ge;",
        r"\ge": "&ge;",
        r"\neq": "&ne;",
        r"\ne": "&ne;",
        r"\infty": "&infin;",
        r"\sum": "&sum;",
        r"\prod": "&prod;",
        r"\int": "&int;",
        r"\partial": "&part;",
        r"\prime": "&prime;",
        r"\rightarrow": "&rarr;",
        r"\to": "&rarr;",
        r"\leftarrow": "&larr;",
        r"\Rightarrow": "&rArr;",
        r"\Leftrightarrow": "&hArr;",
        r"\equiv": "&equiv;",
        r"\in": "&isin;",
        r"\subset": "&sub;",
        r"\supset": "&sup;",
        r"\cup": "&cup;",
        r"\cap": "&cap;",
        r"\emptyset": "&empty;",
        r"\left": "",
        r"\right": "",
    }
    for key, value in sorted(replacements.items(), key=lambda item: -len(item[0])):
        result = result.replace(key, value)

    def replace_sqrt(match: re.Match[str]) -> str:
        inner = match.group(1)
        return f'&radic;<span style="text-decoration: overline;">{inner}</span>'

    def replace_frac(match: re.Match[str]) -> str:
        numerator = match.group(1)
        denominator = match.group(2)
        return (
            '<span style="display: inline-block; vertical-align: middle; text-align: center;">'
            f'<span style="display: block; padding: 0 3px; border-bottom: 1px solid #475569;">{numerator}</span>'
            f'<span style="display: block; padding: 0 3px;">{denominator}</span>'
            "</span>"
        )

    previous = None
    while previous != result:
        previous = result
        result = re.sub(r"\\sqrt\{([^{}]+)\}", replace_sqrt, result)
        result = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", replace_frac, result)

    result = re.sub(r"\^\{([^{}]+)\}", r"<sup>\1</sup>", result)
    result = re.sub(r"_\{([^{}]+)\}", r"<sub>\1</sub>", result)
    result = re.sub(r"\^([A-Za-z0-9&;.+-]+)", r"<sup>\1</sup>", result)
    result = re.sub(r"_([A-Za-z0-9&;.+-]+)", r"<sub>\1</sub>", result)
    result = result.replace("{", "").replace("}", "")
    return result


def render_inline_math(latex: str) -> str:
    """Render inline math with a clean fallback representation."""
    display_html = latex_to_html(latex)
    return (
        f'<span title="{escape(latex)}" '
        'style="font-family: Georgia, &quot;Times New Roman&quot;, serif; '
        'font-size: 15px; color: #0f172a; background: #f8fafc; '
        'padding: 1px 5px; border-radius: 4px; white-space: nowrap;">'
        f"{display_html}</span>"
    )


def render_display_math(latex: str) -> str:
    """Render display math as a standalone email-safe block."""
    display_html = latex_to_html(latex)
    escaped_latex = escape(latex)
    return (
        '<div style="text-align: center; margin: 18px 0; padding: 14px 12px; '
        'background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;">'
        '<div style="font-family: Georgia, &quot;Times New Roman&quot;, serif; '
        f'font-size: 18px; color: #1e293b;">{display_html}</div>'
        '<div style="margin-top: 8px; font-size: 11px; line-height: 1.5; '
        f'color: #64748b; font-family: &quot;Courier New&quot;, monospace;">{escaped_latex}</div>'
        "</div>"
    )


def append_style(tag, extra_style: str) -> None:
    """Append inline style to an HTML tag."""
    existing = tag.get("style", "").strip()
    if existing and not existing.endswith(";"):
        existing += ";"
    tag["style"] = f"{existing} {extra_style}".strip()


def replace_math_placeholders(container, math_items: list[dict]) -> None:
    """Replace math placeholders in rendered HTML, preserving block math layout."""
    placeholder_to_item = {item["placeholder"]: item for item in math_items}

    for paragraph in list(container.find_all(["p", "li"])):
        if paragraph.name == "li":
            continue

        text = paragraph.get_text(strip=True)
        item = placeholder_to_item.get(text)
        if item and item["kind"] == "display":
            fragment = BeautifulSoup(render_display_math(item["latex"]), "html.parser")
            replacement = fragment.contents[0]
            paragraph.replace_with(replacement)

    for node in list(container.find_all(string=PLACEHOLDER_PATTERN)):
        if node.parent and node.parent.name in {"code", "pre"}:
            continue

        pieces = []
        last_index = 0
        text = str(node)

        for match in PLACEHOLDER_PATTERN.finditer(text):
            if match.start() > last_index:
                pieces.append(NavigableString(text[last_index:match.start()]))

            item = math_items[int(match.group(1))]
            html_fragment = render_display_math(item["latex"]) if item["kind"] == "display" else render_inline_math(item["latex"])
            fragment = BeautifulSoup(html_fragment, "html.parser")
            pieces.extend(fragment.contents)
            last_index = match.end()

        if last_index < len(text):
            pieces.append(NavigableString(text[last_index:]))

        for piece in pieces:
            node.insert_before(piece)
        node.extract()


def style_rendered_html(html: str, math_items: list[dict]) -> str:
    """Apply email-friendly inline styles to rendered HTML."""
    soup = BeautifulSoup(f"<div>{html}</div>", "html.parser")
    container = soup.div

    replace_math_placeholders(container, math_items)

    for heading in container.find_all(re.compile(r"^h[1-6]$")):
        level = int(heading.name[1])
        sizes = {1: "24px", 2: "22px", 3: "20px", 4: "18px", 5: "16px", 6: "14px"}
        append_style(heading, f"font-size: {sizes[level]}; font-weight: 600; color: #1e293b; margin: 18px 0 12px; line-height: 1.4;")

    for paragraph in container.find_all("p"):
        append_style(paragraph, "margin: 0 0 14px; line-height: 1.8; color: #334155;")
        if not paragraph.get_text(strip=True) and not paragraph.find(True):
            paragraph.decompose()

    for list_tag in container.find_all(["ul", "ol"]):
        append_style(list_tag, "margin: 0 0 16px 20px; padding: 0; color: #334155;")

    for item in container.find_all("li"):
        append_style(item, "margin: 0 0 8px; line-height: 1.8;")

    for pre in container.find_all("pre"):
        append_style(
            pre,
            "background-color: #1e293b; color: #e2e8f0; padding: 16px; border-radius: 8px; "
            "overflow-x: auto; font-family: \"Courier New\", monospace; font-size: 13px; "
            "line-height: 1.6; white-space: pre-wrap; margin: 16px 0;",
        )

    for code in container.find_all("code"):
        if code.parent and code.parent.name == "pre":
            append_style(code, "font-family: inherit; color: inherit; background: transparent; padding: 0;")
        else:
            append_style(
                code,
                "font-family: \"Courier New\", monospace; font-size: 0.95em; background: #eef2f7; "
                "color: #0f172a; padding: 1px 5px; border-radius: 4px;",
            )

    for table in container.find_all("table"):
        table["role"] = "presentation"
        append_style(
            table,
            "border-collapse: collapse; width: 100%; border: 1px solid #cbd5e0; "
            "margin: 16px 0; table-layout: auto;",
        )

    for cell in container.find_all("th"):
        append_style(
            cell,
            "border: 1px solid #cbd5e0; padding: 10px 12px; font-size: 14px; "
            "font-weight: 600; color: #1e293b; background-color: #f0f4f8;",
        )

    for cell in container.find_all("td"):
        append_style(
            cell,
            "border: 1px solid #cbd5e0; padding: 10px 12px; font-size: 14px; "
            "color: #334155; vertical-align: top;",
        )

    for strong in container.find_all("strong"):
        append_style(strong, "font-weight: 600; color: #1e293b;")

    for em in container.find_all("em"):
        append_style(em, "font-style: italic;")

    for hr in container.find_all("hr"):
        append_style(hr, "border: 0; border-top: 2px solid #e2e8f0; margin: 24px 0;")

    for link in container.find_all("a"):
        append_style(link, "color: #2563eb;")

    for blockquote in container.find_all("blockquote"):
        append_style(
            blockquote,
            "margin: 16px 0; padding: 8px 0 8px 14px; border-left: 4px solid #cbd5e0; "
            "color: #475569; background: #f8fafc;",
        )

    return "".join(str(child) for child in container.contents)


def markdown_to_html(md_content: str) -> str:
    """Convert Markdown to email-friendly HTML."""
    sanitized_markdown = sanitize_markdown_tables(md_content)
    protected_markdown, math_items = extract_math_placeholders(sanitized_markdown)
    html = MARKDOWN_RENDERER.render(protected_markdown)
    return style_rendered_html(html, math_items)


def create_email_html(question: dict) -> str:
    """Create HTML email optimized for email clients."""
    sections = parse_markdown_question(question["content"])
    date_str = sections["date"] or datetime.now().strftime("%Y-%m-%d")

    question_html = markdown_to_html(sections["question"])
    explanation_html = markdown_to_html(sections["explanation"])
    purpose_html = markdown_to_html(sections["purpose"])

    font_sans = "'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', 'Helvetica Neue', Arial, sans-serif"
    accent = "#2f5d73"
    accent_soft = "#eaf4f7"
    accent_border = "#c8dde5"
    answer_soft = "#f2f7ff"
    answer_border = "#d6e4ff"
    answer_accent = "#335c9b"
    purpose_soft = "#f4f8f2"
    purpose_border = "#d8e5cf"
    purpose_accent = "#5b7c46"

    purpose_block = ""
    if sections["purpose"]:
        purpose_block = f"""
              <table role=\"presentation\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"100%\" style=\"border-collapse: collapse; margin-top: 20px; background-color: {purpose_soft}; border: 1px solid {purpose_border};\">
                <tr>
                  <td style=\"padding: 0;\">
                    <div style=\"height: 5px; line-height: 5px; font-size: 5px; background-color: {purpose_accent};\">&nbsp;</div>
                    <div style=\"padding: 22px 24px 26px 24px;\">
                      <div style=\"font-family: {font_sans}; font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: {purpose_accent}; margin-bottom: 12px;\">출제 의도</div>
                      <div style=\"font-family: {font_sans}; font-size: 14px; line-height: 1.8; color: #475569;\">{purpose_html}</div>
                    </div>
                  </td>
                </tr>
              </table>
        """

    return f"""<!DOCTYPE html>
<html xmlns=\"http://www.w3.org/1999/xhtml\">
<head>
  <meta http-equiv=\"Content-Type\" content=\"text/html; charset=UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <meta name=\"x-apple-disable-message-reformatting\" />
  <title>통계분석 일일 문제</title>
</head>
<body style=\"margin: 0; padding: 0; background-color: #edf3f8; font-family: {font_sans};\">
  <div style=\"display: none; max-height: 0; overflow: hidden; opacity: 0; mso-hide: all;\">오늘의 통계 문제와 해설이 도착했습니다.</div>
  <table role=\"presentation\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"100%\" style=\"border-collapse: collapse; background-color: #edf3f8;\">
    <tr>
      <td align=\"center\" style=\"padding: 24px 12px;\">
        <table role=\"presentation\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"680\" style=\"border-collapse: collapse; width: 100%; max-width: 680px; background-color: #ffffff; border: 1px solid #d9e2ec;\">
          <tr>
            <td style=\"padding: 14px 28px; background-color: #f7fafc; border-bottom: 1px solid #d9e2ec;\">
              <span style=\"display: inline-block; font-family: {font_sans}; font-size: 11px; line-height: 1; letter-spacing: 0.08em; text-transform: uppercase; font-weight: 700; color: {accent}; background-color: #e3edf3; padding: 8px 10px;\">Daily Statistics Question</span>
            </td>
          </tr>
          <tr>
            <td style=\"padding: 30px 28px 26px 28px; background-color: {accent};\">
              <h1 style=\"margin: 0; font-family: {font_sans}; font-size: 30px; line-height: 1.25; color: #ffffff; font-weight: 700;\">📊 통계분석 일일 문제</h1>
              <p style=\"margin: 10px 0 0 0; font-family: {font_sans}; font-size: 14px; line-height: 1.7; color: #dbe7ee;\">{date_str}</p>
            </td>
          </tr>
          <tr>
            <td style=\"padding: 28px;\">
              <table role=\"presentation\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"100%\" style=\"border-collapse: collapse; background-color: {accent_soft}; border: 1px solid {accent_border};\">
                <tr>
                  <td style=\"padding: 0;\">
                    <div style=\"height: 5px; line-height: 5px; font-size: 5px; background-color: {accent};\">&nbsp;</div>
                    <div style=\"padding: 22px 24px 26px 24px;\">
                      <div style=\"font-family: {font_sans}; font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: {accent}; margin-bottom: 12px;\">문항</div>
                      <div style=\"font-family: {font_sans}; font-size: 16px; line-height: 1.8; color: #243b53;\">{question_html}</div>
                    </div>
                  </td>
                </tr>
              </table>

              <table role=\"presentation\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"100%\" style=\"border-collapse: collapse;\">
                <tr>
                  <td height=\"360\" valign=\"middle\" align=\"center\" style=\"height: 360px; padding: 0 24px; color: #6b7c93; font-family: {font_sans}; font-size: 14px; line-height: 1.7; text-align: center;\">
                    <div style=\"font-size: 15px; font-weight: 700; color: #52606d; margin-bottom: 10px;\">먼저 문제를 직접 풀어보세요.</div>
                    <div style=\"font-size: 13px; color: #7b8794;\">문제와 해설 사이의 큰 간격은 일부러 유지했습니다.</div>
                  </td>
                </tr>
              </table>

              <table role=\"presentation\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"100%\" style=\"border-collapse: collapse; background-color: {answer_soft}; border: 1px solid {answer_border};\">
                <tr>
                  <td style=\"padding: 0;\">
                    <div style=\"height: 5px; line-height: 5px; font-size: 5px; background-color: {answer_accent};\">&nbsp;</div>
                    <div style=\"padding: 22px 24px 26px 24px;\">
                      <div style=\"font-family: {font_sans}; font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: {answer_accent}; margin-bottom: 12px;\">해설</div>
                      <div style=\"font-family: {font_sans}; font-size: 15px; line-height: 1.8; color: #243b53;\">{explanation_html}</div>
                    </div>
                  </td>
                </tr>
              </table>

              {purpose_block}
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def open_smtp_connection():
    """Open an SMTP connection with sensible defaults for 465/587."""
    if SMTP_PORT == 465:
        return smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
    return smtplib.SMTP(SMTP_HOST, SMTP_PORT)


def validate_email_config() -> None:
    """Ensure required SMTP configuration is present."""
    missing = []
    if not SMTP_HOST:
        missing.append("SMTP_HOST")
    if not SMTP_USERNAME:
        missing.append("SMTP_USERNAME")
    if not SMTP_PASSWORD:
        missing.append("SMTP_PASSWORD")
    if not EMAIL_RECIPIENTS:
        missing.append("EMAIL_RECIPIENTS")

    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


def send_email(question: dict) -> None:
    """Send email with the question via SMTP."""
    validate_email_config()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f'통계분석 일일 문제 ({datetime.now().strftime("%Y-%m-%d")})'
    msg["From"] = f"Statistics Questions <{SMTP_USERNAME}>"
    msg["To"] = ", ".join(EMAIL_RECIPIENTS)

    html_content = create_email_html(question)
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    with open_smtp_connection() as server:
        if SMTP_PORT != 465:
            server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)

    print(f"✓ Email sent to {', '.join(EMAIL_RECIPIENTS)}")
    print(f"  Question: {question['file']}")


def main() -> None:
    """Main entry point."""
    print("📧 Starting daily question email...")
    question = get_random_question()
    print(f"📝 Selected: {question['file']}")
    send_email(question)
    print("✅ Done!")


if __name__ == "__main__":
    main()
