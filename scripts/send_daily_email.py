#!/usr/bin/env python3
"""
Daily Statistics Question Email Sender

Fetches a random question from generated_questions/ and sends via SMTP.
"""

import json
import os
import smtplib
import sys
import random
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from datetime import datetime

# Configuration (relative to repo root)
QUESTIONS_DIR = Path('generated_questions')
SMTP_HOST = os.getenv('SMTP_HOST')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USERNAME = os.getenv('SMTP_USERNAME')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
EMAIL_RECIPIENTS = os.getenv('EMAIL_RECIPIENTS', '').split(',')


def get_random_question() -> dict:
    """Get a random question from the generated_questions directory."""
    sys.stderr.write(f"DEBUG: Current dir = {os.getcwd()}\n")
    sys.stderr.write(f"DEBUG: QUESTIONS_DIR = {QUESTIONS_DIR}\n")
    sys.stderr.write(f"DEBUG: QUESTIONS_DIR exists = {QUESTIONS_DIR.exists()}\n")
    sys.stderr.write(f"DEBUG: QUESTIONS_DIR is_dir = {QUESTIONS_DIR.is_dir()}\n")
    md_files = list(QUESTIONS_DIR.glob('*.md'))
    sys.stderr.write(f"DEBUG: Found {len(md_files)} files: {[f.name for f in md_files]}\n")
    if not md_files:
        raise FileNotFoundError("No question files found")

    selected_file = random.choice(md_files)
    content = selected_file.read_text(encoding='utf-8')
    return {'file': selected_file.name, 'content': content}


def create_email_html(question: dict) -> str:
    """Create HTML email body with the question."""
    date_str = datetime.now().strftime('%Y-%m-%d')

    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}
    .header {{ background: #4A90A4; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
    .content {{ background: #f9f9f9; padding: 20px; border: 1px solid #ddd; border-top: none; }}
    .math {{ font-family: 'Courier New', monospace; background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }}
    .footer {{ text-align: center; padding: 20px; color: #666; font-size: 0.9em; }}
    h1 {{ margin: 0; font-size: 1.5em; }}
    h2 {{ color: #4A90A4; font-size: 1.2em; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>📊 통계분석 일일 문제</h1>
    <p>{date_str}</p>
  </div>

  <div class="content">
    {question['content']}
  </div>

  <div class="footer">
    <p>더 많은 문제는 <a href="https://github.com/CFOLD/statistics-questions">statistics-questions 저장소</a>에서 확인하세요.</p>
  </div>
</body>
</html>
"""


def send_email(question: dict) -> None:
    """Send email with the question via SMTP."""
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'통계분석 일일 문제 ({datetime.now().strftime("%Y-%m-%d")})'
    msg['From'] = f'Statistics Questions <{SMTP_USERNAME}>'
    msg['To'] = ', '.join(EMAIL_RECIPIENTS)

    html_content = create_email_html(question)
    part = MIMEText(html_content, 'html', 'utf-8')
    msg.attach(part)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)

    print(f"✓ Email sent to {', '.join(EMAIL_RECIPIENTS)}")
    print(f"  Question: {question['file']}")


def main():
    """Main entry point."""
    print("📧 Starting daily question email...")

    question = get_random_question()
    print(f"📝 Selected: {question['file']}")

    send_email(question)
    print("✅ Done!")


if __name__ == '__main__':
    main()
