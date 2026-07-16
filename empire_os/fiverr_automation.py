"""
Fiverr Automation — Playwright-based seller operations for Empire OS.

Uses `playwright.sync_api` for headless browser control.
Config-driven (credentials from env / config file, never hardcoded).
Logs to /tmp/fiverr_automation.log.
Hub integration via PREFIX = "/api/avenues/fiverr".
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

# ── Constants ───────────────────────────────────────────────────────────

PREFIX = "/api/avenues/fiverr"

LOG_PATH = "/tmp/fiverr_automation.log"
COOKIE_PATH = "/tmp/fiverr_cookies.json"

BASE_URL = "https://www.fiverr.com"
LOGIN_URL = f"{BASE_URL}/login"
SELLER_DASHBOARD_URL = f"{BASE_URL}/seller_dashboard"
MANAGE_ORDERS_URL = f"{BASE_URL}/users/%s/manage_orders"
MANAGE_GIGS_URL = f"{BASE_URL}/users/%s/manage_gigs"
CREATE_GIG_URL = f"{BASE_URL}/users/%s/manage_gigs/create"

DEFAULT_TIMEOUT_MS = 30_000  # 30 s

# ── Logging setup ───────────────────────────────────────────────────────

_log = logging.getLogger("fiverr_automation")
_log.setLevel(logging.DEBUG)
_fh = logging.FileHandler(LOG_PATH)
_fh.setLevel(logging.DEBUG)
_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
_fh.setFormatter(_fmt)
_log.addHandler(_fh)
# Also emit to stderr so container logs see it
_sh = logging.StreamHandler()
_sh.setLevel(logging.INFO)
_sh.setFormatter(_fmt)
_log.addHandler(_sh)


# ── Config ──────────────────────────────────────────────────────────────

DEFAULT_CONFIG: dict[str, Any] = {
    "username": "",
    "password": "",
    "require_2fa": False,
    "cookie_persistence": True,
    "headless": True,
    "slow_mo": 200,  # ms between actions (avoid rate-limiting)
}


def load_config(path: str | None = None) -> dict[str, Any]:
    """Load Fiverr config from env vars or an optional JSON file.

    Env vars (highest precedence):
      FIVERR_USERNAME
      FIVERR_PASSWORD
      FIVERR_REQUIRE_2FA   ("true"/"false")
      FIVERR_COOKIE_PERSISTENCE ("true"/"false")

    Config file (lower precedence):
      JSON dict with same keys as DEFAULT_CONFIG.
    """
    config = dict(DEFAULT_CONFIG)

    # File-based config
    if path:
        p = Path(path)
        if p.exists():
            try:
                data = json.loads(p.read_text())
                config.update(data)
                _log.info("Loaded config from %s", path)
            except Exception as exc:
                _log.warning("Failed to load config from %s: %s", path, exc)

    # Env overrides
    if os.environ.get("FIVERR_USERNAME"):
        config["username"] = os.environ["FIVERR_USERNAME"]
    if os.environ.get("FIVERR_PASSWORD"):
        config["password"] = os.environ["FIVERR_PASSWORD"]
    if os.environ.get("FIVERR_REQUIRE_2FA"):
        config["require_2fa"] = os.environ["FIVERR_REQUIRE_2FA"].lower() == "true"
    if os.environ.get("FIVERR_COOKIE_PERSISTENCE"):
        config["cookie_persistence"] = (
            os.environ["FIVERR_COOKIE_PERSISTENCE"].lower() == "true"
        )

    return config


# ── Helpers ──────────────────────────────────────────────────────────────


def _ok(data: Any = None) -> dict:
    return {"ok": True, "data": data}


def _err(msg: str, exc: Exception | None = None) -> dict:
    if exc:
        _log.error("%s: %s", msg, exc)
    else:
        _log.error(msg)
    return {"ok": False, "error": msg}


def _safe_filename(s: str) -> str:
    """Sanitise a string for use as a file/URL component."""
    return "".join(c if c.isalnum() or c in "._- " else "_" for c in s).strip()


# ── Login ────────────────────────────────────────────────────────────────


def login(
    page: "playwright.sync_api.Page",
    config: dict[str, Any],
    force: bool = False,
) -> bool:
    """Ensure the user is logged in on *page*.

    * If ``config["cookie_persistence"]`` is True and cookie file exists,
      loads cookies and checks the session is still valid (by visiting
      seller_dashboard).  Skips the login flow if valid.
    * Otherwise performs full username + password login, optionally
      waits for 2FA, and persists cookies.
    """
    from playwright.sync_api import TimeoutError as PWTimeout

    cookies_path = Path(COOKIE_PATH)

    # ── Try cookie restore ──────────────────────────────────────────
    if config.get("cookie_persistence") and cookies_path.exists() and not force:
        _log.info("Restoring session from %s", COOKIE_PATH)
        try:
            cookies = json.loads(cookies_path.read_text())
            page.context.add_cookies(cookies)
            page.goto(SELLER_DASHBOARD_URL, wait_until="domcontentloaded",
                      timeout=DEFAULT_TIMEOUT_MS)
            # If we land on the dashboard we're good; if redirected to
            # login page the session is dead.
            if SELLER_DASHBOARD_URL.rstrip("/") in page.url or \
               "seller_dashboard" in page.url or \
               "manage_" in page.url:
                _log.info("Cookie session is valid")
                return True
            _log.info("Cookie session expired – re-logging in")
        except Exception as exc:
            _log.warning("Cookie restore failed: %s – re-logging in", exc)

    # ── Full login ──────────────────────────────────────────────────
    _log.info("Starting login flow")
    try:
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
        # Wait for the login form to be present
        page.wait_for_selector(
            'input[name="identification_login"]',
            timeout=DEFAULT_TIMEOUT_MS,
        )
    except PWTimeout:
        _log.warning("Login page did not load the expected form field in time")
        # If already logged in (e.g. redirect), check dashboard
        page.goto(SELLER_DASHBOARD_URL, wait_until="domcontentloaded",
                  timeout=DEFAULT_TIMEOUT_MS)
        if "seller_dashboard" in page.url:
            _log.info("Already logged in (redirect from login page)")
            return True
        return False

    # Fill credentials
    login_field = page.locator('input[name="identification_login"]')
    login_field.fill(config.get("username", ""))
    page.wait_for_timeout(300)

    pw_field = page.locator('input[name="identification_password"]')
    pw_field.fill(config.get("password", ""))
    page.wait_for_timeout(300)

    # Click submit (Sign in button)
    submit_btn = page.locator('button[type="submit"]')
    if submit_btn.count() == 0:
        # Fallback: any button that says "Sign in"
        submit_btn = page.locator('button:has-text("Sign in")')
    submit_btn.click()
    _log.info("Login credentials submitted")

    # ── Wait for navigation ────────────────────────────────────────
    try:
        page.wait_for_url(
            lambda u: "seller_dashboard" in u or "manage_" in u or "/users/" in u,
            timeout=DEFAULT_TIMEOUT_MS,
        )
        _log.info("Login succeeded, landed on seller page")
    except PWTimeout:
        _log.info("Login did not immediately navigate – checking for 2FA or error")

    # ── 2FA handling ───────────────────────────────────────────────
    if config.get("require_2fa"):
        _log.info("2FA is enabled – waiting for 2FA code input")
        try:
            page.wait_for_selector(
                'input[name="code"], input[autocomplete="one-time-code"]',
                timeout=DEFAULT_TIMEOUT_MS,
            )
            _log.warning(
                "2FA code required but no automated method available. "
                "The caller should detect 'require_2fa_input' in the return "
                "and prompt the user, or set FIVERR_2FA_CODE and retry."
            )
            # The flow will pause here; the caller can re-call with
            # a 2FA code parameter.
            return False
        except PWTimeout:
            _log.info("No 2FA prompt appeared – continuing")

    # ── Persist cookies ────────────────────────────────────────────
    if config.get("cookie_persistence"):
        try:
            cookies = page.context.cookies()
            cookies_path.write_text(json.dumps(cookies, indent=2))
            _log.info("Cookies saved to %s (%d cookies)", COOKIE_PATH, len(cookies))
        except Exception as exc:
            _log.warning("Failed to persist cookies: %s", exc)

    return True


# ── Gig creation ────────────────────────────────────────────────────────


def _load_template(template_path: str) -> dict:
    """Load a gig template JSON file."""
    p = Path(template_path)
    if not p.exists():
        raise FileNotFoundError(f"Gig template not found: {template_path}")
    return json.loads(p.read_text())


def create_gig(
    template_path: str,
    overrides: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> dict:
    """Create a gig from a JSON template with optional override values.

    Template structure (JSON)::

        {
            "title": "I will ...",
            "category": "programming-tech",
            "subcategory": "web-development",
            "metadata": { ... },
            "description": "Gig description …",
            "packages": {
                "basic": {"name": "Basic", "price": 10, "description": "...", "delivery_time": 3},
                "standard": {"name": "Standard", "price": 30, "description": "...", "delivery_time": 5},
                "premium": {"name": "Premium", "price": 75, "description": "...", "delivery_time": 7}
            },
            "seo_tags": ["tag1", "tag2"],
            "requirements": [],
            "gallery": []
        }

    Returns dict with ``ok`` / ``error`` keys.
    """
    from playwright.sync_api import sync_playwright

    cfg = load_config() if config is None else dict(DEFAULT_CONFIG, **config)
    username = cfg.get("username", "")

    try:
        template = _load_template(template_path)
    except Exception as exc:
        return _err(f"Cannot load template: {exc}")

    # Merge overrides
    if overrides:
        for k, v in overrides.items():
            if k in ("packages",) and isinstance(v, dict):
                template.setdefault("packages", {}).update(v)
            else:
                template[k] = v

    title = template.get("title", "").strip() or "Untitled Gig"
    _log.info("Creating gig: %r", title)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=cfg.get("headless", True),
                slow_mo=cfg.get("slow_mo", 200),
            )
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = ctx.new_page()

            # Login
            if not login(page, cfg):
                return _err("Login failed – cannot create gig")

            # Navigate to create gig
            create_url = CREATE_GIG_URL.format(username)
            page.goto(create_url, wait_until="domcontentloaded",
                      timeout=DEFAULT_TIMEOUT_MS)

            # Wait for the form
            page.wait_for_timeout(2000)
            _log.info("On create-gig page: %s", page.url)

            # ── Fill title ─────────────────────────────────────────
            _log.info("Filling gig title")
            title_input = page.locator(
                'input[name="title"], '
                'input[aria-label*="title" i], '
                'input[placeholder*="title" i]'
            )
            if title_input.count() > 0:
                title_input.first.fill(title)
                page.wait_for_timeout(400)

            # ── Fill description ───────────────────────────────────
            description = template.get("description", "")
            if description:
                _log.info("Filling gig description")
                desc_area = page.locator(
                    'textarea[name="description"], '
                    'div[contenteditable="true"][aria-label*="description" i], '
                    'textarea[placeholder*="description" i]'
                )
                if desc_area.count() > 0:
                    desc_area.first.fill(description)
                    page.wait_for_timeout(400)

            # ── Package prices (basic / standard / premium) ────────
            packages = template.get("packages", {})
            for tier_name, tier_data in packages.items():
                _log.info("Setting %s package", tier_name)
                # Price inputs often have role="textbox" or name containing tier
                price_input = page.locator(
                    f'input[name*="{tier_name}" i][name*="price" i], '
                    f'input[aria-label*="{tier_name}" i][aria-label*="price" i]'
                )
                if price_input.count() > 0:
                    price_input.first.fill(str(tier_data.get("price", "")))
                    page.wait_for_timeout(300)

                delivery = tier_data.get("delivery_time")
                if delivery:
                    delivery_input = page.locator(
                        f'input[name*="{tier_name}" i][name*="delivery" i], '
                        f'input[aria-label*="{tier_name}" i][aria-label*="day" i]'
                    )
                    if delivery_input.count() > 0:
                        delivery_input.first.fill(str(delivery))
                        page.wait_for_timeout(300)

                desc = tier_data.get("description", "")
                if desc:
                    desc_input = page.locator(
                        f'textarea[name*="{tier_name}" i][name*="desc" i], '
                        f'textarea[aria-label*="{tier_name}" i]'
                    )
                    if desc_input.count() > 0:
                        desc_input.first.fill(desc)
                        page.wait_for_timeout(300)

            # ── SEO tags ───────────────────────────────────────────
            seo_tags = template.get("seo_tags", [])
            for tag in seo_tags:
                tag_input = page.locator(
                    'input[placeholder*="tag" i], '
                    'input[aria-label*="tag" i], '
                    'input[name*="tag" i]'
                )
                if tag_input.count() > 0:
                    tag_input.first.fill(tag)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(300)

            # ── Publish / Save as draft ────────────────────────────
            # Prefer "Save as Draft" for safety; the caller can publish
            # via a second call.
            save_btn = page.locator(
                'button:has-text("Save"), '
                'button:has-text("Save as Draft"), '
                'button:has-text("Publish")'
            )
            if save_btn.count() > 0:
                _log.info("Saving gig (as draft)")
                save_btn.first.click()
                page.wait_for_timeout(2000)
            else:
                _log.warning("No save/publish button found – form may have changed")

            browser.close()
            _log.info("Gig creation complete")
            return _ok({"title": title, "status": "draft"})

    except Exception as exc:
        return _err(f"Gig creation failed: {exc}")


# ── Order acceptance ────────────────────────────────────────────────────


def auto_accept_order(order_id: str, config: dict[str, Any] | None = None) -> dict:
    """Navigate to the orders page and accept an order matching ``order_id``.

    Looks for an order row / card containing the order ID and clicks its
    "Accept" button.
    """
    from playwright.sync_api import sync_playwright

    cfg = load_config() if config is None else dict(DEFAULT_CONFIG, **config)
    username = cfg.get("username", "")

    _log.info("Accepting order %s", order_id)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=cfg.get("headless", True),
                slow_mo=cfg.get("slow_mo", 200),
            )
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = ctx.new_page()

            if not login(page, cfg):
                return _err("Login failed – cannot accept order")

            orders_url = MANAGE_ORDERS_URL.format(username)
            page.goto(orders_url, wait_until="domcontentloaded",
                      timeout=DEFAULT_TIMEOUT_MS)
            page.wait_for_timeout(2000)

            # Try to find the order by ID
            order_locator = page.locator(
                f'[data-order-id="{order_id}"], '
                f'[href*="{order_id}"], '
                f'text="{order_id}"'
            ).first
            if order_locator.count() == 0:
                _log.warning("Order %s not found on orders page", order_id)
                browser.close()
                return _err(f"Order {order_id} not found")

            order_locator.click()
            page.wait_for_timeout(1500)

            # Click accept
            accept_btn = page.locator(
                'button:has-text("Accept"), '
                'button:has-text("Accept Order"), '
                'button[aria-label*="accept" i]'
            ).first
            if accept_btn.count() > 0:
                accept_btn.click()
                _log.info("Accepted order %s", order_id)
                page.wait_for_timeout(1000)
            else:
                _log.warning("No accept button found for order %s", order_id)

            browser.close()
            return _ok({"order_id": order_id, "accepted": True})

    except Exception as exc:
        return _err(f"Order acceptance failed: {exc}")


# ── Delivery ────────────────────────────────────────────────────────────


def auto_deliver(
    order_id: str,
    attachment_path: str,
    config: dict[str, Any] | None = None,
) -> dict:
    """Upload a file and mark the order as delivered.

    * Navigates to the order page.
    * Attaches the file at ``attachment_path``.
    * Clicks "Deliver Now" / "Submit".
    """
    from playwright.sync_api import sync_playwright

    cfg = load_config() if config is None else dict(DEFAULT_CONFIG, **config)
    username = cfg.get("username", "")

    _log.info("Delivering order %s with attachment %s", order_id, attachment_path)

    att_path = Path(attachment_path)
    if not att_path.exists():
        return _err(f"Attachment not found: {attachment_path}")

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=cfg.get("headless", True),
                slow_mo=cfg.get("slow_mo", 200),
            )
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = ctx.new_page()

            if not login(page, cfg):
                return _err("Login failed – cannot deliver order")

            order_url = f"{MANAGE_ORDERS_URL.format(username)}/{order_id}"
            page.goto(order_url, wait_until="domcontentloaded",
                      timeout=DEFAULT_TIMEOUT_MS)
            page.wait_for_timeout(2000)

            # ── File upload ────────────────────────────────────────
            _log.info("Uploading attachment for order %s", order_id)
            file_input = page.locator(
                'input[type="file"], '
                'input[accept*="zip"], '
                'input[accept*="pdf"], '
                'input[accept*="image"]'
            ).first
            if file_input.count() > 0:
                file_input.set_input_files(str(att_path.resolve()))
                _log.info("File set for upload")
                page.wait_for_timeout(2000)
            else:
                _log.warning(
                    "No file input found – trying drag-and-drop zone"
                )
                drop_zone = page.locator(
                    '[data-track-tag*="delivery"], '
                    'div:has-text("Drop files here"), '
                    '.file-upload-area, '
                    '[class*="upload"]'
                ).first
                if drop_zone.count() > 0:
                    drop_zone.click()
                    file_input = page.locator('input[type="file"]')
                    if file_input.count() > 0:
                        file_input.set_input_files(str(att_path.resolve()))
                        page.wait_for_timeout(2000)

            # ── Click deliver ──────────────────────────────────────
            deliver_btn = page.locator(
                'button:has-text("Deliver"), '
                'button:has-text("Deliver Now"), '
                'button:has-text("Submit"), '
                'button[aria-label*="deliver" i]'
            ).first
            if deliver_btn.count() > 0:
                deliver_btn.click()
                _log.info("Deliver button clicked for order %s", order_id)
                page.wait_for_timeout(2000)

                # Confirm any modal
                confirm_btn = page.locator(
                    'button:has-text("Yes"), '
                    'button:has-text("Confirm"), '
                    'button:has-text("Deliver")'
                ).first
                if confirm_btn.count() > 0:
                    confirm_btn.click()
                    page.wait_for_timeout(1500)
            else:
                _log.warning("No deliver button found for order %s", order_id)

            browser.close()
            return _ok({"order_id": order_id, "delivered": True})

    except Exception as exc:
        return _err(f"Delivery failed: {exc}")


# ── Messaging ───────────────────────────────────────────────────────────


def send_message(
    order_id: str,
    text: str,
    config: dict[str, Any] | None = None,
) -> dict:
    """Send a template-based message to the buyer for the given order.

    Navigates to the order page and types the message into the chat input.
    """
    from playwright.sync_api import sync_playwright

    cfg = load_config() if config is None else dict(DEFAULT_CONFIG, **config)
    username = cfg.get("username", "")

    _log.info("Sending message on order %s", order_id)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=cfg.get("headless", True),
                slow_mo=cfg.get("slow_mo", 200),
            )
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = ctx.new_page()

            if not login(page, cfg):
                return _err("Login failed – cannot send message")

            order_url = f"{MANAGE_ORDERS_URL.format(username)}/{order_id}"
            page.goto(order_url, wait_until="domcontentloaded",
                      timeout=DEFAULT_TIMEOUT_MS)
            page.wait_for_timeout(2000)

            # Find the chat / message input
            msg_input = page.locator(
                'textarea[placeholder*="message" i], '
                'div[contenteditable="true"][aria-label*="message" i], '
                'textarea[aria-label*="message" i], '
                'input[placeholder*="type" i]'
            ).first

            if msg_input.count() == 0:
                _log.warning("No message input found on order page %s", order_id)
                browser.close()
                return _err("Message input not found")

            msg_input.fill(text)
            page.wait_for_timeout(500)

            # Press Enter or click send
            send_btn = page.locator(
                'button[aria-label*="send" i], '
                'button:has(svg[data-track-tag*="send"]), '
                'button:has-text("Send")'
            ).first
            if send_btn.count() > 0:
                send_btn.click()
            else:
                page.keyboard.press("Enter")

            page.wait_for_timeout(1000)
            _log.info("Message sent on order %s", order_id)

            browser.close()
            return _ok({"order_id": order_id, "sent": True})

    except Exception as exc:
        return _err(f"Messaging failed: {exc}")


# ── Revenue stats ───────────────────────────────────────────────────────


def fetch_revenue(config: dict[str, Any] | None = None) -> dict:
    """Navigate to the seller dashboard / analytics and scrape revenue stats.

    Returns a dict with keys like ``total_revenue``, ``orders_completed``,
    ``active_orders``, and ``cancelled_orders`` if found.
    """
    from playwright.sync_api import sync_playwright

    cfg = load_config() if config is None else dict(DEFAULT_CONFIG, **config)
    username = cfg.get("username", "")

    _log.info("Fetching revenue stats")

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=cfg.get("headless", True),
                slow_mo=cfg.get("slow_mo", 200),
            )
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = ctx.new_page()

            if not login(page, cfg):
                return _err("Login failed – cannot fetch revenue")

            # Try seller dashboard first, then analytics
            page.goto(SELLER_DASHBOARD_URL, wait_until="domcontentloaded",
                      timeout=DEFAULT_TIMEOUT_MS)
            page.wait_for_timeout(2000)

            stats: dict[str, Any] = {}

            # Try dashboard numbers via common selectors
            for label in (
                "total_revenue",
                "orders_completed",
                "active_orders",
                "cancelled_orders",
            ):
                # Look for elements containing dollar amounts or counts
                elems = page.locator(
                    f'[data-test="{label}"], '
                    f'[class*="{label}"], '
                    f'[aria-label*="{label.replace("_", " ")}" i]'
                )
                if elems.count() > 0:
                    stats[label] = elems.first.text_content()
                    _log.info("%s: %s", label, stats[label])

            # Fallback: grab all numeric-looking text from the dashboard
            if not stats:
                _log.info("No structured revenue elements found – scraping page text")
                body_text = page.locator("body").text_content()
                # Simple heuristic: find "$X,XXX" patterns
                import re
                amounts = re.findall(r"\$\s?[\d,]+(?:\.\d{2})?", body_text)
                if amounts:
                    stats["found_amounts"] = amounts[:10]

            browser.close()
            return _ok(stats)

    except Exception as exc:
        return _err(f"Revenue fetch failed: {exc}")


# ── Convenience: full pipeline ──────────────────────────────────────────


def login_and_persist(config: dict[str, Any] | None = None) -> dict:
    """Pre-login and persist cookies without performing any operation.

    Useful for warming up the session in a container init step.
    """
    from playwright.sync_api import sync_playwright

    cfg = load_config() if config is None else dict(DEFAULT_CONFIG, **config)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=cfg.get("headless", True),
                slow_mo=cfg.get("slow_mo", 200),
            )
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = ctx.new_page()
            ok = login(page, cfg)
            browser.close()
            return _ok({"logged_in": ok}) if ok else _err("Login failed")
    except Exception as exc:
        return _err(f"Login-and-persist failed: {exc}")


# ── CLI entry point (for testing in container) ──────────────────────────


if __name__ == "__main__":
    import sys

    action = sys.argv[1] if len(sys.argv) > 1 else "help"

    if action == "login":
        result = login_and_persist()
    elif action == "create-gig":
        tmpl = sys.argv[2] if len(sys.argv) > 2 else "/etc/fiverr/templates/default.json"
        result = create_gig(tmpl)
    elif action == "accept":
        oid = sys.argv[2] if len(sys.argv) > 2 else ""
        result = auto_accept_order(oid)
    elif action == "deliver":
        oid = sys.argv[2] if len(sys.argv) > 2 else ""
        att = sys.argv[3] if len(sys.argv) > 3 else ""
        result = auto_deliver(oid, att)
    elif action == "message":
        oid = sys.argv[2] if len(sys.argv) > 2 else ""
        txt = sys.argv[3] if len(sys.argv) > 3 else "(empty)"
        result = send_message(oid, txt)
    elif action == "revenue":
        result = fetch_revenue()
    else:
        print(
            "Usage: python fiverr_automation.py <action> [args]\n\n"
            "Actions:\n"
            "  login                    Pre-login and persist cookies\n"
            "  create-gig <template>    Create a gig from JSON template\n"
            "  accept <order_id>        Accept order by ID\n"
            "  deliver <order_id> <file> Deliver order with attachment\n"
            "  message <order_id> <text> Send message to buyer\n"
            "  revenue                  Fetch revenue / order stats\n",
            file=sys.stderr,
        )
        sys.exit(1)

    print(json.dumps(result, indent=2, default=str))
