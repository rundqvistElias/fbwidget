# fbwidget — How It Works

## Overview

A FastAPI server that serves an embeddable JavaScript widget. Add a `<script>` tag and a `<div>` placeholder to any website and it renders your Facebook page's recent posts as styled cards — no login required for visitors, no Facebook SDK, no iframes.

---

## File Structure

```
fbwidget/
├── main.py          # Entry point — FastAPI app, routes
├── facebook.py      # Facebook Graph API client
├── static/
│   └── widget.js    # The embeddable frontend widget
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
FB_ACCESS_TOKEN=your_token_here   # Facebook User or Page Access Token
FB_PAGE_ID=your_page_id_here      # Numeric ID of your Facebook page
CORS_ORIGINS=*                    # Which domains can embed the widget
```

These are loaded at startup via `python-dotenv`. The token is **never sent to the browser** — it lives only on the server.

> **Note:** When you update `.env`, touch any Python file to trigger a server reload, or restart uvicorn manually.

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
        │     - Reads data-limit and data-theme from each div
        │     - Shows a loading spinner inside the div
        │
        │  3. For each div, widget fetches posts from our server
        ▼
  GET /api/posts  ──►  main.py  ──►  facebook.py
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
                            │  Returns { page: {...}, posts: [...] } to browser
        │
        │  4. widget.js renders into the div:
        │     - Header: page avatar + page name + Follow button
        │     - One card per post: avatar, name, timestamp, text, image, "View on Facebook"
        ▼
  Posts appear on screen
```

---

## The Three Routes

### `GET /`
A demo page showing a live embed and the embed code snippet. The server URL and page ID are injected dynamically — nothing is hardcoded.

### `GET /widget.js`
Serves the JavaScript widget file. Before returning it, the server replaces the placeholder `__BASE_URL__` in the JS with the actual server URL (e.g. `http://localhost:8000`). This is how the widget knows where to send its API request, regardless of where the server is hosted.

Cache header is set to `no-cache` during development. For production, set it to `public, max-age=300` and use a `?v=` query param for cache busting when deploying updates:
```html
<script src="https://your-server.com/widget.js?v=2" defer></script>
```

### `GET /api/posts?limit=5`
The JSON API. Called by the widget. Reads `FB_PAGE_ID` from `.env` and does two Graph API calls:
1. Page info (name, profile picture)
2. Recent posts

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

**Token** — `_token()` reads `FB_ACCESS_TOKEN` from the environment. Must have `pages_read_engagement` permission.

**Page ID** — `get_page_id()` reads `FB_PAGE_ID` from the environment.

**HTTP client** — Uses a shared `httpx.AsyncClient` instance (lazy-created, async). Reuses the TCP connection across requests.

**Error mapping** — `_check_error()` reads `error.code` from Facebook's response and raises typed Python exceptions (`RateLimitError`, `PageNotFoundError`, `TokenError`, `PermissionError`). `main.py` catches these and maps them to HTTP status codes (429, 404, 500, 403).

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
4. For each div, reads `data-limit` and `data-theme` attributes
5. Shows a loading spinner inside the div
6. Fetches `/api/posts` and renders the response as cards into the div

**Removing the div** removes the widget — the script renders into whatever divs exist at load time.

**Multiple widgets** on the same page just means multiple divs — the script loads once and handles all of them.

**CSS** uses custom properties (`--fbw-*`) for theming. `fbw-light` and `fbw-dark` classes define the theme variables, all components inherit them automatically.

**All text** is passed through `escapeHtml()` before being inserted into the DOM — prevents XSS attacks.

**"See more"** — Long texts are clamped to 4 lines with CSS (`-webkit-line-clamp`). A `setTimeout(0)` defers the height check until the element has layout. If clipped, a "See more" button appears.

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
# Edit .env with your token and page ID

# Start server
uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000` to see the demo.

---

## How to Embed

```html
<!-- Load once in your <head> -->
<script src="https://your-server.com/widget.js" defer></script>

<!-- Place anywhere in your page -->
<div class="fb-widget" data-limit="5" data-theme="light"></div>
```

**Data attributes:**
- `data-limit` — Number of posts to show, 1–20 (default: 5)
- `data-theme` — `light` or `dark` (default: light)

Multiple widgets on the same page:
```html
<div class="fb-widget" data-limit="3" data-theme="light"></div>
<div class="fb-widget" data-limit="5" data-theme="dark"></div>
```
