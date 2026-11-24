from typing import Any

import httpx
from fastapi import HTTPException

from .config import settings


class KeitaroClient:
    """Small adapter for the subset of Keitaro Admin API used by this app."""

    def __init__(self):
        # KEITARO_API_ADDRESS may be either the host or the complete v1 API URL.
        self.base = settings.keitaro_api_address.rstrip("/")
        suffix = "/admin_api/v1"
        if self.base.endswith(suffix):
            self.base = self.base[: -len(suffix)]
        self.headers = {"Api-Key": settings.keitaro_api_key, "Content-Type": "application/json"}

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        if not self.base or not settings.keitaro_api_key:
            raise HTTPException(503, "Set KEITARO_API_ADDRESS and KEITARO_API_KEY.")
        url = f"{self.base}/admin_api/v1{path}"
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                response = await client.request(method, url, headers=self.headers, **kwargs)
                response.raise_for_status()
                return response.json() if response.content else None
        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json()
            except ValueError:
                detail = exc.response.text[:500]
            raise HTTPException(exc.response.status_code, f"Keitaro API error: {detail}") from exc
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"Cannot reach Keitaro: {exc}") from exc

    @staticmethod
    def items(data: Any) -> list[dict]:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("items", "data", "offers", "campaigns", "streams", "groups", "domains", "traffic_sources"):
                if isinstance(data.get(key), list):
                    return data[key]
        return []

    async def list_offers(self, query: str = "") -> list[dict]:
        params = {"offset": 0, "limit": 170}
        data = self.items(await self.request("GET", settings.keitaro_offers_path, params=params))
        if query.strip():
            term = query.casefold().strip()
            data = [row for row in data if term in str(row.get("name", "")).casefold() or term in str(row.get("id", ""))]
        return data

    async def offer(self, offer_id: int) -> dict:
        data = await self.request("GET", f"{settings.keitaro_offers_path}/{offer_id}")
        if not isinstance(data, dict) or not data.get("id"):
            raise HTTPException(404, f"Keitaro offer {offer_id} was not found")
        return data

    async def get_campaign(self, campaign_id: int) -> dict:
        data = await self.request("GET", f"{settings.keitaro_campaigns_path}/{campaign_id}")
        if not isinstance(data, dict) or not data.get("id"):
            raise HTTPException(404, f"Keitaro campaign {campaign_id} was not found")
        return data

    async def get_campaign_streams(self, campaign_id: int) -> list[dict]:
        streams = self.items(await self.request("GET", f"{settings.keitaro_campaigns_path}/{campaign_id}/streams"))
        detailed = []
        for stream in streams:
            stream_id = stream.get("id")
            if not stream_id:
                detailed.append(stream)
                continue
            details = await self.request("GET", f"{settings.keitaro_streams_path}/{stream_id}")
            detailed.append({**stream, **details} if isinstance(details, dict) else stream)
        return detailed

    async def _catalog_item(self, path: str, item_id: int, *, params: dict | None = None) -> dict:
        rows = self.items(await self.request("GET", path, params=params))
        match = next((row for row in rows if int(row.get("id", 0)) == item_id), None)
        if not match:
            raise HTTPException(502, f"Configured Keitaro catalog item {item_id} is missing at {path}")
        return match

    async def create_campaign(self, name: str, country: str, offer_id: int) -> dict:
        # Groups, domains and traffic sources are read-only on the supplied test stand.
        group = await self._catalog_item(settings.keitaro_groups_path, settings.keitaro_group_id, params={"type": "campaigns"})
        source = await self._catalog_item(settings.keitaro_sources_path, settings.keitaro_source_id)
        domain = await self._catalog_item(settings.keitaro_domains_path, settings.keitaro_domain_id)

        campaign_payload = {
            "name": name,
            "group_id": group["id"],
            "traffic_source_id": source["id"],
            "domain_id": domain["id"],
            "type": "position",
            "cost_type": "CPC",
            "cost_value": 0,
            "cost_currency": "USD",
        }
        campaign = await self.request("POST", settings.keitaro_campaigns_path, json=campaign_payload)
        if not isinstance(campaign, dict) or not campaign.get("id"):
            raise HTTPException(502, "Keitaro created a campaign but returned no campaign ID")
        campaign_id = int(campaign["id"])

        # The test stand exposes streams as a separate Admin API resource.
        try:
            await self.request("POST", settings.keitaro_streams_path, json={
                "campaign_id": campaign_id,
                "name": f"Geo {country.upper()}",
                "type": "regular",
                "schema": "redirect",
                "action_type": "http",
                "action_payload": "https://google.com",
                "filters": [{"name": "country", "mode": "accept", "payload": [country.upper()]}],
            })
            await self.request("POST", settings.keitaro_streams_path, json={
                "campaign_id": campaign_id,
                "name": "Офферы",
                "type": "default",
                "schema": "landings",
                "offers": [{"offer_id": offer_id, "share": 100, "state": "active"}],
            })
        except HTTPException as exc:
            # Avoid leaving a campaign with one or no streams if stream setup fails.
            try:
                await self.request("DELETE", f"{settings.keitaro_campaigns_path}/{campaign_id}")
            except HTTPException as cleanup_error:
                raise HTTPException(
                    502,
                    f"Campaign {campaign_id} was created but stream setup failed ({exc.detail}); cleanup also failed ({cleanup_error.detail}).",
                ) from exc
            raise
        return campaign

    async def update_campaign_offers(self, keitaro_id: int, offers: list[Any]) -> None:
        streams = self.items(await self.request("GET", f"{settings.keitaro_campaigns_path}/{keitaro_id}/streams"))
        landing = next((stream for stream in streams if stream.get("name") == "Офферы" or stream.get("type") == "default" or stream.get("schema") == "landings"), None)
        if not landing or not landing.get("id"):
            stream_info = [{"id": s.get("id"), "name": s.get("name"), "type": s.get("type"), "schema": s.get("schema")} for s in streams]
            raise HTTPException(502, f"Could not find the campaign's offer stream in Keitaro. Streams: {stream_info}")
        payload = {
            "offers": [
                {
                    "offer_id": row["offer_id"] if isinstance(row, dict) else row.keitaro_offer_id,
                    "share": row["share"] if isinstance(row, dict) else row.weight,
                    "state": "active",
                }
                for row in offers
            ]
        }
        await self.request("PUT", f"{settings.keitaro_streams_path}/{landing['id']}", json=payload)

    async def update_campaign(self, keitaro_id: int, *, name: str, country: str) -> None:
        await self.request("PUT", f"{settings.keitaro_campaigns_path}/{keitaro_id}", json={"name": name})
        streams = self.items(await self.request("GET", f"{settings.keitaro_campaigns_path}/{keitaro_id}/streams"))
        geo_stream = next((stream for stream in streams if str(stream.get("name") or "").startswith("Geo ") or any(f.get("name") == "country" for f in (stream.get("filters") or []))), None)
        if not geo_stream or not geo_stream.get("id"):
            raise HTTPException(502, "Could not find the GEO stream in Keitaro")
        await self.request("PUT", f"{settings.keitaro_streams_path}/{geo_stream['id']}", json={
            "name": "Geo GM" if country.upper() == "GM" else f"Geo {country.upper()}",
            "filters": [{"name": "country", "mode": "accept", "payload": [country.upper()]}],
        })


keitaro = KeitaroClient()
