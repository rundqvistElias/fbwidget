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
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

import facebook as fb

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))
BASE_URL_PLACEHOLDER = "__BASE_URL__"
NO_CACHE_HEADERS = {"Cache-Control": "no-cache, no-store, must-revalidate"}
WIDGET_JS_PATH = Path(__file__).parent / "static" / "widget.js"
DEMO_HTML_PATH = Path(__file__).parent / "static" / "demo.html"

_posts_cache: dict[tuple[str, int], tuple[float, dict]] = {}

# ── API key configuration ─────────────────────────────────────────────────────
#
# Set API_KEYS in your Railway environment variables:
#
#   API_KEYS=key1:yourdomain.com,key2:anotherdomain.com
#
# Each entry is <api-key>:<domain>. The domain is compared against the
# bare netloc of the incoming Origin header (e.g. "yourdomain.com" or
# "localhost:5173").
#
# Generate a secure key:
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
#
# Add a new domain by appending to the env var and redeploying:
#   API_KEYS=existingkey:olddomain.com,newkey:newdomain.com
#
# If API_KEYS is not set the server runs in open development mode.


def _parse_api_keys() -> dict[str, str] | None:
    """Parse API_KEYS env var. Returns None if not set, raising on bad format."""
    raw = os.getenv("API_KEYS")
    if not raw or not raw.strip():
        return None

    result: dict[str, str] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue

        parts = entry.split(":", 1)
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            raise ValueError(
                f"Wrong input: {entry!r}, input should be 'key1:domain1.com'"
            )

        result[parts[0].strip()] = parts[1].strip().lower()

    if not result:
        raise ValueError("API_KEYS is set but contains no valid entries")

    return result


def _is_local_domain(domain: str) -> bool:
    return domain.startswith("localhost") or domain.startswith("127.")


def _cors_origins_for_domain(domain: str) -> list[str]:
    """Return allowed CORS origin URLs for a registered domain.

    Local domains get both http and https because browsers use plain http
    for localhost. Production domains are restricted to https only.
    """
    if _is_local_domain(domain):
        return [f"http://{domain}", f"https://{domain}"]
    return [f"https://{domain}"]


_api_keys: dict[str, str] | None = _parse_api_keys()


# ── CORS origins ──────────────────────────────────────────────────────────────


def _build_cors_origins() -> list[str]:
    if _api_keys:
        origins: list[str] = []
        for domain in _api_keys.values():
            origins.extend(_cors_origins_for_domain(domain))
        return origins
    return [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]


_cors_origins = _build_cors_origins()


# ── Rate limiter ───────────────────────────────────────────────────────────────
# Keyed by API key when present so each client has its own bucket, not a shared IP bucket.


def _identify_requester(request: Request) -> str:
    api_key = request.headers.get("x-api-key")
    if api_key:
        return f"key:{api_key}"
    client_ip = request.client.host if request.client else "unknown"
    return f"ip:{client_ip}"


limiter = Limiter(key_func=_identify_requester)


# ── App ────────────────────────────────────────────────────────────────────────


def _log_startup_config() -> None:
    if _api_keys:
        logger.info("API key auth enabled for %d domain(s):", len(_api_keys))
        for domain in _api_keys.values():
            logger.info(
                "  → %s  (origins: %s)", domain, _cors_origins_for_domain(domain)
            )
    else:
        logger.warning(
            "API_KEYS not set — running in open development mode (no key required)"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    fb.validate_config()
    _log_startup_config()
    yield
    await fb.close_client()


app = FastAPI(title="fbwidget", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]


# ── Auth middleware ────────────────────────────────────────────────────────────
# Registered BEFORE CORSMiddleware so CORS becomes the outermost layer.
# This ensures every response — including 401s — carries CORS headers,
# and OPTIONS preflight requests reach CORSMiddleware unobstructed.


def _extract_request_origin(request: Request) -> str:
    """Return the bare netloc (host or host:port) from the Origin header."""
    origin_header = request.headers.get("origin", "")
    if not origin_header:
        return ""
    return urlparse(origin_header).netloc.lower()


def _validate_api_key(request: Request) -> JSONResponse | None:
    """Return a 401 response if the request fails key validation, else None."""
    if _api_keys is None:
        return None

    api_key = request.headers.get("x-api-key", "")
    request_origin = _extract_request_origin(request)

    if not api_key:
        logger.warning(
            "Auth rejected — missing X-Api-Key header (origin: %s)", request_origin
        )
        return JSONResponse({"error": "Missing X-Api-Key header"}, status_code=401)

    allowed_domain = _api_keys.get(api_key)
    if not allowed_domain:
        logger.warning(
            "Auth rejected — unknown key: %s… (origin: %s)", api_key[:8], request_origin
        )
        return JSONResponse({"error": "Invalid API key"}, status_code=401)

    if request_origin and request_origin != allowed_domain:
        logger.warning(
            "Auth rejected — origin mismatch: key=%s… expected=%s got=%s",
            api_key[:8],
            allowed_domain,
            request_origin,
        )
        return JSONResponse({"error": "Origin does not match API key"}, status_code=401)

    return None


@app.middleware("http")
async def enforce_api_key(request: Request, call_next):
    is_api_request = request.url.path.startswith("/api/")
    is_preflight = request.method == "OPTIONS"
    auth_enabled = bool(_api_keys)

    if not is_api_request or is_preflight or not auth_enabled:
        return await call_next(request)

    rejection = _validate_api_key(request)
    if rejection:
        return rejection

    return await call_next(request)


# CORSMiddleware added AFTER auth so it wraps auth as the outermost layer.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ── Routes ─────────────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def demo_page(request: Request):
    base_url = str(request.base_url).rstrip("/")
    html = DEMO_HTML_PATH.read_text(encoding="utf-8").replace(
        BASE_URL_PLACEHOLDER, base_url
    )
    return HTMLResponse(html)


@app.get("/widget.js")
async def widget_js(request: Request):
    base_url = str(request.base_url).rstrip("/")
    script = WIDGET_JS_PATH.read_text(encoding="utf-8").replace(
        BASE_URL_PLACEHOLDER, base_url
    )
    return Response(
        content=script, media_type="application/javascript", headers=NO_CACHE_HEADERS
    )


def _get_cached_posts(page_id: str, limit: int) -> JSONResponse | None:
    """Return a cached response if one exists and has not yet expired."""
    entry = _posts_cache.get((page_id, limit))
    if not entry:
        return None
    expiry, payload = entry
    remaining_seconds = int(expiry - time.monotonic())
    if remaining_seconds <= 0:
        return None
    return JSONResponse(
        payload, headers={"Cache-Control": f"public, max-age={remaining_seconds}"}
    )


@app.get("/api/posts")
@limiter.limit("60/minute")
async def api_posts(
    request: Request,
    page_id: str = Query(...),
    limit: int = Query(5, ge=1, le=20),
):
    cached = _get_cached_posts(page_id, limit)
    if cached:
        return cached

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
    except Exception:
        logger.exception("Unexpected error fetching posts for page_id=%s", page_id)
        return JSONResponse({"error": "Internal server error"}, status_code=500)

    payload = {"page": page_info, "posts": posts}
    _posts_cache[(page_id, limit)] = (time.monotonic() + CACHE_TTL_SECONDS, payload)
    return JSONResponse(
        payload, headers={"Cache-Control": f"public, max-age={CACHE_TTL_SECONDS}"}
    )
