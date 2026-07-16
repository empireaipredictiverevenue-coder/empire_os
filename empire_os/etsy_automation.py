"""
Etsy Automation — Empire OS avenue for Etsy Open API v3.

Uses the Etsy Open API v3 REST API with OAuth2 token-based auth.
Handles listing creation, image upload, inventory sync, order management,
shop sections, and revenue reporting.

Config is loaded from env vars:
  ETSY_CLIENT_ID        — OAuth2 client ID
  ETSY_CLIENT_SECRET    — OAuth2 client secret
  ETSY_REFRESH_TOKEN    — OAuth2 refresh token (for token refresh flow)
  ETSY_API_KEY          — Legacy API key (required for some endpoints)
  ETSY_SHOP_ID          — Default shop ID to operate on
  ETSY_RATE_LIMIT       — Max calls/second (default 10)

Logs to /tmp/etsy_automation.log
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

import requests

# ── Logging ───────────────────────────────────────────────────────────
LOG_PATH = "/tmp/etsy_automation.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("etsy_automation")

# ── Hub prefix for avenue registration ───────────────────────────────
PREFIX = "/api/avenues/etsy"

# ── Constants ─────────────────────────────────────────────────────────
_BASE_URL = "https://openapi.etsy.com/v3"

# ── Config ────────────────────────────────────────────────────────────


def _load_config() -> dict:
    """Load Etsy API config from environment variables.

    Returns a dict with keys:
        client_id, client_secret, refresh_token, api_key, shop_id, rate_limit
    """
    return {
        "client_id": os.environ.get("ETSY_CLIENT_ID", ""),
        "client_secret": os.environ.get("ETSY_CLIENT_SECRET", ""),
        "refresh_token": os.environ.get("ETSY_REFRESH_TOKEN", ""),
        "api_key": os.environ.get("ETSY_API_KEY", ""),
        "shop_id": os.environ.get("ETSY_SHOP_ID", ""),
        "rate_limit": float(os.environ.get("ETSY_RATE_LIMIT", "10")),
    }


CONFIG = _load_config()

# ── In-memory token store ────────────────────────────────────────────
_token: dict = {}
_last_request_ts: float = 0.0


# ══════════════════════════════════════════════════════════════════════
# Core API Wrapper
# ══════════════════════════════════════════════════════════════════════


def _rate_limit_wait() -> None:
    """Enforce max calls/second from config.

    Sleeps if we've hit the rate ceiling since the last call.
    """
    global _last_request_ts
    rate = CONFIG.get("rate_limit", 10)
    if rate <= 0:
        return
    elapsed = time.monotonic() - _last_request_ts
    min_interval = 1.0 / rate
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _last_request_ts = time.monotonic()


def _get_auth_headers() -> dict[str, str]:
    """Build auth headers from current token state.

    Uses Bearer token if available, otherwise falls back to api_key header.
    """
    headers = {
        "x-api-key": CONFIG.get("api_key", ""),
        "Accept": "application/json",
    }
    token = _token.get("access_token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def refresh_auth() -> dict:
    """Refresh the OAuth token using the configured refresh_token.

    Calls Etsy's token endpoint with a refresh grant.
    Stores the new access_token (+ new refresh_token if provided) in
    the module-level _token dict.

    Returns:
        dict with keys: success (bool), data (token dict on success), error (str)
    """
    global _token
    client_id = CONFIG.get("client_id", "")
    client_secret = CONFIG.get("client_secret", "")
    refresh_token = CONFIG.get("refresh_token", "")

    if not client_id or not refresh_token:
        msg = "Missing ETSY_CLIENT_ID or ETSY_REFRESH_TOKEN"
        logger.error(msg)
        return {"success": False, "data": None, "error": msg}

    token_url = "https://api.etsy.com/v3/public/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
    }
    if client_secret:
        payload["client_secret"] = client_secret

    try:
        logger.info("Refreshing OAuth token...")
        resp = requests.post(token_url, data=payload, timeout=15)
        if resp.status_code == 200:
            body = resp.json()
            _token = {
                "access_token": body.get("access_token", ""),
                "refresh_token": body.get("refresh_token", refresh_token),
                "expires_in": body.get("expires_in", 3600),
                "token_type": body.get("token_type", "Bearer"),
                "acquired_at": time.time(),
            }
            logger.info("Token refreshed successfully (expires in %ds)", _token["expires_in"])
            return {"success": True, "data": dict(_token), "error": None}
        else:
            msg = f"Token refresh failed: HTTP {resp.status_code} {resp.text[:300]}"
            logger.error(msg)
            return {"success": False, "data": None, "error": msg}
    except requests.RequestException as e:
        msg = f"Token refresh request failed: {e}"
        logger.error(msg)
        return {"success": False, "data": None, "error": msg}


def _ensure_token() -> None:
    """Ensure we have a valid access token, refreshing if needed/possible."""
    if not _token.get("access_token"):
        refresh_auth()
        return

    # Check expiry (with 60s buffer)
    acquired = _token.get("acquired_at", 0)
    expires_in = _token.get("expires_in", 3600)
    if time.time() > acquired + expires_in - 60:
        refresh_auth()


def etsy_request(
    method: str,
    path: str,
    params: Optional[dict] = None,
    data: Optional[dict] = None,
    max_retries: int = 3,
) -> dict:
    """Generic wrapper around Etsy API calls.

    Handles:
        - Auth headers (with auto-refresh on 401)
        - Rate limiting (10 calls/sec default)
        - Retry with backoff on 5xx
        - Structured return with success/data/error keys

    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        path: Path relative to base URL (e.g. '/application/listings')
        params: Optional query-string params
        data: Optional request body (sent as JSON for non-GET)
        max_retries: Max retries on 5xx errors (default 3)

    Returns:
        dict: {success: bool, data: Any, error: str|None}
    """
    # Ensure we have a valid token before making the request
    _ensure_token()

    url = _BASE_URL.rstrip("/") + "/" + path.lstrip("/")
    headers = _get_auth_headers()

    for attempt in range(1, max_retries + 2):  # attempt 1..max_retries+1
        _rate_limit_wait()

        try:
            if method.upper() == "GET":
                resp = requests.get(url, headers=headers, params=params, timeout=30)
            elif method.upper() == "DELETE":
                resp = requests.delete(url, headers=headers, params=params, timeout=30)
            else:
                headers["Content-Type"] = "application/json"
                if params:
                    url = url + "?" + urllib.parse.urlencode(params, doseq=True)
                resp = requests.request(
                    method.upper(),
                    url,
                    headers=headers,
                    json=data,
                    timeout=30,
                )

        except requests.RequestException as e:
            logger.warning("Request error (attempt %d/%d): %s", attempt, max_retries + 1, e)
            if attempt <= max_retries:
                time.sleep(2 ** attempt)
                continue
            return {"success": False, "data": None, "error": str(e)}

        # ── 401 — Token expired; refresh and retry once ──────────
        if resp.status_code == 401:
            logger.info("Got 401, refreshing token and retrying...")
            ref_result = refresh_auth()
            if ref_result["success"]:
                headers = _get_auth_headers()
                continue
            else:
                return {"success": False, "data": None, "error": "Auth failed after refresh attempt"}

        # ── 429 — Rate limited; backoff and retry ────────────────
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 2 ** attempt))
            logger.warning("Rate limited (429). Waiting %ds...", retry_after)
            time.sleep(retry_after)
            continue

        # ── 5xx — Server error; retry with exponential backoff ───
        if 500 <= resp.status_code < 600:
            logger.warning("Server error %d (attempt %d/%d)", resp.status_code, attempt, max_retries + 1)
            if attempt <= max_retries:
                time.sleep(2 ** attempt)
                continue
            return {
                "success": False,
                "data": None,
                "error": f"Etsy API server error: HTTP {resp.status_code}",
            }

        # ── 2xx / 4xx (non-401/429) — parse and return ───────────
        try:
            body = resp.json() if resp.status_code != 204 and resp.text else None
        except (json.JSONDecodeError, ValueError):
            body = resp.text

        if 200 <= resp.status_code < 300:
            return {"success": True, "data": body, "error": None}
        else:
            # 4xx other than 401/429
            error_detail = body if body else resp.text
            return {
                "success": False,
                "data": None,
                "error": f"Etsy API error HTTP {resp.status_code}: {error_detail}",
            }

    # Shouldn't reach here, but just in case
    return {"success": False, "data": None, "error": "Max retries exceeded"}


# ══════════════════════════════════════════════════════════════════════
# Templates
# ══════════════════════════════════════════════════════════════════════


def default_listing_template(**overrides: Any) -> dict:
    """Return a default listing template with sensible defaults.

    All values can be overridden via keyword args.

    Returns a dict suitable for the create_listing body:
        title, description, price, quantity, tags, materials,
        shipping_profile_id, shop_section_id, who_made, when_made,
        taxonomy_id, listing_type, state
    """
    template = {
        "title": "Handcrafted Item — Customize Yours Today!",
        "description": (
            "A beautiful handcrafted item made with care. "
            "Each piece is unique and made to order. "
            "Please allow 3-5 business days for production "
            "before shipping.\n\n"
            "**Customization:**\n"
            "Feel free to message me with any custom requests!\n\n"
            "**Care Instructions:**\n"
            "Handle with care. Store in a cool, dry place."
        ),
        "price": 29.99,
        "quantity": 1,
        "tags": [
            "handcrafted",
            "gift",
            "unique",
            "custom",
            "handmade",
            "artisan",
            "decor",
            "personalized",
            "gift-idea",
            "present",
        ],
        "materials": [
            "cotton",
            "thread",
        ],
        "shipping_profile_id": None,
        "shop_section_id": None,
        "who_made": "i_did",
        "when_made": "made_to_order",
        "taxonomy_id": 1,  # Fallback; user should set a real taxonomy_id
        "listing_type": "physical",
        "state": "draft",  # Use 'active' to publish immediately
    }
    template.update(overrides)
    return template


# ══════════════════════════════════════════════════════════════════════
# Capabilities: Listings
# ══════════════════════════════════════════════════════════════════════


def create_listing(
    template_path: Optional[str] = None,
    overrides: Optional[dict] = None,
) -> dict:
    """Create a new Etsy listing via POST /v3/application/listings.

    If template_path is provided, loads the listing template from a JSON
    file and merges overrides on top. Otherwise uses default_listing_template().

    Args:
        template_path: Optional path to a JSON template file
        overrides: Optional dict of field overrides

    Returns:
        dict with success/data/error keys. On success, data is the
        created listing object.
    """
    # Build the template
    if template_path:
        try:
            with open(template_path, "r") as f:
                template = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            return {"success": False, "data": None, "error": f"Failed to load template: {e}"}
    else:
        template = default_listing_template()

    # Merge overrides
    if overrides:
        template.update(overrides)

    # Build the request payload per Etsy API v3 spec
    payload = {
        "title": template.get("title", ""),
        "description": template.get("description", ""),
        "price": template.get("price", 0),
        "quantity": template.get("quantity", 1),
        "who_made": template.get("who_made", "i_did"),
        "when_made": template.get("when_made", "made_to_order"),
        "taxonomy_id": template.get("taxonomy_id", 1),
        "type": template.get("listing_type", "physical"),
        "state": template.get("state", "draft"),
    }

    # Optional fields
    tags = template.get("tags")
    if tags:
        payload["tags"] = tags

    materials = template.get("materials")
    if materials:
        payload["materials"] = materials

    shipping_profile_id = template.get("shipping_profile_id")
    if shipping_profile_id is not None:
        payload["shipping_profile_id"] = shipping_profile_id

    shop_section_id = template.get("shop_section_id")
    if shop_section_id is not None:
        payload["shop_section_id"] = shop_section_id

    logger.info(
        "Creating listing: title=%r price=%s qty=%s",
        payload.get("title", "")[:60],
        payload.get("price"),
        payload.get("quantity"),
    )
    return etsy_request("POST", "/application/listings", data=payload)


def upload_image(listing_id: int, image_path: str, rank: int = 1) -> dict:
    """Upload an image to a listing via POST /v3/application/listings/{id}/images.

    Users the multipart/form-data upload endpoint. The image is read from
    disk and sent as file data.

    Args:
        listing_id: The numeric listing ID
        image_path: Path to the image file on disk (JPEG, PNG, GIF)
        rank: Display order (1 = primary, default 1)

    Returns:
        dict with success/data/error keys
    """
    img_path = Path(image_path)
    if not img_path.is_file():
        return {"success": False, "data": None, "error": f"Image not found: {image_path}"}

    url = f"{_BASE_URL}/application/listings/{listing_id}/images"
    headers = _get_auth_headers()
    # Remove Content-Type so requests sets it for multipart
    headers.pop("Content-Type", None)

    _rate_limit_wait()

    try:
        with open(img_path, "rb") as f:
            files = {"image": (img_path.name, f, "image/jpeg")}
            resp = requests.post(
                url,
                headers=headers,
                files=files,
                data={"rank": rank},
                timeout=60,
            )
    except requests.RequestException as e:
        logger.error("Image upload request failed: %s", e)
        return {"success": False, "data": None, "error": str(e)}

    # Handle auth errors for upload (refresh and retry once)
    if resp.status_code == 401:
        ref_result = refresh_auth()
        if ref_result["success"]:
            headers = _get_auth_headers()
            headers.pop("Content-Type", None)
            try:
                with open(img_path, "rb") as f:
                    files = {"image": (img_path.name, f, "image/jpeg")}
                    resp = requests.post(
                        url,
                        headers=headers,
                        files=files,
                        data={"rank": rank},
                        timeout=60,
                    )
            except requests.RequestException as e:
                return {"success": False, "data": None, "error": str(e)}
        else:
            return {"success": False, "data": None, "error": "Auth failed during image upload"}

    try:
        body = resp.json() if resp.text else None
    except (json.JSONDecodeError, ValueError):
        body = resp.text

    if 200 <= resp.status_code < 300:
        logger.info("Image uploaded to listing %d (rank %d)", listing_id, rank)
        return {"success": True, "data": body, "error": None}
    else:
        return {
            "success": False,
            "data": None,
            "error": f"Image upload failed HTTP {resp.status_code}: {body}",
        }


def update_inventory(listing_id: int, products: list[dict]) -> dict:
    """Update listing inventory (stock, variations) via PUT.

    PUT /v3/application/listings/{listing_id}/inventory

    Args:
        listing_id: The numeric listing ID
        products: List of product dicts per Etsy API spec, each with:
            - sku (str)
            - property_values (list[dict])
            - offerings (list[dict] with price, quantity, is_enabled)

    Returns:
        dict with success/data/error keys
    """
    payload = {"products": products}
    logger.info(
        "Updating inventory for listing %d (%d products)",
        listing_id,
        len(products),
    )
    return etsy_request(
        "PUT",
        f"/application/listings/{listing_id}/inventory",
        data=payload,
    )


# ══════════════════════════════════════════════════════════════════════
# Capabilities: Orders (Receipts)
# ══════════════════════════════════════════════════════════════════════


def list_orders(
    status: str = "open",
    shop_id: Optional[str] = None,
    limit: int = 25,
    offset: int = 0,
) -> dict:
    """List shop receipts (orders).

    GET /v3/application/shops/{shop_id}/receipts

    Args:
        status: Receipt status filter — 'open' (default), 'completed', 'all'
        shop_id: Shop ID (defaults to ETSY_SHOP_ID from config)
        limit: Max results per page (max 100)
        offset: Pagination offset

    Returns:
        dict with success/data/error keys. On success, data contains
        the receipts list and pagination info.
    """
    shop = shop_id or CONFIG.get("shop_id", "")
    if not shop:
        return {"success": False, "data": None, "error": "No shop_id configured (ETSY_SHOP_ID)"}

    params = {
        "limit": min(limit, 100),
        "offset": offset,
    }
    if status and status != "all":
        params["was_paid"] = "true" if status == "paid" else None
        params["was_shipped"] = "true" if status == "shipped" else None

    logger.info("Listing orders for shop %s (status=%s)", shop, status)
    return etsy_request("GET", f"/application/shops/{shop}/receipts", params=params)


def fulfill_order(
    receipt_id: int,
    tracking_code: str,
    carrier: str,
    shop_id: Optional[str] = None,
) -> dict:
    """Mark a receipt as shipped with tracking info.

    POST /v3/application/shops/{shop_id}/receipts/{receipt_id}/tracking

    Args:
        receipt_id: The receipt (order) ID
        tracking_code: Carrier tracking number
        carrier: Carrier name (e.g. 'usps', 'fedex', 'ups', 'other')
        shop_id: Shop ID (defaults to ETSY_SHOP_ID from config)

    Returns:
        dict with success/data/error keys
    """
    shop = shop_id or CONFIG.get("shop_id", "")
    if not shop:
        return {"success": False, "data": None, "error": "No shop_id configured (ETSY_SHOP_ID)"}

    payload = {
        "tracking_code": tracking_code,
        "carrier_name": carrier,
    }

    logger.info(
        "Fulfilling receipt %d via %s (tracking: %s)",
        receipt_id,
        carrier,
        tracking_code,
    )
    return etsy_request(
        "POST",
        f"/application/shops/{shop}/receipts/{receipt_id}/tracking",
        data=payload,
    )


# ══════════════════════════════════════════════════════════════════════
# Capabilities: Shop Sections
# ══════════════════════════════════════════════════════════════════════


def list_shop_sections(shop_id: Optional[str] = None) -> dict:
    """List all sections for a shop.

    GET /v3/application/shops/{shop_id}/sections

    Args:
        shop_id: Shop ID (defaults to ETSY_SHOP_ID from config)

    Returns:
        dict with success/data/error keys
    """
    shop = shop_id or CONFIG.get("shop_id", "")
    if not shop:
        return {"success": False, "data": None, "error": "No shop_id configured (ETSY_SHOP_ID)"}

    return etsy_request("GET", f"/application/shops/{shop}/sections")


def create_shop_section(title: str, shop_id: Optional[str] = None) -> dict:
    """Create a new shop section.

    POST /v3/application/shops/{shop_id}/sections

    Args:
        title: Section display name
        shop_id: Shop ID (defaults to ETSY_SHOP_ID from config)

    Returns:
        dict with success/data/error keys
    """
    shop = shop_id or CONFIG.get("shop_id", "")
    if not shop:
        return {"success": False, "data": None, "error": "No shop_id configured (ETSY_SHOP_ID)"}

    payload = {"title": title}
    logger.info("Creating shop section: %r", title)
    return etsy_request("POST", f"/application/shops/{shop}/sections", data=payload)


def update_shop_section(
    section_id: int,
    title: str,
    shop_id: Optional[str] = None,
) -> dict:
    """Update an existing shop section's title.

    PUT /v3/application/shops/{shop_id}/sections/{section_id}

    Args:
        section_id: The section ID to update
        title: New section title
        shop_id: Shop ID (defaults to ETSY_SHOP_ID from config)

    Returns:
        dict with success/data/error keys
    """
    shop = shop_id or CONFIG.get("shop_id", "")
    if not shop:
        return {"success": False, "data": None, "error": "No shop_id configured (ETSY_SHOP_ID)"}

    payload = {"title": title}
    logger.info("Updating shop section %d → %r", section_id, title)
    return etsy_request(
        "PUT",
        f"/application/shops/{shop}/sections/{section_id}",
        data=payload,
    )


def delete_shop_section(section_id: int, shop_id: Optional[str] = None) -> dict:
    """Delete a shop section.

    DELETE /v3/application/shops/{shop_id}/sections/{section_id}

    Args:
        section_id: The section ID to delete
        shop_id: Shop ID (defaults to ETSY_SHOP_ID from config)

    Returns:
        dict with success/data/error keys
    """
    shop = shop_id or CONFIG.get("shop_id", "")
    if not shop:
        return {"success": False, "data": None, "error": "No shop_id configured (ETSY_SHOP_ID)"}

    logger.info("Deleting shop section %d", section_id)
    return etsy_request(
        "DELETE",
        f"/application/shops/{shop}/sections/{section_id}",
    )


# ══════════════════════════════════════════════════════════════════════
# Capabilities: Revenue / Payments
# ══════════════════════════════════════════════════════════════════════


def get_revenue(
    date_range: Optional[tuple[str, str]] = None,
    shop_id: Optional[str] = None,
) -> dict:
    """Fetch revenue data from shop transactions.

    GET /v3/application/shops/{shop_id}/transactions

    Generates a revenue summary including:
        - total transaction count
        - gross revenue
        - net revenue (after fees & tax)
        - breakdown by date if a range is provided

    Args:
        date_range: Optional (start_date, end_date) as ISO-8601 strings
        shop_id: Shop ID (defaults to ETSY_SHOP_ID from config)

    Returns:
        dict with success/data/error keys. Data contains transaction list
        and a computed summary dict.
    """
    shop = shop_id or CONFIG.get("shop_id", "")
    if not shop:
        return {"success": False, "data": None, "error": "No shop_id configured (ETSY_SHOP_ID)"}

    params: dict[str, Any] = {"limit": 100}
    if date_range:
        params["min_created"] = date_range[0]
        params["max_created"] = date_range[1]

    logger.info("Fetching revenue data for shop %s (range: %s)", shop, date_range)

    result = etsy_request("GET", f"/application/shops/{shop}/transactions", params=params)
    if not result["success"]:
        return result

    transactions = result["data"]
    if isinstance(transactions, dict):
        transactions = transactions.get("results", [])

    # Compute summary
    gross = sum(
        float(t.get("price", {}).get("amount", 0) if isinstance(t.get("price"), dict) else t.get("price", 0))
        * t.get("quantity", 1)
        for t in transactions
    )
    total_qty = sum(t.get("quantity", 1) for t in transactions)

    # Etsy fee estimation (6.5% transaction fee + 0.45 payment processing)
    estimated_fees = gross * 0.065 + total_qty * 0.45
    net_revenue = gross - estimated_fees

    summary = {
        "transaction_count": len(transactions),
        "total_quantity": total_qty,
        "gross_revenue": round(gross, 2),
        "estimated_fees": round(estimated_fees, 2),
        "net_revenue": round(net_revenue, 2),
        "currency": "USD",
        "date_range": date_range,
    }

    return {
        "success": True,
        "data": {
            "transactions": transactions,
            "summary": summary,
        },
        "error": None,
    }


# ══════════════════════════════════════════════════════════════════════
# Utility: Quick sanity / health check
# ══════════════════════════════════════════════════════════════════════


def ping() -> dict:
    """Quick health check — fetches the authenticated user's shop list.

    GET /v3/application/shops

    Returns success if the API key and token are valid.
    """
    logger.info("Ping: checking API connectivity...")
    result = etsy_request("GET", "/application/shops", params={"limit": 1})
    if result["success"]:
        logger.info("Ping OK — Etsy API is reachable")
    else:
        logger.warning("Ping FAILED: %s", result.get("error"))
    return result


# ══════════════════════════════════════════════════════════════════════
# Quick test (when run directly)
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "ping":
        result = ping()
        print(json.dumps(result, indent=2, default=str))
    else:
        print("Etsy Automation Module — Empire OS Avenue")
        print(f"  Prefix: {PREFIX}")
        print(f"  Log: {LOG_PATH}")
        print(f"  Config loaded: client_id={'set' if CONFIG.get('client_id') else 'MISSING'}")
        print(f"  Config loaded: api_key={'set' if CONFIG.get('api_key') else 'MISSING'}")
        print(f"  Config loaded: shop_id={'set' if CONFIG.get('shop_id') else 'MISSING'}")
        print(f"  Config loaded: refresh_token={'set' if CONFIG.get('refresh_token') else 'MISSING'}")
        print()
        print("Run `python3 etsy_automation.py ping` to test connectivity.")
