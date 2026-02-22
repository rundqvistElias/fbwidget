import logging
import os

import httpx

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"

_RATE_LIMIT_CODES = frozenset({4, 17, 32, 613})
_PERMISSION_CODES = frozenset({10, *range(200, 300)})

_client: httpx.AsyncClient | None = None


class FacebookAPIError(Exception):
    pass


class ConfigurationError(FacebookAPIError):
    pass


class RateLimitError(FacebookAPIError):
    pass


class PageNotFoundError(FacebookAPIError):
    pass


class TokenError(FacebookAPIError):
    pass


class PermissionError(FacebookAPIError):
    pass


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=10.0)
    return _client


async def close_client() -> None:
    global _client
    if _client:
        await _client.aclose()
        _client = None


def _get_access_token() -> str:
    token = os.getenv("FB_ACCESS_TOKEN", "").strip()
    if not token:
        raise TokenError("FB_ACCESS_TOKEN not set in .env")
    return token


def get_page_id() -> str:
    page_id = os.getenv("FB_PAGE_ID", "").strip()
    if not page_id:
        raise ConfigurationError("FB_PAGE_ID not set in .env")
    return page_id


def _raise_for_api_error(data: dict) -> None:
    err = data.get("error")
    if not err:
        return
    code = err.get("code", 0)
    msg = err.get("message", "Unknown Facebook API error")
    if code in _RATE_LIMIT_CODES:
        raise RateLimitError(msg)
    if code == 100:
        raise PageNotFoundError(msg)
    if code == 190:
        raise TokenError(msg)
    if code in _PERMISSION_CODES:
        raise PermissionError(msg)
    raise FacebookAPIError(msg)


def _normalize_post(item: dict) -> dict:
    return {
        "id": item.get("id", ""),
        "message": item.get("message") or item.get("story") or "",
        "created_time": item.get("created_time", ""),
        "full_picture": item.get("full_picture"),
        "permalink_url": item.get("permalink_url", ""),
    }


async def get_page_info(page_id: str) -> dict:
    logger.info("FB get_page_info: page_id=%s", page_id)
    resp = await _get_client().get(
        f"{GRAPH_API_BASE}/{page_id}",
        params={"fields": "id,name,picture.type(normal)", "access_token": _get_access_token()},
    )
    data = resp.json()
    _raise_for_api_error(data)
    return {
        "id": data["id"],
        "name": data.get("name", ""),
        "picture_url": data.get("picture", {}).get("data", {}).get("url", ""),
    }


async def get_page_posts(page_id: str, limit: int = 5) -> list[dict]:
    logger.info("FB get_page_posts: page_id=%s limit=%s", page_id, limit)
    resp = await _get_client().get(
        f"{GRAPH_API_BASE}/{page_id}/posts",
        params={
            "fields": "message,story,created_time,full_picture,permalink_url",
            "limit": limit,
            "access_token": _get_access_token(),
        },
    )
    data = resp.json()
    _raise_for_api_error(data)
    return [_normalize_post(item) for item in data.get("data", [])]
