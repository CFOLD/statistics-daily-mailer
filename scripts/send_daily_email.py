#!/usr/bin/env python3
"""
Daily Statistics Question Email Sender

Fetches a random question from generated_questions/, parses Markdown,
converts to HTML with HTML math entities (no JS), and sends via SMTP.

Email-optimized design:
- No JavaScript (works in all email clients)
- Inline CSS for maximum compatibility
- Tables render correctly in Gmail/Outlook/Apple Mail
- Large spacing between question and explanation
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

    # Split by '---' delimiter (flexible newlines)
    parts = re.split(r'\n\s*---\s*\n', content)

    for part in parts:
        part = part.strip()
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
    """Create HTML email optimized for email clients."""
    date_str = datetime.now().strftime('%Y-%m-%d')
    sections = parse_markdown_question(question['content'])

    # Convert markdown to HTML with math conversion
    question_html = markdown_to_html(sections['question'])
    explanation_html = markdown_to_html(sections['explanation'])
    purpose_html = markdown_to_html(sections['purpose'])

    # Gothic font family for Korean
    font_sans = "'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', 'Helvetica Neue', Arial, sans-serif"

    return f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <meta name="x-apple-disable-message-reformatting" />
  <title>통계분석 일일 문제</title>
  <style type="text/css">
    body, table, td, p, a, li, blockquote {{
      -ms-text-size-adjust: 100%;
      -webkit-text-size-adjust: 100%;
      margin: 0;
      padding: 0;
    }}
    table, td {{
      mso-table-lspace: 0pt;
      mso-table-rspace: 0pt;
    }}
    table {{
      border-collapse: collapse !important;
    }}
    img {{
      -ms-interpolation-mode: bicubic;
      border: 0;
      height: auto;
      line-height: 100%;
      outline: none;
      text-decoration: none;
    }}
    p {{
      margin: 0 0 16px 0;
    }}
    /* Table styles */
    table.data-table, table.data-table td, table.data-table th {{
      border: 1px solid #cbd5e0 !important;
      border-collapse: collapse !important;
    }}
    table.data-table {{
      width: 100% !important;
      mso-table-lspace: 0pt !important;
      mso-table-rspace: 0pt !important;
    }}
    table.data-table th {{
      background-color: #e2e8f0 !important;
      font-weight: bold !important;
      text-align: left !important;
      padding: 8px 12px !important;
    }}
    table.data-table td {{
      padding: 8px 12px !important;
    }}
    a {{
      color: #2563eb;
    }}
    u+[b] a {{
      color: inherit;
      text-decoration: none;
    }}
    @media screen and (max-width: 600px) {{
      .email-container {{
        width: 100% !important;
      }}
      .content-padding {{
        padding-left: 20px !important;
        padding-right: 20px !important;
      }}
    }}
  </style>
</head>
<body style="margin: 0; padding: 0; background-color: #f5f5f5; font-family: {font_sans};">

  <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f5f5f5;">
    <tr>
      <td align="center" style="padding: 20px 0;">

        <table class="email-container" role="presentation" border="0" cellpadding="0" cellspacing="0" width="600" style="background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); max-width: 600px; width: 100%;">

          <!-- Header -->
          <tr>
            <td style="background: linear-gradient(135deg, #4A90A4 0%, #357A9A 100%); padding: 32px 28px; text-align: left;">
              <h1 style="margin: 0; font-family: {font_sans}; font-size: 26px; font-weight: 600; color: #ffffff; line-height: 1.3;">📊 통계분석 일일 문제</h1>
              <p style="margin: 10px 0 0 0; font-family: {font_sans}; font-size: 14px; color: rgba(255,255,255,0.9);">{date_str}</p>
            </td>
          </tr>

          <!-- Content -->
          <tr>
            <td class="content-padding" style="padding: 36px 32px; background-color: #ffffff;">

              <!-- Question Section -->
              <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f8fafb; border: 1px solid #e1e8ed; border-radius: 8px; margin-bottom: 40px;">
                <tr>
                  <td style="padding: 28px 24px;">
                    <h2 style="margin: 0 0 20px 0; font-family: {font_sans}; font-size: 18px; font-weight: 600; color: #2c5282; padding-bottom: 14px; border-bottom: 2px solid #bed6e6;">문항</h2>
                    <div style="font-family: {font_sans}; font-size: 16px; line-height: 1.8; color: #334155;">
                      {question_html}
                    </div>
                  </td>
                </tr>
              </table>

              <!-- Large spacer (1000px) -->
              <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" height="1000" style="background: linear-gradient(to bottom, #f5f5f5, rgba(245,245,245,0.3)); margin: 40px 0;">
                <tr>
                  <td align="center" valign="middle" style="color: #94a3b8; font-size: 15px; font-family: {font_sans};">
                    <p style="margin: 0 0 10px 0; font-size: 16px; font-weight: 600;">📝 아래로 스크롤하여 해설 확인</p>
                    <p style="margin: 0; font-size: 13px; color: #64748b;">(먼저 문제를 풀어보세요!)</p>
                  </td>
                </tr>
              </table>

              <!-- Explanation Section -->
              <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f0f7ff; border: 1px solid #d1e8ff; border-radius: 8px; margin-bottom: 16px;">
                <tr>
                  <td style="padding: 28px 24px;">
                    <h2 style="margin: 0 0 20px 0; font-family: {font_sans}; font-size: 18px; font-weight: 600; color: #2b6cb0; padding-bottom: 14px; border-bottom: 2px solid #93c5fd;">해설</h2>
                    <div style="font-family: {font_sans}; font-size: 15px; line-height: 1.8; color: #334155;">
                      {explanation_html}
                    </div>
                  </td>
                </tr>
              </table>

              <!-- Purpose Section -->
              <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f9fbf5; border: 1px solid #e8f0d8; border-radius: 8px;">
                <tr>
                  <td style="padding: 28px 24px;">
                    <h2 style="margin: 0 0 20px 0; font-family: {font_sans}; font-size: 18px; font-weight: 600; color: #276749; padding-bottom: 14px; border-bottom: 2px solid #9ae6b4;">출제 의도</h2>
                    <div style="font-family: {font_sans}; font-size: 14px; line-height: 1.8; color: #4a5568;">
                      {purpose_html}
                    </div>
                  </td>
                </tr>
              </table>

            </td>
          </tr>

        </table>

      </td>
    </tr>
  </table>

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
