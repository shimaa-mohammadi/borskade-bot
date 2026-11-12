"""Async client for the official (undocumented) TSETMC CDN API.

All endpoints below were verified live against https://cdn.tsetmc.com
(the same API the new tsetmc.ir frontend calls from its JS bundle).
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

log = logging.getLogger(__name__)

BASE = "https://cdn.tsetmc.com/api"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Referer": "https://www.tsetmc.com/",
    "Accept": "application/json, text/plain, */*",
}


class TsetmcClient:
    def __init__(self, proxy: str | None = None):
        self._client = httpx.AsyncClient(
            headers=HEADERS,
            timeout=httpx.Timeout(25.0),
            proxy=proxy or None,
            follow_redirects=True,
            http2=False,
        )
        self._cache: dict[str, tuple[float, Any]] = {}

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------ core
    async def _get(self, path: str, *, ttl: float = 0.0) -> Any:
        if ttl:
            hit = self._cache.get(path)
            if hit and hit[0] > time.time():
                return hit[1]
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                r = await self._client.get(BASE + path)
                r.raise_for_status()
                data = r.json()
                if ttl:
                    self._cache[path] = (time.time() + ttl, data)
                return data
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                log.warning("TSETMC %s failed (attempt %s): %s", path, attempt + 1, exc)
                await asyncio.sleep(1.2 * (attempt + 1))
        raise RuntimeError(f"TSETMC request failed: {path} ({last_exc})")

    # ------------------------------------------------------------- endpoints
    async def search(self, query: str) -> list[dict]:
        """Return candidate instruments for a (Persian) symbol name."""
        from urllib.parse import quote

        data = await self._get(f"/Instrument/GetInstrumentSearch/{quote(query)}", ttl=300)
        rows = data.get("instrumentSearch") or []
        return [r for r in rows if r.get("insCode") and r.get("lVal18AFC")]

    async def instrument_info(self, ins_code: str) -> dict:
        data = await self._get(f"/Instrument/GetInstrumentInfo/{ins_code}", ttl=60)
        return data.get("instrumentInfo") or {}

    async def daily_list(self, ins_code: str) -> list[dict]:
        """Daily closing rows, newest first (dEven is Gregorian yyyymmdd)."""
        data = await self._get(f"/ClosingPrice/GetClosingPriceDailyList/{ins_code}/0", ttl=120)
        return data.get("closingPriceDaily") or []

    async def best_limits(self, ins_code: str) -> list[dict]:
        """Order book snapshot (5+ levels)."""
        data = await self._get(f"/BestLimits/{ins_code}", ttl=25)
        return data.get("bestLimits") or []

    async def client_type_history(self, ins_code: str) -> list[dict]:
        """Individual/legal buy-sell history, newest first."""
        data = await self._get(f"/ClientType/GetClientTypeHistory/{ins_code}", ttl=120)
        return data.get("clientType") or []

    async def share_holders(self, ins_code: str) -> list[dict]:
        data = await self._get(f"/Shareholder/GetInstrumentShareHolderLast/{ins_code}", ttl=600)
        return data.get("shareHolder") or []

    async def codal_reports(self, ins_code: str, top: int = 30) -> list[dict]:
        """Latest Codal disclosures related to this instrument, newest first."""
        data = await self._get(f"/Codal/GetPreparedDataByInsCode/{top}/{ins_code}", ttl=120)
        return data.get("preparedData") or []

    async def statement_content(self, ins_code: str) -> list[dict]:
        """Codal income-statement tables (reportType 6, subType 6, pageId 1)."""
        data = await self._get(f"/Codal/GetStatementContentByInsCode/6/6/1/{ins_code}", ttl=900)
        return data.get("statemetnContent") or []

    async def messages(self, ins_code: str) -> list[dict]:
        """Exchange / market-supervisor announcements for the instrument."""
        data = await self._get(f"/Msg/GetMsgByInsCode/{ins_code}", ttl=120)
        return data.get("msg") or []

    async def closing_price_info(self, ins_code: str) -> dict | None:
        """Live intraday snapshot; returns {} if unavailable."""
        for path in (f"/ClosingPrice/GetClosingPriceInfo/{ins_code}",
                     f"/ClosingPrice/GetClosingPrice/{ins_code}"):
            try:
                data = await self._get(path, ttl=20)
                for key in ("closingPriceInfo", "closingPrice"):
                    if isinstance(data.get(key), dict):
                        return data[key]
                if isinstance(data, dict) and data:
                    return data
            except Exception as exc:  # noqa: BLE001
                log.debug("closing info failed via %s: %s", path, exc)
        return None
