# GitHub Actions scheduler (Betika bot)

This repo includes a scheduled workflow that runs the Selenium bot **3 times per day** (UTC schedule converted for **Africa/Nairobi**).

## Setup

1. Push the workflow file to your repo.
2. In GitHub: **Settings → Secrets and variables → Actions → New repository secret**
   - `BETIKA_USERNAME` (your phone / username)
   - `BETIKA_PASSWORD` (your password / PIN)
3. (Optional) Add secret `BETIKA_EXECUTE=true` if you want scheduled runs to actually place bets.
   - If not set, the job runs in dry-run mode.

## Recommended: self-hosted runner (avoids OTP/CAPTCHA)

Betika may show an OTP/CAPTCHA/suspicious-login challenge on GitHub-hosted runners and headless browsers. For reliability, use a **self-hosted runner** (PC/VPS).

1. Create a self-hosted runner in GitHub: **Settings → Actions → Runners → New self-hosted runner**.
2. Add repo variable `BETIKA_RUNS_ON=self-hosted` (Settings → Secrets and variables → Actions → Variables).
3. (Optional but recommended) Add repo variable `BETIKA_PROFILE_DIR=/home/runner/.cache/betika-bot/chrome-profile` so the bot can reuse a persisted Chrome session.
4. First-time session bootstrap (manual run):
   - Run **Actions → Betika bot → Run workflow**
   - Set `headless=false` and `manual_login_wait=180`
   - Complete OTP in the visible browser window
   - After this, scheduled runs can stay `headless=true` using the same `BETIKA_PROFILE_DIR`

## Parameters (defaults)

The workflow defaults to:

- `BETIKA_COUNT=20`
- `BETIKA_STAKE=2` (KES)
- `BETIKA_MAX_ODDS=1.40`
- `BETIKA_MIN_ODDS=1.01`

You can override these from **Actions → Betika bot → Run workflow** (manual run).

## Notes

- GitHub scheduled workflows run in **UTC**. The cron in `.github/workflows/betika-bot.yml` is set to `06:05, 14:05, 22:05` Africa/Nairobi.
- On failures, the workflow uploads `debug_artifacts/` (screenshot + HTML) when `--debug-login` triggers.
- GitHub-hosted Ubuntu runners may not have Google Chrome available. The workflow installs `chromium` + `chromium-driver` and points Selenium at `/usr/bin/chromium` by default (override with `BETIKA_CHROME_BINARY`).
