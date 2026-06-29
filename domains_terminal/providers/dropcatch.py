"""DropCatch API provider for domain-agent.

Wraps the DropCatch v2 REST API. Handles OAuth2 authentication with
auto-refresh and maps API responses to domain-agent's Domain model.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from domains_terminal.models import Domain
from domains_terminal.storage import Storage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
API_BASE = "https://api.dropcatch.com"
CONFIG_DIR = Path.home() / ".config" / "domains-terminal"
TOKEN_FILE = CONFIG_DIR / "token.json"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_PAGE_SIZE = 50

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DropCatchError(Exception):
    """Base exception for DropCatch provider errors."""


class AuthenticationError(DropCatchError):
    """Raised when API authentication fails."""


class ApiError(DropCatchError):
    """Raised when the API returns an unexpected status code."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Config / token helpers  (shared file format with dropcatch-cli)
# ---------------------------------------------------------------------------


def _ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _load_config() -> Dict[str, str]:
    _ensure_config_dir()
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def _save_config(cfg: Dict[str, str]) -> None:
    _ensure_config_dir()
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def _load_token() -> Optional[Dict[str, Any]]:
    _ensure_config_dir()
    if TOKEN_FILE.exists():
        return json.loads(TOKEN_FILE.read_text())
    return None


def _save_token(token: Dict[str, Any]) -> None:
    _ensure_config_dir()
    TOKEN_FILE.write_text(json.dumps(token, indent=2))


def _token_is_valid(token: Optional[Dict[str, Any]]) -> bool:
    if not token:
        return False
    expires_at = token.get("expires_at", 0)
    return bool(expires_at) and time.time() < expires_at - 60


def _resolve_credentials(
    client_id: Optional[str], client_secret: Optional[str]
) -> tuple[str, str]:
    """Resolve API credentials from params, config file, or env vars.

    Raises AuthenticationError if none are found.
    """
    cfg = _load_config()
    cid = (
        client_id
        or cfg.get("client_id")
        or os.environ.get("DROPCATCH_CLIENT_ID")
        or os.environ.get("DROPCATCH_CLIENTID")
    )
    secret = (
        client_secret
        or cfg.get("client_secret")
        or os.environ.get("DROPCATCH_CLIENT_SECRET")
        or os.environ.get("DROPCATCH_CLIENTSECRET")
    )
    if not cid or not secret:
        raise AuthenticationError(
            "DropCatch credentials not found. Pass client_id/client_secret, "
            "set DROPCATCH_CLIENT_ID / DROPCATCH_CLIENT_SECRET env vars, "
            "or run auth() to generate a config file."
        )
    return cid, secret


# ---------------------------------------------------------------------------
# Low-level HTTP client (internal)
# ---------------------------------------------------------------------------


class _DropCatchAPI:
    """Minimal HTTP client for the DropCatch v2 REST API.

    Handles token injection, 401 re-auth, and response parsing.
    """

    def __init__(self, base: str = API_BASE):
        self.base = base

    # -- Auth -----------------------------------------------------------------

    @staticmethod
    def auth(
        client_id: str, client_secret: str
    ) -> Dict[str, Any]:
        """Authenticate with DropCatch and persist the bearer token."""
        logger.info("Authenticating with DropCatch API ...")
        try:
            resp = requests.post(
                f"{API_BASE}/Authorize",
                json={"ClientId": client_id, "ClientSecret": client_secret},
                timeout=30,
            )
        except requests.ConnectionError as exc:
            raise ApiError(
                f"Network failure — could not reach {API_BASE}: {exc}"
            ) from exc
        except requests.Timeout as exc:
            raise ApiError(
                "Auth request timed out after 30s."
            ) from exc

        if resp.status_code != 200:
            raise AuthenticationError(
                f"Auth failed ({resp.status_code}): {resp.text[:500]}"
            )

        try:
            data = resp.json()
        except json.JSONDecodeError as exc:
            raise ApiError(
                f"Invalid JSON from auth endpoint: {exc}\nBody: {resp.text[:1000]}"
            ) from exc

        if "access_token" not in data:
            detail = (
                data.get("detail")
                or data.get("title")
                or data.get("error")
                or json.dumps(data)
            )
            raise AuthenticationError(
                f"No access_token in response. API returned: {detail}"
            )

        token = {
            "access_token": data["access_token"],
            "token_type": data.get("token_type", "bearer"),
            "expires_in": data.get("expires_in", 3600),
            "expires_at": time.time() + data.get("expires_in", 3600),
        }
        _save_token(token)

        # Persist credentials so future calls can use them
        cfg = _load_config()
        if client_id != cfg.get("client_id"):
            cfg["client_id"] = client_id
        if client_secret != cfg.get("client_secret"):
            cfg["client_secret"] = client_secret
        _save_config(cfg)

        logger.info(
            "DropCatch authentication successful — token expires in %ss",
            token["expires_in"],
        )
        return token

    @staticmethod
    def get_token() -> str:
        """Return a valid bearer token, refreshing if needed."""
        token = _load_token()
        if _token_is_valid(token):
            return token["access_token"]  # type: ignore[return-value]

        logger.info("DropCatch token expired or missing, re-authenticating ...")
        cid, secret = _resolve_credentials(None, None)
        token = _DropCatchAPI.auth(cid, secret)
        return token["access_token"]

    # -- Requests -------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.get_token()}"}

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 60,
        download: bool = False,
    ) -> Any:
        url = f"{self.base}{path}"
        headers = self._headers()

        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, params=params, timeout=timeout)
            else:
                resp = requests.post(url, headers=headers, json=params, timeout=timeout)
        except requests.ConnectionError as exc:
            raise ApiError(
                f"Network failure — could not reach {self.base}: {exc}"
            ) from exc
        except requests.Timeout as exc:
            raise ApiError(
                f"Request timed out after {timeout}s."
            ) from exc

        # Handle 401 — attempt re-auth once
        if resp.status_code == 401:
            logger.info("DropCatch token rejected, re-authenticating ...")
            try:
                cid, secret = _resolve_credentials(None, None)
                self.auth(cid, secret)
                headers = self._headers()
                if method == "GET":
                    resp = requests.get(url, headers=headers, params=params, timeout=timeout)
                else:
                    resp = requests.post(url, headers=headers, json=params, timeout=timeout)
                if resp.status_code == 401:
                    raise AuthenticationError(
                        "Unauthorized — check that your credentials are valid."
                    )
            except (AuthenticationError, ApiError) as exc:
                raise AuthenticationError(
                    f"Re-authentication failed: {exc}"
                ) from exc

        if download:
            if resp.status_code != 200:
                raise ApiError(
                    f"Download failed ({resp.status_code}): {resp.text[:500]}",
                    status_code=resp.status_code,
                )
            return resp.content

        if resp.status_code == 400:
            try:
                err = resp.json()
                detail = err.get("detail", err.get("title", resp.text[:500]))
            except json.JSONDecodeError:
                detail = resp.text[:500]
            raise ApiError(f"Bad request: {detail}", status_code=400)

        if resp.status_code == 404:
            return None

        if resp.status_code != 200:
            raise ApiError(
                f"API error ({resp.status_code}): {resp.text[:500]}",
                status_code=resp.status_code,
            )

        try:
            return resp.json()
        except json.JSONDecodeError as exc:
            raise ApiError(
                f"Invalid JSON response: {exc}\nBody: {resp.text[:1000]}"
            ) from exc

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return self._request("GET", path, params=params, timeout=60, download=False)

    def _get_download(self, path: str, params: Optional[Dict[str, Any]] = None) -> bytes:
        return self._request("GET", path, params=params, timeout=120, download=True)

    # -- Endpoints ------------------------------------------------------------

    def get_auctions(
        self,
        search_term: Optional[str] = None,
        size: int = DEFAULT_PAGE_SIZE,
        next_token: Optional[str] = None,
        previous: Optional[str] = None,
        show_all_active: bool = False,
        has_bids: Optional[bool] = None,
        end_time_min: Optional[str] = None,
        end_time_max: Optional[str] = None,
        tlds: Optional[List[str]] = None,
        types: Optional[List[str]] = None,
        high_bid_min: Optional[float] = None,
        high_bid_max: Optional[float] = None,
        sort: str = "HighBidDesc",
    ) -> Optional[Dict[str, Any]]:
        """Query /v2/auctions with the given filters."""
        params: Dict[str, Any] = {"size": size, "sort": sort}
        if search_term:
            params["searchTerm"] = search_term
        if next_token:
            params["next"] = next_token
        if previous:
            params["previous"] = previous
        if show_all_active:
            params["showAllActive"] = "true"
        if has_bids is not None:
            params["HasBids"] = str(has_bids).lower()
        if end_time_min:
            params["EndTime.Min"] = end_time_min
        if end_time_max:
            params["EndTime.Max"] = end_time_max
        if tlds:
            params["Tlds"] = ",".join(tlds) if len(tlds) > 1 else tlds[0]
        if types:
            params["Types"] = ",".join(types)
        if high_bid_min is not None:
            params["HighBid.Min"] = high_bid_min
        if high_bid_max is not None:
            params["HighBid.Max"] = high_bid_max
        return self._get("/v2/auctions", params)

    def get_backorders(
        self,
        search_term: Optional[str] = None,
        size: int = DEFAULT_PAGE_SIZE,
        tld: Optional[str] = None,
        next_token: Optional[str] = None,
        previous: Optional[str] = None,
        backorder_type: Optional[str] = None,
        sort: str = "MaxBidDesc",
    ) -> Optional[Dict[str, Any]]:
        """Query /v2/backorders with the given filters."""
        params: Dict[str, Any] = {"size": size, "sort": sort}
        if search_term:
            params["searchTerm"] = search_term
        if tld:
            params["tld"] = tld
        if next_token:
            params["next"] = next_token
        if previous:
            params["previous"] = previous
        if backorder_type:
            params["type"] = backorder_type
        return self._get("/v2/backorders", params)

    def download_auctions(self, download_type: str, file_type: str = "Csv") -> bytes:
        """Bulk download auction data as a .zip."""
        return self._get_download(
            f"/v2/downloads/auctions/{download_type}",
            {"fileType": file_type},
        )


# ---------------------------------------------------------------------------
# Public provider class
# ---------------------------------------------------------------------------


class DropCatchProvider:
    """Provider for fetching domain data from DropCatch auctions and backorders.

    Handles authentication, API querying, and persistence via Storage.

    Usage::

        provider = DropCatchProvider()
        provider.auth()
        domains = provider.get_auctions(tlds=["com", "io"], high_bid_min=10.0)
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        storage: Optional[Storage] = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.storage = storage or Storage()
        self._api: Optional[_DropCatchAPI] = None

    @property
    def api(self) -> _DropCatchAPI:
        if self._api is None:
            self._api = _DropCatchAPI()
        return self._api

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def auth(self) -> Dict[str, Any]:
        """Authenticate with DropCatch API.

        Credentials are resolved in this order:
        1. Values passed to the constructor
        2. Config file at ``~/.config/dropcatch-cli/config.json``
        3. ``DROPCATCH_CLIENT_ID`` / ``DROPCATCH_CLIENT_SECRET`` env vars

        The bearer token is persisted to ``~/.config/dropcatch-cli/token.json``.
        """
        cid, secret = _resolve_credentials(self.client_id, self.client_secret)
        return self.api.auth(cid, secret)

    # ------------------------------------------------------------------
    # Auctions
    # ------------------------------------------------------------------

    def get_auctions(
        self,
        search_term: Optional[str] = None,
        size: int = DEFAULT_PAGE_SIZE,
        next_token: Optional[str] = None,
        previous: Optional[str] = None,
        show_all_active: bool = False,
        has_bids: Optional[bool] = None,
        end_time_min: Optional[str] = None,
        end_time_max: Optional[str] = None,
        tlds: Optional[List[str]] = None,
        types: Optional[List[str]] = None,
        high_bid_min: Optional[float] = None,
        high_bid_max: Optional[float] = None,
        sort: str = "HighBidDesc",
        persist: bool = True,
    ) -> List[Domain]:
        """Query live auctions and return ``Domain`` objects.

        Args:
            search_term: Keyword to search for in domain names.
            size: Results per page (default 50).
            next_token: Pagination token for the next page.
            previous: Pagination token for the previous page.
            show_all_active: If True, show ALL active auctions instead of
                only those the user is participating in.
            has_bids: Filter by presence of bids.
            end_time_min: Earliest end time (ISO 8601).
            end_time_max: Latest end time (ISO 8601).
            tlds: List of TLDs to filter by (e.g. ``["com", "io"]``).
            types: Auction types (``"Dropped"``, ``"PrivateSeller"``,
                ``"PreRelease"``).
            high_bid_min: Minimum current high bid.
            high_bid_max: Maximum current high bid.
            sort: Sort order. One of ``"HighBidDesc"``, ``"HighBidAsc"``,
                ``"EndTimeAsc"``, ``"EndTimeDesc"``, ``"NameAsc"``,
                ``"NameDesc"``.
            persist: If True, persist results to the Storage backend.

        Returns:
            List of ``Domain`` models parsed from the API response.
        """
        logger.info(
            "Fetching DropCatch auctions (search=%s, tlds=%s, size=%d, sort=%s)",
            search_term, tlds, size, sort,
        )
        result = self.api.get_auctions(
            search_term=search_term,
            size=size,
            next_token=next_token,
            previous=previous,
            show_all_active=show_all_active,
            has_bids=has_bids,
            end_time_min=end_time_min,
            end_time_max=end_time_max,
            tlds=tlds,
            types=types,
            high_bid_min=high_bid_min,
            high_bid_max=high_bid_max,
            sort=sort,
        )
        domains = self._parse_auction_items(result)
        if persist:
            self._persist_domains(domains)
        logger.info("Retrieved %d auction domains", len(domains))
        return domains

    # ------------------------------------------------------------------
    # Backorders
    # ------------------------------------------------------------------

    def get_backorders(
        self,
        search_term: Optional[str] = None,
        size: int = DEFAULT_PAGE_SIZE,
        tld: Optional[str] = None,
        next_token: Optional[str] = None,
        previous: Optional[str] = None,
        backorder_type: Optional[str] = None,
        sort: str = "MaxBidDesc",
        persist: bool = True,
    ) -> List[Domain]:
        """List active backorders and return ``Domain`` objects.

        Args:
            search_term: Keyword to search for in domain names.
            size: Results per page (default 50).
            tld: Filter by TLD (e.g. ``"com"``).
            next_token: Pagination token for the next page.
            previous: Pagination token for the previous page.
            backorder_type: ``"Standard"`` or ``"DiscountClub"``.
            sort: Sort order (``"MaxBidDesc"``, ``"MaxBidAsc"``,
                ``"NameAsc"``, ``"NameDesc"``).
            persist: If True, persist results to the Storage backend.

        Returns:
            List of ``Domain`` models parsed from the API response.
        """
        logger.info(
            "Fetching DropCatch backorders (search=%s, tld=%s, size=%d, sort=%s)",
            search_term, tld, size, sort,
        )
        result = self.api.get_backorders(
            search_term=search_term,
            size=size,
            tld=tld,
            next_token=next_token,
            previous=previous,
            backorder_type=backorder_type,
            sort=sort,
        )
        domains = self._parse_backorder_items(result)
        if persist:
            self._persist_domains(domains)
        logger.info("Retrieved %d backorder domains", len(domains))
        return domains

    # ------------------------------------------------------------------
    # Bulk download
    # ------------------------------------------------------------------

    def download_auctions(self, download_type: str, file_type: str = "Csv") -> bytes:
        """Bulk download auction data as a compressed archive.

        Args:
            download_type: One of ``"AllActive"``, ``"Dropped"``,
                ``"PreRelease"``, ``"PrivateSeller"``.
            file_type: ``"Csv"`` or ``"Json"``.

        Returns:
            Raw bytes of the downloaded .zip file.
        """
        logger.info(
            "Downloading DropCatch auctions (type=%s, format=%s)",
            download_type, file_type,
        )
        return self.api.download_auctions(download_type, file_type)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_auction_items(result: Optional[Dict[str, Any]]) -> List[Domain]:
        """Map raw auction API items to Domain models."""
        if not result:
            return []
        items = result.get("items") or result.get("data") or []
        domains: List[Domain] = []
        for item in items:
            name: str = item.get("Name", "")
            if not name:
                continue
            tld_str = _extract_tld(name)
            end_time = _normalize_datetime(item.get("EndTime"))
            high_bid = _parse_money(item.get("HighBid"))
            domains.append(Domain(
                domain=name,
                source=f"dropcatch:{item.get('Type', 'auction')}",
                tld=tld_str,
                length=len(name),
                word_count=len(name.split(".")),
                current_price=high_bid,
                end_time=end_time,
                auction_id=str(item.get("AuctionId", "")),
                status="active",
                raw_data=json.dumps(item, default=str) if item else None,
            ))
        return domains

    @staticmethod
    def _parse_backorder_items(result: Optional[Dict[str, Any]]) -> List[Domain]:
        """Map raw backorder API items to Domain models."""
        if not result:
            return []
        items = result.get("items") or result.get("data") or []
        domains: List[Domain] = []
        for item in items:
            name: str = item.get("Name", "")
            if not name:
                continue
            tld_str = _extract_tld(name)
            max_bid = _parse_money(item.get("MaxBid"))
            domains.append(Domain(
                domain=name,
                source=f"dropcatch:backorder:{item.get('Type', 'unknown')}",
                tld=tld_str,
                length=len(name),
                word_count=len(name.split(".")),
                current_price=max_bid,
                status=item.get("Status", "active"),
                raw_data=json.dumps(item, default=str) if item else None,
            ))
        return domains

    def _persist_domains(self, domains: List[Domain]) -> None:
        """Write Domain objects into the storage backend."""
        self.storage.init()
        for d in domains:
            self.storage.insert_domain(d.model_dump())


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _extract_tld(domain: str) -> str:
    """Return the TLD portion of a domain name (everything after the last dot)."""
    parts = domain.split(".")
    return parts[-1].lower() if len(parts) > 1 else ""


def _parse_money(val: Any) -> Optional[float]:
    """Convert a money value from the API to float (or None)."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _normalize_datetime(dt_str: Optional[str]) -> Optional[str]:
    """Normalize ISO 8601 datetime string to a consistent format or return None."""
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.isoformat()
    except (ValueError, TypeError):
        return dt_str
