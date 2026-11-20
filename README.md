# ReelPilot AI

A small FastAPI service that checks one **authorized Instagram Professional account** every 30 minutes and can publish newly detected Reels to a second Instagram Professional account using Meta's official Instagram API.

Configured source profile: `https://www.instagram.com/aoonoww/`

## Important platform requirements

- Both source and destination accounts must be eligible Instagram Professional accounts and connected/configured with the required Meta app/API permissions.
- You must have permission to republish the source account's videos. This project does not scrape public profiles, bypass login, or download content through unofficial endpoints.
- Instagram API access is not granted merely by knowing a profile URL. You must obtain the account IDs and access tokens through Meta's supported authorization flow.
- The app uses the source account's Graph API `/{ig-user-id}/media` edge and the returned `media_url`. Availability of `media_url` and publishing permissions depends on the account type, API product, permissions, and Meta app review/configuration.
- Automatic publishing is powerful. Keep `AUTO_PUBLISH=true` only after testing with accounts you control. Set it to `false` to record items as pending instead.
- OpenAI API usage is billed separately. If `OPENAI_API_KEY` is blank, the original caption is used.

## Deploy on Render

1. Create a GitHub repository named `reelpilot-ai` and upload this project.
2. In Render, choose **New + → Blueprint**, connect the repository, and deploy `render.yaml`.
3. In the Render service's Environment settings, add the secret values from `.env.example`:
   - `SOURCE_IG_USER_ID`
   - `SOURCE_ACCESS_TOKEN`
   - `DEST_IG_USER_ID`
   - `DEST_ACCESS_TOKEN`
   - `OPENAI_API_KEY` (optional)
4. Confirm both Instagram accounts are authorized and the Meta app has the relevant read/publishing permissions.
5. Open the Render service URL. The dashboard shows recent processing activity.

## Run locally

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Fill .env with credentials
uvicorn app:app --reload
```

Open `http://127.0.0.1:8000`.

## Environment variables

See `.env.example`. Never put tokens or API keys in GitHub. Set secrets in Render's private environment-variable settings.

## Current implementation notes

- Checks the latest 25 media items every 30 minutes.
- Filters video media and, when supplied by Meta, `media_product_type=REELS`.
- Stores source media IDs in SQLite to avoid duplicate publishing.
- Creates a Reels media container and publishes it after Meta reports processing is finished.
- Dashboard includes status and error history.
- The scheduler runs inside the web process. Use a persistent always-on service; a sleeping/free web instance may miss checks. For production, move the scheduler into a dedicated worker and use managed persistent storage/database.
- Meta API versions and permissions can change; verify current requirements in Meta's developer documentation before deployment.

## Meta setup

Create/configure a Meta developer app and follow the current Instagram API documentation for the source and destination account types. Obtain separate authorized credentials for each account where required. Do not share access tokens in chat or commit them to the repository.

## Safety and compliance

Use only content you own or have explicit permission to republish. Respect music, third-party footage, creator rights, and Instagram's terms. This tool intentionally does not offer arbitrary-profile scraping.
