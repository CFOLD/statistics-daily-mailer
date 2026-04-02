#!/usr/bin/env python3
"""
Daily Statistics Question Email Sender

Fetches a random question from generated_questions/, parses Markdown,
converts to HTML with HTML math entities (no JS), and sends via SMTP.
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


def parse_markdown_question(content: str) -> dict:
    """Parse markdown question into sections (question, explanation, purpose)."""
    sections = {
        'question': '',
        'explanation': '',
        'purpose': '',
        'date': ''
    }

    # Split by '---' delimiter
    parts = re.split(r'\n---\n', content)

    for part in parts:
        if part.startswith('## 문항'):
            sections['question'] = part.replace('## 문항', '').strip()
        elif part.startswith('## 해설'):
            sections['explanation'] = part.replace('## 해설', '').strip()
        elif part.startswith('## 출제 의도'):
            sections['purpose'] = part.replace('## 출제 의도', '').strip()
        elif 'Generated on:' in part:
            sections['date'] = part.strip()

    return sections


def latex_to_html(latex: str) -> str:
    """Convert LaTeX math to HTML entities."""
    # Greek letters
    replacements = {
        'alpha': '&alpha;', 'beta': '&beta;', 'gamma': '&gamma;',
        'delta': '&delta;', 'epsilon': '&epsilon;', 'zeta': '&zeta;',
        'eta': '&eta;', 'theta': '&theta;', 'lambda': '&lambda;',
        'mu': '&mu;', 'xi': '&xi;', 'pi': '&pi;', 'rho': '&rho;',
        'sigma': '&sigma;', 'tau': '&tau;', 'phi': '&phi;',
        'chi': '&chi;', 'psi': '&psi;', 'omega': '&omega;',
        'Delta': '&Delta;', 'Sigma': '&Sigma;', 'Pi': '&Pi;',
        'Phi': '&Phi;', 'Omega': '&Omega;',
        # Symbols
        'times': '&times;', 'div': '&divide;', 'pm': '&plusmn;',
        'approx': '&approx;', 'leq': '&le;', 'geq': '&ge;',
        'neq': '&ne;', 'infty': '&infin;', 'sqrt': '&radic;',
        'sum': '&sum;', 'prod': '&prod;', 'int': '&int;',
        'partial': '&part;', 'prime': '&prime;',
        'rightarrow': '&rarr;', 'leftarrow': '&larr;',
        'Leftrightarrow': '&harr;', 'equiv': '&equiv;',
        'in': '&isin;', 'subset': '&sub;', 'supset': '&sup;',
        'cup': '&cup;', 'cap': '&cap;', 'emptyset': '&empty;',
    }

    result = latex
    for key, value in replacements.items():
        result = result.replace(key, value)

    # Superscripts: ^{...} or ^...
    result = re.sub(r'\^\{([^}]*)\}', r'<sup>\1</sup>', result)
    result = re.sub(r'\^([^ }\{])', r'<sup>\1</sup>', result)

    # Subscripts: _{...} or _...
    result = re.sub(r'_{([^}]*)\}', r'<sub>\1</sub>', result)
    result = re.sub(r'_([^ }\{])', r'<sub>\1</sub>', result)

    return result


def convert_math_to_html(content: str) -> str:
    """Convert LaTeX math expressions to HTML, keeping LaTeX for reference."""
    # Inline math: $...$ → show HTML + LaTeX
    def replace_inline(match):
        latex = match.group(1)
        html = latex_to_html(latex)
        return f'<code class="math">{html} <span class="latex">(${latex}$)</span></code>'

    # Display math: $$...$$ → show HTML + LaTeX
    def replace_display(match):
        latex = match.group(1)
        html = latex_to_html(latex)
        return f'<div class="math-display"><code>{html} <span class="latex">($${latex}$$)</span></code></div>'

    result = content
    result = re.sub(r'\$\$([^$]+)\$\$', replace_display, result)
    result = re.sub(r'\$([^$]+)\$', replace_inline, result)

    return result


def markdown_to_html(md_content: str) -> str:
    """Convert Markdown to HTML (preserves math for conversion)."""
    # Temporarily hide math expressions
    hidden_math = []
    def hide_math(match):
        hidden_math.append(match.group(0))
        return f'__MATH_{len(hidden_math)-1}__'

    # Hide math first
    temp_content = re.sub(r'\$[\$\w\W]*?\$', hide_math, md_content)

    # Convert to HTML
    html = markdown.markdown(temp_content, extensions=['fenced_code', 'tables'])

    # Restore math and convert
    for i, math in enumerate(hidden_math):
        html = html.replace(f'__MATH_{i}__', math)

    # Convert math to HTML
    html = convert_math_to_html(html)

    return html


def create_email_html(question: dict) -> str:
    """Create HTML email with large spacing between question and explanation."""
    date_str = datetime.now().strftime('%Y-%m-%d')
    sections = parse_markdown_question(question['content'])

    # Convert markdown to HTML with math conversion
    question_html = markdown_to_html(sections['question'])
    explanation_html = markdown_to_html(sections['explanation'])
    purpose_html = markdown_to_html(sections['purpose'])

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
      margin-bottom: 80px;
    }}
    .question-section h2 {{
      color: #2c5282;
      font-size: 18px;
      font-weight: 600;
      margin: 0 0 16px 0;
      padding-bottom: 12px;
      border-bottom: 2px solid #bed6e6;
    }}
    .question-section p {{
      margin: 0 0 12px 0;
      font-size: 16px;
      line-height: 1.8;
    }}
    .question-section p:last-child {{
      margin-bottom: 0;
    }}
    .spacer {{
      height: 1000px;
      background: linear-gradient(to bottom, #f5f5f5, transparent);
      display: flex;
      align-items: center;
      justify-content: center;
      color: #ccc;
      font-size: 14px;
    }}
    .explanation-section {{
      background: #f0f7ff;
      border: 1px solid #d1e8ff;
      border-radius: 10px;
      padding: 24px 22px;
      margin-bottom: 20px;
    }}
    .explanation-section h2 {{
      color: #2b6cb0;
      font-size: 18px;
      font-weight: 600;
      margin: 0 0 16px 0;
      padding-bottom: 12px;
      border-bottom: 2px solid #93c5fd;
    }}
    .explanation-section p {{
      margin: 0 0 12px 0;
      font-size: 15px;
      line-height: 1.8;
    }}
    .explanation-section p:last-child {{
      margin-bottom: 0;
    }}
    .purpose-section {{
      background: #f9fbf5;
      border: 1px solid #e8f0d8;
      border-radius: 10px;
      padding: 24px 22px;
    }}
    .purpose-section h2 {{
      color: #276749;
      font-size: 18px;
      font-weight: 600;
      margin: 0 0 16px 0;
      padding-bottom: 12px;
      border-bottom: 2px solid #9ae6b4;
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
    .math {{
      background: #e8f5e9;
      border: 1px solid #c8e6c9;
    }}
    .math-display {{
      text-align: center;
      padding: 16px;
      margin: 12px 0;
      background: #f1f8f4;
      border-radius: 8px;
    }}
    .latex {{
      font-size: 0.8em;
      color: #999;
      font-style: italic;
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
    ul, ol {{
      margin: 0 0 12px 0;
      padding-left: 24px;
    }}
    ul li, ol li {{
      margin: 6px 0;
    }}
    hr {{
      border: none;
      border-top: 2px solid #e2e8f0;
      margin: 24px 0;
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
      <div class="question-section">
        <h2>문항</h2>
        {question_html}
      </div>

      <div class="spacer">
        <div>
          <p>📝 아래로 스크롤하여 해설 확인</p>
          <p style="font-size: 12px;">(먼저 문제를 풀어보세요!)</p>
        </div>
      </div>

      <div class="explanation-section">
        <h2>해설</h2>
        <div class="explanation-content">{explanation_html}</div>
      </div>

      <div class="purpose-section">
        <h2>출제 의도</h2>
        <div class="purpose-content">{purpose_html}</div>
      </div>
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
