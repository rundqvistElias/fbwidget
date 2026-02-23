import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response

import facebook as fb

load_dotenv(override=True)

CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "300"))
_cache: dict[tuple[str, int], tuple[float, dict]] = {}  # (page_id, limit) -> (expiry, payload)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL_PLACEHOLDER = "__BASE_URL__"
NO_CACHE_HEADERS = {"Cache-Control": "no-cache, no-store, must-revalidate"}

WIDGET_JS = Path(__file__).parent / "static" / "widget.js"
DEMO_HTML = Path(__file__).parent / "static" / "demo.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    fb.validate_config()
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


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def demo_page(request: Request):
    base_url = str(request.base_url).rstrip("/")
    html = DEMO_HTML.read_text(encoding="utf-8").replace(BASE_URL_PLACEHOLDER, base_url)
    return HTMLResponse(html)


def _check_origin(request: Request) -> JSONResponse | None:
    """Return a 403 if the request origin isn't in the allowed list, else None.

    Skipped entirely when CORS_ORIGINS=* (development / permissive mode).
    Checks the Origin header first; falls back to Referer for clients that
    omit Origin on same-origin or navigational requests.
    """
    if "*" in _cors_origins:
        return None

    origin = request.headers.get("origin")

    if not origin:
        referer = request.headers.get("referer", "")
        parsed = urlparse(referer)
        if parsed.scheme and parsed.netloc:
            origin = f"{parsed.scheme}://{parsed.netloc}"

    if origin and origin.rstrip("/") in _cors_origins:
        return None

    logger.warning("Blocked request with origin: %s", origin or "(none)")
    return JSONResponse({"error": "Origin not allowed"}, status_code=403)


@app.get("/api/posts")
async def api_posts(
    request: Request,
    limit: int = Query(5, ge=1, le=20),
    page_id: str = Query(...),
):
    blocked = _check_origin(request)
    if blocked:
        return blocked

    cached = _cache.get((page_id, limit))
    if cached:
        expiry, payload = cached
        remaining = int(expiry - time.monotonic())
        if remaining > 0:
            return JSONResponse(payload, headers={"Cache-Control": f"public, max-age={remaining}"})

    try:
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

    payload = {"page": page_info, "posts": posts}
    _cache[(page_id, limit)] = (time.monotonic() + CACHE_TTL, payload)
    return JSONResponse(payload, headers={"Cache-Control": f"public, max-age={CACHE_TTL}"})


@app.get("/widget.js")
async def widget_js(request: Request):
    base_url = str(request.base_url).rstrip("/")
    widget_script = WIDGET_JS.read_text(encoding="utf-8").replace(BASE_URL_PLACEHOLDER, base_url)
    return Response(
        content=widget_script,
        media_type="application/javascript",
        headers=NO_CACHE_HEADERS,
    )
