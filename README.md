# fbwidget

Embed your Facebook page's recent posts on any website — no login required for visitors, no Facebook SDK, no iframes.

Add a `<script>` tag and a `<div>` to your page. The widget fetches posts through your own server (so your Facebook access token stays private) and renders them as styled cards.

---

## Quick start

```bash
# 1. Clone and install
git clone https://github.com/yourname/fbwidget.git
cd fbwidget
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env and set FB_ACCESS_TOKEN

# 3. Run
uvicorn main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000) to see the live demo and embed code generator.

---

## Getting a Facebook access token

1. Go to [Meta for Developers](https://developers.facebook.com/) and open **Graph API Explorer**
2. Select your app and set the token type to your **Page**
3. Add the `pages_read_engagement` permission
4. Copy the token into `.env` as `FB_ACCESS_TOKEN`

For production, use a **Page Access Token** — it never expires. User tokens expire in ~1–2 hours.

---

## Embedding the widget

Add this to your `<head>`:

```html
<script src="https://your-server.com/widget.js" defer></script>
```

Then place this wherever you want the widget to appear:

```html
<div
  class="fb-widget"
  data-page-id="your_page_id"
  data-limit="5"
  data-skin="light"
></div>
```

Replace `your-server.com` with your deployed server URL and `your_page_id` with your Facebook page ID or username.

### All data attributes

| Attribute | Values | Default | Description |
|---|---|---|---|
| `data-page-id` | string | *(required)* | Facebook page ID or username |
| `data-limit` | 1–20 | `5` | Number of posts to show |
| `data-skin` | `light`, `dark`, `vivid` | `light` | Color scheme |
| `data-api-key` | string | — | Required in production (see below) |
| `data-skip-keywords` | comma-separated | — | Hide posts that contain any of these words |
| `data-only-keywords` | comma-separated | — | Show only posts containing at least one of these words |
| `data-color-bg` | hex e.g. `#1a1a2e` | — | Override background color |
| `data-color-text` | hex | — | Override text color |
| `data-color-accent` | hex | — | Override button/accent color |

### Multiple widgets on one page

```html
<div class="fb-widget" data-page-id="page1" data-skin="light"></div>
<div class="fb-widget" data-page-id="page2" data-skin="dark"></div>
```

---

## Production setup

### Securing the API with keys

Without `API_KEYS` set, any website can call your `/api/posts` endpoint. For production, restrict access by domain:

```dotenv
API_KEYS=key1:yourdomain.com,key2:anotherdomain.com
```

Generate a secure key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Each key is locked to exactly one domain. Requests from other origins are rejected with 401.

Then pass the key in your embed:

```html
<div
  class="fb-widget"
  data-page-id="your_page_id"
  data-api-key="key1"
></div>
```

### Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `FB_ACCESS_TOKEN` | Yes | — | Facebook Page Access Token |
| `API_KEYS` | No | — | Comma-separated `key:domain` pairs |
| `CACHE_TTL_SECONDS` | No | `300` | How long to cache API responses |
| `CORS_ORIGINS` | No | `*` | Fallback CORS origins (only used if `API_KEYS` is not set) |

---

## Deploying

The server is a standard Python ASGI app. It works on any platform that supports Python:

- **Railway** — connect your repo, set env vars, deploy
- **Render** — create a Web Service, set start command to `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Fly.io** — `fly launch` and `fly secrets set FB_ACCESS_TOKEN=...`

The `/health` route returns `{"status": "ok"}` for platform health checks.

---

## Cache busting

The widget script is served with `no-cache` headers. To force browsers to reload after an update:

```html
<script src="https://your-server.com/widget.js?v=2" defer></script>
```

---

## JavaScript API

The widget exposes a small global API for advanced use:

```js
window.fbwidget.render(divElement);  // manually render a widget div
window.fbwidget.resetCache();        // clear in-flight fetch deduplication cache
```
