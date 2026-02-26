# fbwidget — How It Works

## Overview

A FastAPI server that serves an embeddable JavaScript widget. Add a `<script>` tag and a `<div>` placeholder to any website and it renders your Facebook page's recent posts as styled cards — no login required for visitors, no Facebook SDK, no iframes.

---

## File Structure

```
fbwidget/
├── main.py          # Entry point — FastAPI app, routes, auth, rate limiting
├── facebook.py      # Facebook Graph API client
├── static/
│   ├── widget.js    # The embeddable frontend widget
│   └── demo.html    # Demo + configurator page (served by GET /)
├── .env             # Secret config (never commit this)
├── .env.example     # Template for .env
└── requirements.txt
```

---

## Entry Point

The server starts with:

```bash
uvicorn main:app --reload --port 8000
```

`uvicorn` is the ASGI web server. It loads `main.py`, which defines the FastAPI `app`. `--reload` watches for file changes and restarts automatically during development.

---

## Configuration (`.env`)

```dotenv
FB_ACCESS_TOKEN=your_token_here   # Facebook User or Page Access Token (required)

# Security — set this in production:
API_KEYS=key1:yourdomain.com,key2:anotherdomain.com

# Optional:
CACHE_TTL_SECONDS=300             # How long to cache API responses (default: 300)
CORS_ORIGINS=*                    # Fallback CORS setting (only used if API_KEYS is not set)
```

These are loaded at startup via `python-dotenv`. The token is **never sent to the browser** — it lives only on the server.

> **Note:** When you update `.env`, touch any Python file to trigger a server reload, or restart uvicorn manually.

---

## Security — API Key System

The server supports two modes:

**Open development mode** (no `API_KEYS` set): Any origin can call `/api/posts`. Use this for local development only. A warning is logged at startup.

**Production mode** (`API_KEYS` is set): Every request to `/api/` must include a valid `X-Api-Key` header, and the key must match the request's `Origin` header. Requests that fail either check receive a `401` response.

### Setting up `API_KEYS`

The format is a comma-separated list of `key:domain` pairs:

```
API_KEYS=abc123:yourdomain.com,xyz789:anotherdomain.com
```

- Each key is tied to exactly one domain.
- The domain is compared against the bare netloc of the incoming `Origin` header (e.g. `yourdomain.com` or `localhost:5173`).
- Duplicate keys are rejected at startup with an error.
- Malformed entries raise an error with a descriptive message.

Generate a secure key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Add a new domain by appending to the env var and redeploying:
```
API_KEYS=existingkey:olddomain.com,newkey:newdomain.com
```

### How it works

1. `enforce_api_key` middleware runs on all `/api/` requests (OPTIONS preflights are bypassed).
2. It extracts the `X-Api-Key` header and the `Origin` (falling back to `Referer`).
3. The key is looked up in `_api_keys`. If unknown → 401.
4. The domain from the key entry is compared against the request origin. If mismatched → 401.
5. Matching requests pass through to the route handler.

### Middleware ordering

FastAPI/Starlette applies middleware in reverse registration order (LIFO). This project registers them so CORS is the **outermost** layer:

```
Browser request → CORSMiddleware → enforce_api_key → route handler
```

This ensures every response — including `401` rejections — carries CORS headers, so the browser sees the error body rather than a generic CORS failure.

### CORS origins

When `API_KEYS` is set, CORS is automatically locked to the registered domains. Local domains (`localhost`, `127.x.x.x`) get both `http://` and `https://` origins (browsers use plain http for localhost). Production domains are restricted to `https://` only.

When `API_KEYS` is not set, CORS falls back to the `CORS_ORIGINS` env var (default: `*`).

---

## Rate Limiting

All `/api/` requests are rate-limited to **60 requests per minute** using slowapi. The rate limit is keyed by API key when present, otherwise by client IP. This gives each client its own bucket rather than sharing a global counter.

Exceeding the limit returns HTTP `429`.

---

## Request Flow

```
Website visitor's browser
        │
        │  1. Browser loads widget.js (deferred, runs after DOM ready)
        ▼
  GET /widget.js  ──►  main.py
                            │  Reads static/widget.js from disk
                            │  Replaces __BASE_URL__ with the server's actual URL
                            │  Returns JavaScript
        │
        │  2. widget.js scans the page for <div class="fb-widget">
        │     - Reads data-page-id, data-limit, data-skin, data-api-key, etc.
        │     - Shows a loading spinner inside the div
        │
        │  3. For each div, widget fetches posts from our server
        ▼
  GET /api/posts?page_id=...  ──►  enforce_api_key middleware
                                          │  Validates X-Api-Key header
                                          │  Validates Origin matches key's domain
                                          ▼
                                    main.py  ──►  facebook.py
                                                        │
                                                        │  GET graph.facebook.com/v19.0/{page_id}
                                                        │    → page name, avatar picture
                                                        │
                                                        │  GET graph.facebook.com/v19.0/{page_id}/posts
                                                        │    → message, timestamp, image, link
                                                        │
                                                        ▼
                                                  Returns JSON to main.py
                                    │
                                    │  Caches response for CACHE_TTL_SECONDS
                                    │  Returns { page: {...}, posts: [...] } to browser
        │
        │  4. widget.js filters posts (skip/only keywords) then renders:
        │     - Header: page avatar + page name + Follow button
        │     - One card per post: avatar, name, timestamp, text, image, "View on Facebook"
        ▼
  Posts appear on screen
```

---

## Routes

### `GET /health`
Returns `{"status": "ok"}`. Used by Railway and other hosting platforms to check if the server is alive.

### `GET /`
The demo + configurator page. The server reads `static/demo.html`, replaces the `__BASE_URL__` placeholder with the actual server URL, and returns it. Includes a live preview widget and generates embed code based on selected options.

### `GET /widget.js`
Serves the JavaScript widget file. The server replaces `__BASE_URL__` in the JS with the actual server URL (e.g. `https://your-server.com`). This is how the widget knows where to send its API requests, regardless of where the server is hosted.

Cache header is set to `no-cache` so browsers always fetch the latest version. For production cache busting when deploying updates, use a `?v=` query param:
```html
<script src="https://your-server.com/widget.js?v=2" defer></script>
```

### `GET /api/posts?page_id=...&limit=5`
The JSON API. Called by the widget. `page_id` is required, `limit` is 1–20 (default: 5).

When `API_KEYS` is set, requires `X-Api-Key` header matching the request origin.

Responses are cached server-side for `CACHE_TTL_SECONDS` (default 5 minutes). The cache key is `(page_id, limit)`. Cached responses include a `Cache-Control: public, max-age=N` header reflecting the remaining TTL.

Returns:
```json
{
  "page": { "id": "...", "name": "...", "picture_url": "..." },
  "posts": [
    {
      "id": "...",
      "message": "...",
      "created_time": "2026-02-19T17:44:28+0000",
      "full_picture": "https://...",
      "permalink_url": "https://facebook.com/..."
    }
  ]
}
```

---

## `facebook.py` — The Graph API Client

This module handles all communication with Facebook's Graph API (`graph.facebook.com/v19.0`).

**Token** — `_get_access_token()` reads `FB_ACCESS_TOKEN` from the environment. Must have `pages_read_engagement` permission.

**HTTP client** — `_get_client()` returns a shared `httpx.AsyncClient` instance (lazy-created). Reuses the TCP connection across requests.

**Error mapping** — `_raise_for_api_error()` reads `error.code` from Facebook's response and raises typed Python exceptions. `main.py` catches these and maps them to HTTP status codes:

| Exception | HTTP status |
|---|---|
| `RateLimitError` | 429 |
| `PageNotFoundError` | 404 |
| `ConfigurationError` | 500 |
| `TokenError` | 500 |
| `PermissionError` | 403 |
| `FacebookAPIError` (generic) | 502 |

`TokenError` is raised by `_get_access_token()` when `FB_ACCESS_TOKEN` is missing.

**Post normalisation** — `_normalize_post()` maps raw Graph API fields to a clean dict. The `message` field falls back to `story` (used for shared posts and events that have no message text).

---

## `static/widget.js` — The Frontend Widget

The widget is a self-contained **IIFE** (Immediately Invoked Function Expression):

```js
(function () {
  // everything in here is isolated from the host page
})();
```

This means it does not pollute any global variables on the host page.

**On load, it:**
1. Waits for `DOMContentLoaded` (or runs immediately if DOM is already ready)
2. Injects a `<style>` tag with all widget CSS once per page (guarded by ID check)
3. Finds all `<div class="fb-widget">` elements on the page
4. For each div, reads its data attributes
5. Shows a loading spinner inside the div
6. Fetches `/api/posts` and renders the response as cards into the div

**Multiple widgets** on the same page just means multiple divs. Fetches are deduplicated: an in-flight fetch promise is stored in `fetchCache` keyed by `pageId:limit:apiKey`, so two widgets requesting the same page and limit share one HTTP request.

**DOM construction** — A `buildElement(tag, props, ...children)` helper creates and assembles DOM nodes. All user-supplied text is set via `textContent` (never `innerHTML`), which prevents XSS attacks without a separate escape function.

**Theming** — CSS custom properties (`--fbw-*`) define all colors. Three built-in skins:
- `light` — white cards on light grey background
- `dark` — dark background, muted borders
- `vivid` — indigo accent on light blue background

**Custom colors** — Three `data-color-*` attributes override individual CSS variables inline. `data-color-bg` also sets `--fbw-card` to a slightly lightened version of the background color (8% brighter per channel, capped at 255).

**Post filtering** — `data-skip-keywords` and `data-only-keywords` filter posts client-side after fetching. The server always returns `limit` posts; filtering happens in the browser.

**"See more" / "See less"** — Long texts are clamped to 4 lines with CSS (`-webkit-line-clamp`). A `setTimeout(0)` defers the height check until the element has layout. If clipped, a "See more" button appears; clicking it toggles expansion.

**Global API** — The widget exposes `window.fbwidget`:
```js
window.fbwidget.render(divElement);   // manually render a widget div
window.fbwidget.resetCache();         // clear in-flight fetch cache
```

---

## Token Lifecycle

For testing, use a short-lived **User Access Token** from the Graph API Explorer (expires ~1-2 hours).

For production, use a **never-expiring Page Access Token**:
1. In Graph API Explorer, switch the token dropdown from "User Token" to your page
2. Copy the page access token
3. Paste it into `.env` as `FB_ACCESS_TOKEN`

When the token expires the widget shows an error. Update `.env` and restart the server.

---

## How to Run

```bash
# First time setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your FB_ACCESS_TOKEN

# Start server
uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000` to see the demo and configurator.

---

## How to Embed

```html
<!-- Load once in your <head> -->
<script src="https://your-server.com/widget.js" defer></script>

<!-- Place anywhere in your page -->
<div
  class="fb-widget"
  data-page-id="your_page_id"
  data-limit="5"
  data-skin="light"
  data-api-key="your_api_key"
></div>
```

**Data attributes:**

| Attribute | Values | Default | Description |
|---|---|---|---|
| `data-page-id` | string | *(required)* | Facebook page ID or username |
| `data-limit` | 1–20 | `5` | Number of posts to fetch |
| `data-skin` | `light`, `dark`, `vivid` | `light` | Built-in color scheme |
| `data-api-key` | string | — | API key (required when server has `API_KEYS` set) |
| `data-skip-keywords` | comma-separated | — | Hide posts containing any of these words |
| `data-only-keywords` | comma-separated | — | Show only posts containing at least one of these words |
| `data-color-bg` | hex color e.g. `#1a1a2e` | — | Override background color |
| `data-color-text` | hex color | — | Override text color |
| `data-color-accent` | hex color | — | Override accent/button color |

Multiple widgets on the same page:
```html
<div class="fb-widget" data-page-id="page1" data-limit="3" data-skin="light"></div>
<div class="fb-widget" data-page-id="page2" data-limit="5" data-skin="dark"></div>
```
