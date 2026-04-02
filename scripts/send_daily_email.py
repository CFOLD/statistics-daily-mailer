#!/usr/bin/env python3
"""
Daily Statistics Question Email Sender

Fetches a random question from generated_questions/ and sends via SMTP.
Converts Markdown to HTML with styled sections for email display.
"""

import os
import re
import smtplib
import random
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from datetime import datetime
import markdown

# Configuration - use working directory (repo root)
QUESTIONS_DIR = Path.cwd() / 'generated_questions'
SMTP_HOST = os.getenv('SMTP_HOST')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USERNAME = os.getenv('SMTP_USERNAME')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
EMAIL_RECIPIENTS = os.getenv('EMAIL_RECIPIENTS', '').split(',')


def get_random_question() -> dict:
    """Get a random question from the generated_questions directory."""
    md_files = list(QUESTIONS_DIR.glob('*.md'))
    if not md_files:
        raise FileNotFoundError("No question files found")

    selected_file = random.choice(md_files)
    content = selected_file.read_text(encoding='utf-8')
    return {'file': selected_file.name, 'content': content}


def markdown_to_html(md_content: str) -> str:
    """Convert Markdown to HTML with proper styling for email."""
    # Use markdown library with extensions
    html = markdown.markdown(
        md_content,
        extensions=['fenced_code', 'tables']
    )
    return html


def create_email_html(question: dict) -> str:
    """Create HTML email body with the question."""
    date_str = datetime.now().strftime('%Y-%m-%d')

    # Convert markdown content to HTML
    content_html = markdown_to_html(question['content'])

    # Remove any extra outer divs that markdown might add
    content_html = re.sub(r'^<div>\s*|(?s)<div>(.*?)</div>\s*$', r'\1', content_html)

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
      line-height: 1.8;
      color: #333;
      max-width: 700px;
      margin: 0 auto;
      padding: 20px;
      background-color: #f5f5f5;
    }}
    .email-container {{
      background: white;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }}
    .header {{
      background: linear-gradient(135deg, #4A90A4 0%, #357A9A 100%);
      color: white;
      padding: 28px 24px;
    }}
    .header h1 {{
      margin: 0;
      font-size: 28px;
      font-weight: 600;
    }}
    .header p {{
      margin: 8px 0 0 0;
      font-size: 14px;
      opacity: 0.9;
    }}
    .content {{
      padding: 32px 28px;
    }}
    .question-section {{
      background: #f8fafb;
      border: 1px solid #e1e8ed;
      border-radius: 10px;
      padding: 24px 22px;
      margin-bottom: 36px;
    }}
    .explanation-section {{
      background: #f0f7ff;
      border: 1px solid #d1e8ff;
      border-radius: 10px;
      padding: 24px 22px;
      margin-bottom: 36px;
    }}
    .purpose-section {{
      background: #f9fbf5;
      border: 1px solid #e8f0d8;
      border-radius: 10px;
      padding: 24px 22px;
    }}
    .question-section h2 {{
      color: #2c5282;
      font-size: 18px;
      font-weight: 600;
      margin: 0 0 16px 0;
      padding-bottom: 12px;
      border-bottom: 2px solid #bed6e6;
    }}
    .explanation-section h2 {{
      color: #2b6cb0;
      font-size: 18px;
      font-weight: 600;
      margin: 0 0 16px 0;
      padding-bottom: 12px;
      border-bottom: 2px solid #93c5fd;
    }}
    .purpose-section h2 {{
      color: #276749;
      font-size: 18px;
      font-weight: 600;
      margin: 0 0 16px 0;
      padding-bottom: 12px;
      border-bottom: 2px solid #9ae6b4;
    }}
    .question-section p {{
      margin: 0;
      font-size: 16px;
      line-height: 1.8;
    }}
    .explanation-section p {{
      margin: 0 0 12px 0;
      font-size: 15px;
      line-height: 1.8;
    }}
    .explanation-section p:last-child {{
      margin-bottom: 0;
    }}
    .purpose-section p {{
      margin: 0;
      font-size: 14px;
      line-height: 1.8;
      color: #4a5568;
    }}
    code {{
      font-family: 'SF Mono', 'Monaco', 'Consolas', 'Courier New', monospace;
      background: #edf2f7;
      color: #2d3748;
      padding: 3px 8px;
      border-radius: 5px;
      font-size: 0.9em;
    }}
    pre {{
      background: #1a202c;
      color: #f7fafc;
      padding: 16px;
      border-radius: 8px;
      overflow-x: auto;
      margin: 12px 0;
    }}
    pre code {{
      background: transparent;
      color: inherit;
      padding: 0;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      margin: 16px 0;
      font-size: 14px;
    }}
    th {{
      background: #e2e8f0;
      padding: 10px 12px;
      text-align: left;
      font-weight: 600;
      border: 1px solid #cbd5e0;
    }}
    td {{
      padding: 10px 12px;
      border: 1px solid #e2e8f0;
    }}
    hr {{
      border: none;
      border-top: 2px solid #e2e8f0;
      margin: 24px 0;
    }}
    .math {{
      font-family: 'Times New Roman', serif;
      font-style: italic;
      background: #f7fafc;
      padding: 2px 6px;
      border-radius: 3px;
    }}
  </style>
</head>
<body>
  <div class="email-container">
    <div class="header">
      <h1>📊 통계분석 일일 문제</h1>
      <p>{date_str}</p>
    </div>

    <div class="content">
      {content_html}
    </div>
  </div>
</body>
</html>"""


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
