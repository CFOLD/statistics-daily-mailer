# statistics-daily-mailer

Private GitHub repository for sending one daily statistics question email with GitHub Actions.

This repository is the **mailer runtime**, not the question-generation skill itself.
Question generation logic lives in the `statistics-question-creator` skill, and completed markdown question files are placed into this repository's `questions/` directory for delivery.

## What this repository does

- Looks for a question markdown file in `questions/`
- Prefers a file whose name includes today's date (`YYYYMMDD`)
- Falls back to the most recent question file if no dated file matches today
- Converts the markdown question into email-friendly HTML
- Sends the email through SMTP using GitHub Actions
- Runs automatically every day at **09:00 Asia/Seoul**

## Repository layout

- `questions/`: delivered question markdown files
- `templates/daily_email.html`: email HTML template
- `scripts/send_daily_email.py`: mail sending script
- `.github/workflows/daily-email.yml`: scheduled/manual GitHub Actions workflow
- `.github/SECRETS_SETUP.md`: GitHub Actions secret setup guide

## Required GitHub secrets

Set these repository secrets before running the workflow:

- `SMTP_HOST`: SMTP server address, e.g. `smtp.gmail.com`
- `SMTP_PORT`: SMTP port, e.g. `465` or `587`
- `SMTP_USERNAME`: SMTP username / sender email address
- `SMTP_PASSWORD`: SMTP password or app password
- `EMAIL_RECIPIENTS`: recipient email(s), comma-separated

## Gmail notes

If you use Gmail, use a Gmail **App Password**, not your normal account password.
This usually requires enabling 2-Step Verification on the Google account.

## Schedule

GitHub Actions cron uses UTC.

- `0 0 * * *` UTC = `09:00` Asia/Seoul every day

## Manual run

You can manually test the workflow from the **Actions** tab.

## Adding question files

Place question markdown files in the `questions/` directory.

Recommended naming pattern:

- `*_YYYYMMDD*.md`

Examples:

- `20260410_question.md`
- `ab12cd34_20260410.md`
