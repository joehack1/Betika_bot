# GitHub Actions scheduler (Betika bot)

This repo includes a scheduled workflow that runs the Selenium bot **3 times per day** (UTC schedule converted for **Africa/Nairobi**).

## Setup

1. Push the workflow file to your repo.
2. In GitHub: **Settings → Secrets and variables → Actions → New repository secret**
   - `BETIKA_USERNAME` (your phone / username)
   - `BETIKA_PASSWORD` (your password / PIN)
3. (Optional) Add secret `BETIKA_EXECUTE` = `true` if you want scheduled runs to actually place bets.
   - If not set, the job runs in dry-run mode.

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
