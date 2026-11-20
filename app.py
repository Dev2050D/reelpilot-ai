import os, sqlite3, logging
from datetime import datetime, timezone
from contextlib import closing
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("reelpilot")

APP_NAME = "ReelPilot AI"
GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v27.0")
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
DB_PATH = os.getenv("DATABASE_PATH", "reelpilot.db")
SOURCE_IG_USER_ID = os.getenv("SOURCE_IG_USER_ID", "")
DEST_IG_USER_ID = os.getenv("DEST_IG_USER_ID", "")
SOURCE_ACCESS_TOKEN = os.getenv("SOURCE_ACCESS_TOKEN", "")
DEST_ACCESS_TOKEN = os.getenv("DEST_ACCESS_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "30"))
AUTO_PUBLISH = os.getenv("AUTO_PUBLISH", "true").lower() == "true"
SOURCE_PROFILE_URL = os.getenv("SOURCE_PROFILE_URL", "https://www.instagram.com/aoonoww/")

app = FastAPI(title=APP_NAME)
templates = Jinja2Templates(directory="templates")
scheduler = BackgroundScheduler(timezone="UTC")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with closing(db()) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS processed (
            source_media_id TEXT PRIMARY KEY,
            permalink TEXT,
            caption TEXT,
            status TEXT NOT NULL,
            destination_media_id TEXT,
            error TEXT,
            created_at TEXT NOT NULL
        )""")
        con.commit()

def graph_get(path, token, params=None):
    p = dict(params or {})
    p["access_token"] = token
    r = requests.get(f"{GRAPH}/{path.lstrip('/')}", params=p, timeout=45)
    r.raise_for_status()
    return r.json()

def graph_post(path, token, data):
    payload = dict(data)
    payload["access_token"] = token
    r = requests.post(f"{GRAPH}/{path.lstrip('/')}", data=payload, timeout=60)
    r.raise_for_status()
    return r.json()

def make_caption(original):
    fallback = (original or "").strip()
    if not OPENAI_API_KEY:
        return fallback[:2100]
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            input=(
                "Write an engaging Instagram Reels caption based on this source caption. "
                "Preserve factual meaning, do not invent claims, use a few relevant hashtags, "
                "and keep it under 2,000 characters. Return only the caption.\n\n"
                f"Source caption:\n{fallback}"
            ),
        )
        return response.output_text.strip()[:2100]
    except Exception:
        log.exception("AI caption generation failed; using original caption")
        return fallback[:2100]

def publish_reel(video_url, caption):
    if not DEST_IG_USER_ID or not DEST_ACCESS_TOKEN:
        raise RuntimeError("Destination Instagram credentials are not configured.")
    container = graph_post(f"{DEST_IG_USER_ID}/media", DEST_ACCESS_TOKEN, {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "share_to_feed": "true",
    })
    creation_id = container.get("id")
    if not creation_id:
        raise RuntimeError(f"Instagram did not return a creation container: {container}")
    # Wait for Meta's asynchronous video processing.
    import time
    for _ in range(30):
        status = graph_get(creation_id, DEST_ACCESS_TOKEN, {"fields": "status_code"})
        code = status.get("status_code")
        if code == "FINISHED":
            break
        if code == "ERROR":
            raise RuntimeError(f"Instagram video processing failed: {status}")
        time.sleep(10)
    else:
        raise RuntimeError("Instagram video processing timed out.")
    result = graph_post(f"{DEST_IG_USER_ID}/media_publish", DEST_ACCESS_TOKEN, {
        "creation_id": creation_id
    })
    return result.get("id", "")

def check_source():
    if not SOURCE_IG_USER_ID or not SOURCE_ACCESS_TOKEN:
        log.warning("Source Instagram credentials are not configured; monitor is idle.")
        return
    if not DEST_IG_USER_ID or not DEST_ACCESS_TOKEN:
        log.warning("Destination Instagram credentials are not configured; monitor is idle.")
        return
    try:
        data = graph_get(f"{SOURCE_IG_USER_ID}/media", SOURCE_ACCESS_TOKEN, {
            "fields": "id,caption,media_type,media_url,permalink,timestamp,media_product_type",
            "limit": 25
        })
        media_items = data.get("data", [])
        for item in reversed(media_items):
            media_id = item.get("id")
            if not media_id or item.get("media_type") != "VIDEO":
                continue
            # This workflow republishes only Reels, not ordinary feed videos.
            if item.get("media_product_type") not in (None, "REELS"):
                continue
            with closing(db()) as con:
                exists = con.execute(
                    "SELECT status FROM processed WHERE source_media_id=?", (media_id,)
                ).fetchone()
            # Retry prior failures; skip content already published or pending review.
            if exists and exists["status"] in ("published", "pending"):
                continue
            media_url = item.get("media_url")
            if not media_url:
                log.warning("No media_url returned for source item %s", media_id)
                continue
            caption = make_caption(item.get("caption", ""))
            try:
                if not AUTO_PUBLISH:
                    status, dest_id = "pending", None
                else:
                    dest_id = publish_reel(media_url, caption)
                    status = "published"
                with closing(db()) as con:
                    con.execute(
                        """INSERT INTO processed
                        (source_media_id, permalink, caption, status, destination_media_id, error, created_at)
                        VALUES (?, ?, ?, ?, ?, NULL, ?)
                        ON CONFLICT(source_media_id) DO UPDATE SET
                          permalink=excluded.permalink, caption=excluded.caption,
                          status=excluded.status, destination_media_id=excluded.destination_media_id,
                          error=NULL, created_at=excluded.created_at""",
                        (media_id, item.get("permalink"), caption, status, dest_id,
                         datetime.now(timezone.utc).isoformat())
                    )
                    con.commit()
                log.info("Processed source Reel %s: %s", media_id, status)
            except Exception as exc:
                log.exception("Failed to publish source Reel %s", media_id)
                with closing(db()) as con:
                    con.execute(
                        """INSERT INTO processed
                        (source_media_id, permalink, caption, status, error, created_at)
                        VALUES (?, ?, ?, 'failed', ?, ?)
                        ON CONFLICT(source_media_id) DO UPDATE SET
                          permalink=excluded.permalink, caption=excluded.caption,
                          status='failed', error=excluded.error, created_at=excluded.created_at""",
                        (media_id, item.get("permalink"), caption, str(exc)[:1000],
                         datetime.now(timezone.utc).isoformat())
                    )
                    con.commit()
    except Exception:
        log.exception("Source account check failed")

@app.on_event("startup")
def startup():
    init_db()
    scheduler.add_job(check_source, "interval", minutes=CHECK_INTERVAL_MINUTES,
                      id="source-monitor", max_instances=1, coalesce=True)
    scheduler.start()
    # First run shortly after startup.
    scheduler.add_job(check_source, "date", run_date=datetime.now(timezone.utc),
                      id="initial-check", replace_existing=True)

@app.on_event("shutdown")
def shutdown():
    if scheduler.running:
        scheduler.shutdown(wait=False)

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    with closing(db()) as con:
        rows = con.execute(
            "SELECT * FROM processed ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
    configured = all([SOURCE_IG_USER_ID, SOURCE_ACCESS_TOKEN, DEST_IG_USER_ID, DEST_ACCESS_TOKEN])
    return templates.TemplateResponse("index.html", {
        "request": request, "rows": rows, "configured": configured,
        "source_url": SOURCE_PROFILE_URL, "interval": CHECK_INTERVAL_MINUTES,
        "auto_publish": AUTO_PUBLISH
    })

@app.post("/check-now")
def check_now():
    check_source()
    return RedirectResponse("/", status_code=303)

@app.get("/health")
def health():
    return {"status": "ok", "service": APP_NAME}
