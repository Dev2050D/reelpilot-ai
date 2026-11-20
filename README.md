# ReelPilot AI

Free scheduled Instagram Reels cross-posting starter for an Instagram account you own or are authorized to manage.

**Source:** https://www.instagram.com/aoonoww/  
**Schedule:** every 30 minutes (GitHub Actions schedule; best-effort, not exact-time guaranteed)  
**Mode:** automatic publishing after Meta API credentials are configured  
**Hosting:** GitHub Actions only; no paid always-on web server.

## Free operating mode

- GitHub Actions runs the monitor every 30 minutes. Standard GitHub-hosted runners are free for public repositories.
- SQLite duplicate-detection state is restored/saved using GitHub Actions cache. Cache is best-effort and may be evicted; this is not a permanent database.
- No Render service or Supabase account is required.
- Leave `OPENAI_API_KEY` empty to reuse the source caption. This avoids OpenAI API charges; ChatGPT subscriptions do not include API credits.
- Instagram/Meta API access is subject to Meta account, permission, and policy requirements.

## Setup

1. Keep this repository public to use the free standard GitHub-hosted runner allowance. Do not put credentials in files or commits.
2. Open **Settings → Secrets and variables → Actions → New repository secret**.
3. Add these four required secrets:
   - `SOURCE_IG_USER_ID`
   - `SOURCE_ACCESS_TOKEN`
   - `DEST_IG_USER_ID`
   - `DEST_ACCESS_TOKEN`
4. Optional: add `OPENAI_API_KEY` if you want AI-generated captions (API usage may cost money).
5. Open **Actions → ReelPilot monitor → Run workflow** to test manually. The scheduled job runs every 30 minutes after GitHub Actions is enabled.

Both accounts must be eligible Instagram Professional accounts and authorized through a compatible Meta Instagram API product. A profile URL alone does not grant API access. The source account must be accessible to the authorized source token; the destination token must have content-publishing permission. Verify the current Meta permissions and media fields for your app before enabling unattended publishing.

## How it works

- `run_once.py` runs one monitoring pass from the scheduled workflow.
- The worker checks recent source media through Meta's official Graph API.
- Video/Reels media is considered; already-published media IDs are skipped.
- New items are submitted to the destination Instagram account through the Reels media-container and publish endpoints.
- Source IDs and statuses are stored in SQLite and carried between workflow runs using GitHub Actions cache.
- Failed items can be retried on a later run.
- `app.py` contains a small FastAPI dashboard for optional self-hosting, but the free GitHub Actions setup does **not** provide a continuously running web dashboard.

## Important limitations

- GitHub scheduled workflows are best-effort and can start late. The 30-minute schedule is not a guarantee of exact timing.
- GitHub Actions cache is not a transactional or permanent database and can be evicted. Check the Actions logs for failures and duplicate state.
- Reposting is only appropriate for content you own or have explicit permission to republish, including music and third-party footage.
- This workflow is configured for automatic publishing as requested. Test first with a controlled account before relying on unattended posting.
- Keep tokens and API keys in GitHub Actions secrets. Never paste them into chat, commit them, or print them in logs.

## Run locally

```bash
python -m venv .venv
# Windows PowerShell:
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Fill .env with credentials
python run_once.py
```

## Optional paid hosting

Render deployment files remain in this repository for a later paid always-on dashboard. They are not used by the free GitHub Actions workflow.
