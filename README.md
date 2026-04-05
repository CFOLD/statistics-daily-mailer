# statistics-daily-mailer

Private GitHub repository for sending daily statistics questions by email with GitHub Actions.

## What it does

- Finds today's dated question file from `questions/` when available
- Falls back to the most recent question file if no file matches today's date
- Converts markdown to email-friendly HTML using the shared email template format
- Sends via standard SMTP using shared secret names
- Runs automatically every day at **09:00 Asia/Seoul**

## Repository layout

- `questions/`: statistics question markdown files
- `templates/daily_email.html`: shared email template
- `scripts/send_daily_email.py`: email sender script
- `.github/workflows/daily-email.yml`: GitHub Actions workflow
- `.github/SECRETS_SETUP.md`: secret setup guide

## Required GitHub secrets

Set these repository secrets before running:

- `SMTP_HOST`: SMTP server address, e.g. `smtp.gmail.com`
- `SMTP_PORT`: SMTP port, e.g. `465` or `587`
- `SMTP_USERNAME`: SMTP username / sender email address
- `SMTP_PASSWORD`: SMTP password or app password
- `EMAIL_RECIPIENTS`: recipient email(s), comma-separated

## Gmail notes

If you use Gmail, use a Gmail **App Password**, not your normal login password.
This usually requires 2-Step Verification to be enabled on the Gmail account.

## Schedule

GitHub Actions cron uses UTC.

- `0 0 * * *` UTC = `09:00` Asia/Seoul every day

## Manual run

You can manually trigger the workflow from the Actions tab.

## Adding question files

Place question markdown files in the `questions/` directory.

Recommended naming pattern:

- `*_YYYYMMDD*.md`

Example:

- `20260410_question.md`
