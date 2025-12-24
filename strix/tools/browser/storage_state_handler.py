import json
import logging
from pathlib import Path

from playwright.async_api import BrowserContext

logger = logging.getLogger(__name__)


class StorageStateHandler:
    """Handle storage state import/export with auto-format detection"""

    @staticmethod
    def _normalize_cookie(cookie: dict) -> dict:
        """Normalize cookie to Playwright format"""
        normalized = {
            "name": cookie.get("name", ""),
            "value": cookie.get("value", ""),
            "domain": cookie.get("domain", ""),
            "path": cookie.get("path", "/"),
            "httpOnly": cookie.get("httpOnly", False),
            "secure": cookie.get("secure", False),
        }

        # Handle expiration date (different field names in different formats)
        expires = cookie.get("expires", cookie.get("expirationDate", -1))
        if isinstance(expires, str) and expires.isdigit():
            expires = int(expires)
        elif isinstance(expires, float):
            expires = int(expires)
        normalized["expires"] = expires if expires != 0 else -1

        # Handle sameSite (case normalization and common aliases)
        same_site = cookie.get("sameSite")
        if isinstance(same_site, str):
            normalized_same_site = same_site.strip().lower()
            if not normalized_same_site:
                normalized["sameSite"] = "Lax"
            else:
                same_site_map = {
                    "lax": "Lax",
                    "strict": "Strict",
                    "none": "None",
                    "no_restriction": "None",
                    "unspecified": "Lax",
                }
                normalized["sameSite"] = same_site_map.get(
                    normalized_same_site, same_site.capitalize()
                )
        else:
            normalized["sameSite"] = "Lax"

        return normalized

    @staticmethod
    def _detect_format(data: dict | list) -> str:
        """
        Detect cookie file format

        Returns:
            - "playwright": Playwright storage_state format
            - "cookie_array": Cookie-Editor/EditThisCookie array format
            - "unknown": Unknown format
        """
        # Check if it's already Playwright format
        if isinstance(data, dict):
            if "cookies" in data and isinstance(data.get("cookies"), list):
                logger.info("Detected format: Playwright storage_state")
                return "playwright"

        # Check if it's a cookie array (Cookie-Editor, EditThisCookie, etc.)
        if isinstance(data, list):
            if len(data) > 0 and isinstance(data[0], dict):
                # Check for cookie fields
                first_item = data[0]
                if "name" in first_item and "value" in first_item:
                    logger.info("Detected format: Cookie array (Cookie-Editor/EditThisCookie)")
                    return "cookie_array"

        logger.warning("Unknown cookie format")
        return "unknown"

    @staticmethod
    def _convert_cookie_array_to_playwright(cookies: list) -> dict:
        """Convert cookie array format to Playwright format"""
        normalized_cookies = [
            StorageStateHandler._normalize_cookie(cookie)
            for cookie in cookies
        ]

        return {
            "cookies": normalized_cookies,
            "origins": []
        }

    @staticmethod
    def _auto_convert_to_playwright(data: dict | list) -> dict:
        """Auto-detect format and convert to Playwright format"""
        format_type = StorageStateHandler._detect_format(data)

        if format_type == "playwright":
            # Already in Playwright format, just normalize cookies
            normalized_cookies = [
                StorageStateHandler._normalize_cookie(cookie)
                for cookie in data.get("cookies", [])
            ]
            return {
                "cookies": normalized_cookies,
                "origins": data.get("origins", [])
            }

        elif format_type == "cookie_array":
            # Convert from cookie array to Playwright format
            logger.info("Converting cookie array to Playwright format...")
            return StorageStateHandler._convert_cookie_array_to_playwright(data)

        else:
            raise ValueError(
                "Unsupported cookie format. Supported formats:\n"
                "  - Playwright storage_state (native)\n"
                "  - Cookie-Editor JSON export\n"
                "  - EditThisCookie JSON export\n"
                "  - JSON array of cookies"
            )

    @staticmethod
    async def load_storage_state(state_path: str) -> dict:
        """
        Read and auto-convert storage state file

        Supports multiple formats:
        - Playwright storage_state format (native)
        - Cookie-Editor JSON export
        - EditThisCookie JSON export
        - Generic cookie array JSON
        """
        path = Path(state_path)

        if not path.exists():
            raise FileNotFoundError(f"Storage state file not found: {state_path}")

        logger.info(f"Loading storage state from: {state_path}")

        try:
            with open(path) as f:
                raw_data = json.load(f)

            # Auto-detect and convert to Playwright format
            state = StorageStateHandler._auto_convert_to_playwright(raw_data)

            cookies_count = len(state.get("cookies", []))
            origins_count = len(state.get("origins", []))

            logger.info(
                f"Loaded storage state: {cookies_count} cookies, {origins_count} origins"
            )

            return state

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in storage state file: {e}")
            raise RuntimeError(f"Storage state file is not valid JSON: {e}") from e
        except Exception as e:
            logger.error(f"Failed to load storage state: {e}")
            raise RuntimeError(f"Storage state load failed: {e}") from e

    @staticmethod
    async def save_storage_state(context: BrowserContext, state_path: str) -> None:
        """Export storage state to file"""
        logger.info(f"Saving storage state to: {state_path}")

        try:
            # Playwright's storage_state() returns dict containing cookies and origins
            await context.storage_state(path=state_path)

            # Read and verify
            with open(state_path) as f:
                state = json.load(f)

            cookies_count = len(state.get("cookies", []))
            logger.info(f"Saved storage state with {cookies_count} cookies")

        except Exception as e:
            logger.error(f"Failed to save storage state: {e}")
            raise RuntimeError(f"Storage state save failed: {e}") from e
