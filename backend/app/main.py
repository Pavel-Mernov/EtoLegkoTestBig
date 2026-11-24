from contextlib import asynccontextmanager
from math import floor

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import models
from .database import Base, engine, get_db
from .keitaro import keitaro
from .schemas import CampaignCreate, CampaignImport, CampaignUpdate, CampaignView, OfferPush


def order_campaign_offers(campaign: models.Campaign) -> None:
    active = sorted((row for row in campaign.offers if not row.archived), key=lambda row: row.position)
    archived = sorted((row for row in campaign.offers if row.archived), key=lambda row: row.position)
    for position, row in enumerate(active + archived):
        row.position = position


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Adrobot Campaign Manager", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/offers")
async def search_offers(q: str = ""):
    return await keitaro.list_offers(q)


@app.get("/api/campaigns", response_model=list[CampaignView])
def list_campaigns(db: Session = Depends(get_db)):
    return db.scalars(select(models.Campaign).options(selectinload(models.Campaign.offers)).order_by(models.Campaign.id.desc())).all()


@app.post("/api/campaigns", response_model=CampaignView, status_code=201)
async def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db)):
    name = payload.name.strip()
    country = payload.country.upper()
    if not name:
        raise HTTPException(422, "Campaign name is required")
    offer = await keitaro.offer(payload.offer_id)
    remote = await keitaro.create_campaign(name, country, payload.offer_id)
    remote_id = remote.get("id") if isinstance(remote, dict) else None
    alias = remote.get("alias") if isinstance(remote, dict) else None
    record = models.Campaign(name=name, country=country, offer_id=payload.offer_id, keitaro_id=remote_id, keitaro_alias=alias, status="created")
    record.offers.append(models.CampaignOffer(keitaro_offer_id=payload.offer_id, name=offer.get("name", str(payload.offer_id)), position=0, weight=100))
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@app.post("/api/campaigns/import", response_model=CampaignView)
async def import_campaign(payload: CampaignImport, db: Session = Depends(get_db)):
    remote = await keitaro.get_campaign(payload.keitaro_id)
    streams = await keitaro.get_campaign_streams(payload.keitaro_id)
    geo_stream = next((s for s in streams if any(f.get("name") == "country" for f in (s.get("filters") or []))), None)
    offer_stream = next((s for s in streams if s.get("type") == "default" or s.get("schema") == "landings" or s.get("name") == "Офферы"), None)
    if not geo_stream:
        raise HTTPException(422, "Campaign has no country filter stream")
    if not offer_stream or not offer_stream.get("offers"):
        raise HTTPException(422, "Campaign has no offers in its default stream")
    filters = geo_stream.get("filters") or []
    country_filter = next((f for f in filters if f.get("name") == "country"), None)
    country_values = (country_filter or {}).get("payload") or []
    if not country_values:
        raise HTTPException(422, "Country filter has no country code")
    country = str(country_values[0]).upper()
    if len(country) != 2:
        raise HTTPException(422, "Expected a two-letter country code in the GEO stream")

    rows = []
    for position, remote_offer in enumerate(offer_stream["offers"]):
        offer_id = int(remote_offer.get("offer_id", 0))
        if not offer_id:
            continue
        details = await keitaro.offer(offer_id)
        share = float(remote_offer.get("share", 0))
        rows.append(models.CampaignOffer(
            keitaro_offer_id=offer_id,
            name=details.get("name", str(offer_id)),
            position=position,
            weight=share,
        ))
    if not rows:
        raise HTTPException(422, "Campaign has no valid offers")

    record = db.scalar(select(models.Campaign).options(selectinload(models.Campaign.offers)).where(models.Campaign.keitaro_id == payload.keitaro_id))
    if record is None:
        record = models.Campaign(
            name=remote.get("name", f"Campaign {payload.keitaro_id}"),
            country=country,
            offer_id=rows[0].keitaro_offer_id,
            keitaro_id=payload.keitaro_id,
            keitaro_alias=remote.get("alias"),
            status=remote.get("state", "active"),
        )
        db.add(record)
        record.offers.extend(rows)
    else:
        record.name = remote.get("name", record.name)
        record.country = country
        record.offer_id = rows[0].keitaro_offer_id
        record.keitaro_alias = remote.get("alias", record.keitaro_alias)
        record.status = remote.get("state", record.status)
        known = {row.keitaro_offer_id: row for row in record.offers}
        remote_ids = {row.keitaro_offer_id for row in rows}
        for row in record.offers:
            if row.keitaro_offer_id not in remote_ids:
                row.archived = True
                row.position = len(rows) + row.position
        for row in rows:
            existing = known.get(row.keitaro_offer_id)
            if existing:
                existing.name = row.name
                existing.position = row.position
                existing.weight = row.weight
                existing.archived = False
            else:
                record.offers.append(row)
    order_campaign_offers(record)
    db.commit()
    db.refresh(record)
    return record


@app.post("/api/campaigns/{campaign_id}/fetch-streams")
async def fetch_campaign_streams(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.scalar(select(models.Campaign).options(selectinload(models.Campaign.offers)).where(models.Campaign.id == campaign_id))
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if not campaign.keitaro_id:
        raise HTTPException(409, "Campaign is not linked to Keitaro")
    remote = await keitaro.get_campaign(campaign.keitaro_id)
    streams = await keitaro.get_campaign_streams(campaign.keitaro_id)
    offer_stream = next((s for s in streams if s.get("type") == "default" or s.get("schema") == "landings" or s.get("name") == "Офферы"), None)
    geo_stream = next((s for s in streams if any(f.get("name") == "country" for f in (s.get("filters") or []))), None)
    if not offer_stream:
        raise HTTPException(422, "Keitaro campaign has no default offer stream")

    remote_rows = []
    for position, offer_data in enumerate(offer_stream.get("offers") or []):
        offer_id = int(offer_data.get("offer_id", 0))
        if offer_id <= 0:
            continue
        details = await keitaro.offer(offer_id)
        remote_rows.append((offer_id, details.get("name", str(offer_id)), float(offer_data.get("share", 0)), position))
    if not remote_rows:
        raise HTTPException(422, "Keitaro offer stream is empty")

    existing = {row.keitaro_offer_id: row for row in campaign.offers}
    remote_ids = {offer_id for offer_id, _, _, _ in remote_rows}
    for row in campaign.offers:
        if row.keitaro_offer_id not in remote_ids:
            row.archived = True
    for offer_id, name, share, position in remote_rows:
        row = existing.get(offer_id)
        if row is None:
            row = models.CampaignOffer(campaign_id=campaign.id, keitaro_offer_id=offer_id, name=name)
            campaign.offers.append(row)
        row.name = name
        row.weight = share
        row.position = position
        row.archived = False
    if geo_stream:
        country_filter = next((f for f in (geo_stream.get("filters") or []) if f.get("name") == "country"), None)
        values = (country_filter or {}).get("payload") or []
        if values:
            campaign.country = str(values[0]).upper()
    campaign.name = remote.get("name", campaign.name)
    campaign.offer_id = remote_rows[0][0]
    campaign.status = remote.get("state", campaign.status)
    order_campaign_offers(campaign)
    db.commit()
    db.refresh(campaign)
    return {"campaign": CampaignView.model_validate(campaign), "streams": streams}


@app.post("/api/campaigns/{campaign_id}/offers/push", response_model=CampaignView)
async def push_offers(campaign_id: int, payload: OfferPush, db: Session = Depends(get_db)):
    campaign = db.scalar(select(models.Campaign).options(selectinload(models.Campaign.offers)).where(models.Campaign.id == campaign_id))
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if not campaign.keitaro_id:
        raise HTTPException(409, "Campaign is not linked to Keitaro")
    if len(payload.offer_ids) != len(set(payload.offer_ids)):
        raise HTTPException(422, "Offer IDs must be unique")

    existing = {row.keitaro_offer_id: row for row in campaign.offers}
    details_by_id = {}
    for offer_id in payload.offer_ids:
        details_by_id[offer_id] = await keitaro.offer(offer_id)

    desired_rows = []
    if payload.offer_ids:
        base_points = floor(10_000 / len(payload.offer_ids))
        extra_points = 10_000 - base_points * len(payload.offer_ids)
        for position, offer_id in enumerate(payload.offer_ids):
            share = (base_points + (1 if position < extra_points else 0)) / 100
            desired_rows.append({"offer_id": offer_id, "share": share})
    try:
        await keitaro.update_campaign_offers(campaign.keitaro_id, desired_rows)
    except HTTPException:
        db.rollback()
        raise

    for position, offer_id in enumerate(payload.offer_ids):
        row = existing.get(offer_id)
        if row is None:
            row = models.CampaignOffer(campaign_id=campaign.id, keitaro_offer_id=offer_id, name=details_by_id[offer_id].get("name", str(offer_id)))
            campaign.offers.append(row)
        row.name = details_by_id[offer_id].get("name", str(offer_id))
        row.position = position
        row.weight = desired_rows[position]["share"]
        row.archived = False
    for offer_id, row in existing.items():
        if offer_id not in payload.offer_ids:
            row.archived = True
            row.position = len(payload.offer_ids) + row.position
    order_campaign_offers(campaign)
    if payload.offer_ids:
        campaign.offer_id = payload.offer_ids[0]
    db.commit()
    db.refresh(campaign)
    return campaign

@app.put("/api/campaigns/{campaign_id}", response_model=CampaignView)
async def edit_campaign(campaign_id: int, payload: CampaignUpdate, db: Session = Depends(get_db)):
    campaign = db.scalar(select(models.Campaign).options(selectinload(models.Campaign.offers)).where(models.Campaign.id == campaign_id))
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    name = payload.name.strip()
    country = payload.country.upper()
    if not name:
        raise HTTPException(422, "Campaign name is required")
    if campaign.keitaro_id:
        try:
            await keitaro.update_campaign(campaign.keitaro_id, name=name, country=country)
        except HTTPException:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            raise HTTPException(502, f"Campaign update failed: {exc}") from exc
    campaign.name = name
    campaign.country = country
    db.commit()
    db.refresh(campaign)
    return campaign
