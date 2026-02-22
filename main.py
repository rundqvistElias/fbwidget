import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response

import facebook as fb

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL_PLACEHOLDER = "__BASE_URL__"
NO_CACHE_HEADERS = {"Cache-Control": "no-cache, no-store, must-revalidate"}

WIDGET_JS = Path(__file__).parent / "static" / "widget.js"
DEMO_HTML = Path(__file__).parent / "static" / "demo.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await fb.close_client()


app = FastAPI(title="fbwidget", lifespan=lifespan)

_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def demo_page(request: Request):
    base_url = str(request.base_url).rstrip("/")
    html = DEMO_HTML.read_text(encoding="utf-8").replace(BASE_URL_PLACEHOLDER, base_url)
    return HTMLResponse(html)


@app.get("/api/posts")
async def api_posts(
    limit: int = Query(5, ge=1, le=20),
):
    try:
        page_id = fb.get_page_id()
        page_info = await fb.get_page_info(page_id)
        posts = await fb.get_page_posts(page_id, limit=limit)
    except fb.RateLimitError as e:
        return JSONResponse({"error": str(e)}, status_code=429)
    except fb.PageNotFoundError as e:
        return JSONResponse({"error": str(e)}, status_code=404)
    except fb.ConfigurationError as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    except fb.TokenError as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    except fb.PermissionError as e:
        return JSONResponse({"error": str(e)}, status_code=403)
    except fb.FacebookAPIError as e:
        return JSONResponse({"error": str(e)}, status_code=502)
    except Exception as e:
        logger.exception("Unexpected error fetching posts")
        return JSONResponse({"error": str(e)}, status_code=500)

    return {"page": page_info, "posts": posts}


@app.get("/widget.js")
async def widget_js(request: Request):
    base_url = str(request.base_url).rstrip("/")
    widget_script = WIDGET_JS.read_text(encoding="utf-8").replace(BASE_URL_PLACEHOLDER, base_url)
    return Response(
        content=widget_script,
        media_type="application/javascript",
        headers=NO_CACHE_HEADERS,
    )
