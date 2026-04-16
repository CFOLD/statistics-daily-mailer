#!/usr/bin/env python3
"""Daily email sender.

Loads `templates/daily_email.html`, renders question markdown to HTML,
and sends via SMTP. Markdown is converted to email-friendly HTML, while
LaTeX expressions are rendered at send time into PNG inline attachments
referenced from the HTML with CID URLs.

Usage: python scripts/send_daily_email.py [--file PATH] [--dry-run]
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from string import Template
import smtplib

try:
    import holidays
except Exception:
    holidays = None

from email_render import InlineImage, RenderedFragment, render_markdown

BASE = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = BASE / "templates" / "daily_email.html"
QUESTIONS_DIR = BASE / "questions"

DEFAULTS = {
    "title": "통계분석 일일 문제",
    "headline": "📊 통계분석 일일 문제",
    "badge": "Daily Statistics Question",
    "page_bg": "#edf3f8",
    "accent": "#2f5d73",
    "badge_bg": "#e3edf3",
    "header_subtle": "#dbe7ee",
    "preheader": "오늘의 통계 문제와 해설이 도착했습니다.",
    "font_sans": "'Noto Sans KR', Arial, sans-serif",
}

SECTION_RE = re.compile(r"^(#{2,6})\s+(.+?)\s*$", re.I | re.M)
DATE_FROM_FILENAME_RE = re.compile(r"_(\d{8})\.md$")


@dataclass
class ComposedEmail:
    html: str
    inline_images: list[InlineImage] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def preview_html(self) -> str:
        html = self.html
        for image in self.inline_images:
            html = html.replace(f"cid:{image.cid}", image.as_data_uri())
        return html


def find_question() -> Path | None:
    today = datetime.now().strftime("%Y%m%d")
    today_matches = sorted(QUESTIONS_DIR.glob(f"*{today}*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return today_matches[0] if today_matches else None


def parse_sections(content: str) -> dict:
    lines = content.splitlines()
    sections = {"question": "", "explanation": "", "date": ""}
    current = None
    for ln in lines:
        stripped = ln.strip()
        m = SECTION_RE.match(stripped)
        if m:
            title = re.sub(r"\s+", " ", m.group(2)).strip().lower()
            if title in ("문항", "문제", "problem"):
                current = "question"
                continue
            if title in ("해설", "정답 및 해설", "정답", "solution", "answers"):
                current = "explanation"
                continue
            if current:
                sections[current] += ln + "\n"
            continue
        if re.match(r"^\s*---\s*$", ln):
            continue
        gen = re.match(r"^\*?generated on:\s*(.+?)\*?\s*$", stripped, re.I)
        if gen:
            sections["date"] = gen.group(1)
            continue
        if current:
            sections[current] += ln + "\n"
    if not sections["question"] and not sections["explanation"]:
        sections["question"] = content
    for key in ("question", "explanation"):
        sections[key] = sections[key].strip()
    return sections


def load_template() -> Template:
    return Template(TEMPLATE_PATH.read_text(encoding="utf-8"))


def extract_target_date(path: Path) -> str | None:
    match = DATE_FROM_FILENAME_RE.search(path.name)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def is_kr_business_day(day: date) -> bool:
    if day.weekday() >= 5:
        return False
    if holidays is None:
        return True
    kr_holidays = holidays.country_holidays("KR", years=[day.year])
    return day not in kr_holidays


def open_smtp():
    port = int(os.getenv("SMTP_PORT", 587))
    host = os.getenv("SMTP_HOST")
    if not host:
        raise RuntimeError("SMTP_HOST not set")
    if port == 465:
        return smtplib.SMTP_SSL(host, port)
    return smtplib.SMTP(host, port)


def send_email(composed: ComposedEmail, subject: str):
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    recipients = [e.strip() for e in os.getenv("EMAIL_RECIPIENTS", "").split(",") if e.strip()]
    if not recipients:
        raise RuntimeError("EMAIL_RECIPIENTS not set")

    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"] = username or "noreply@example.com"
    msg["To"] = ", ".join(recipients)

    alternative = MIMEMultipart("alternative")
    alternative.attach(MIMEText(composed.html, "html", "utf-8"))
    msg.attach(alternative)

    for image in composed.inline_images:
        maintype, subtype = image.mime_type.split("/", 1)
        if maintype != "image":
            raise ValueError(f"Unsupported inline image type: {image.mime_type}")
        part = MIMEImage(image.content, _subtype=subtype)
        part.add_header("Content-ID", f"<{image.cid}>")
        part.add_header("Content-Disposition", "inline", filename=image.filename)
        msg.attach(part)

    with open_smtp() as s:
        if int(os.getenv("SMTP_PORT", 587)) != 465:
            s.starttls()
        if username and password:
            s.login(username, password)
        s.send_message(msg)


def build_blocks(question_html: str, explanation_html: str, accent: str) -> str:
    return f"""
    <table role="presentation" width="100%" style="border-collapse:collapse; margin-bottom:24px; background:#eaf4f7; border:1px solid #c8dde5;">
      <tr><td style="padding:0;">
        <div style="height:5px; background:{accent}; line-height:5px; font-size:5px;">&nbsp;</div>
        <div style="padding:22px;">{question_html}</div>
      </td></tr>
    </table>

    <table role="presentation" width="100%" style="border-collapse:collapse;">
      <tr><td height="360" style="text-align:center; color:#6b7c93;">&nbsp;</td></tr>
    </table>

    <table role="presentation" width="100%" style="border-collapse:collapse; margin-top:14px; background:#f2f7ff; border:1px solid #d6e4ff;">
      <tr><td style="padding:0;">
        <div style="height:5px; background:#335c9b; line-height:5px; font-size:5px;">&nbsp;</div>
        <div style="padding:22px;">{explanation_html}</div>
      </td></tr>
    </table>
    """


def compose_email(question_fragment: RenderedFragment, explanation_fragment: RenderedFragment, mail_date: str) -> ComposedEmail:
    tpl = load_template()
    vars = DEFAULTS.copy()
    vars.update({
        "content_blocks": build_blocks(question_fragment.html, explanation_fragment.html, DEFAULTS["accent"]),
        "subhead": mail_date,
    })
    html = tpl.safe_substitute(vars)
    return ComposedEmail(
        html=html,
        inline_images=[*question_fragment.inline_images, *explanation_fragment.inline_images],
        warnings=[*question_fragment.warnings, *explanation_fragment.warnings],
    )


def emit_warnings(warnings: list[str]) -> None:
    for warning in warnings:
        print(f"[warn] {warning}", file=sys.stderr)


def main(argv: list[str]):
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--file", help="Markdown file to send")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    today = datetime.now().date()
    if not args.file and not args.dry_run and not is_kr_business_day(today):
        print(f"Skipping send for non-business day: {today.isoformat()}")
        return

    qfile = Path(args.file) if args.file else find_question()
    if qfile is None:
        print("No question file found for today; skipping send.")
        return

    content = qfile.read_text(encoding="utf-8")
    secs = parse_sections(content)
    question_fragment = render_markdown(secs["question"])
    explanation_fragment = render_markdown(secs["explanation"])
    mail_date = extract_target_date(qfile) or datetime.now().strftime("%Y-%m-%d")
    composed = compose_email(question_fragment, explanation_fragment, mail_date)
    emit_warnings(composed.warnings)

    if args.dry_run:
        out = Path.home() / "email_preview_statistics.html"
        out.write_text(composed.preview_html(), encoding="utf-8")
        print("Wrote preview to", out)
        print(f"Inline images: {len(composed.inline_images)}")
        return

    subject = f"{DEFAULTS['title']} ({mail_date})"
    send_email(composed, subject)
    print("Sent email")


if __name__ == "__main__":
    main(sys.argv[1:])
