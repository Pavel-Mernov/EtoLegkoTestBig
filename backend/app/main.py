from contextlib import asynccontextmanager
from math import floor

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import models
from .database import Base, engine, get_db
from .keitaro import keitaro
from .schemas import CampaignCreate, CampaignImport, CampaignUpdate, CampaignView, OfferAdd


def rebalance_offers(offers: list[models.CampaignOffer]) -> None:
    """Assign equal shares to 0.01% precision while keeping the total at 100%."""
    if not offers:
        return
    base_points = floor(10_000 / len(offers))
    extra_points = 10_000 - base_points * len(offers)
    for index, offer in enumerate(offers):
        offer.weight = (base_points + (1 if index < extra_points else 0)) / 100


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
    else:
        record.name = remote.get("name", record.name)
        record.country = country
        record.offer_id = rows[0].keitaro_offer_id
        record.keitaro_alias = remote.get("alias", record.keitaro_alias)
        record.status = remote.get("state", record.status)
        record.offers.clear()
    record.offers.extend(rows)
    db.commit()
    db.refresh(record)
    return record


@app.post("/api/campaigns/{campaign_id}/offers", response_model=CampaignView)
async def add_offer(campaign_id: int, payload: OfferAdd, db: Session = Depends(get_db)):
    campaign = db.scalar(select(models.Campaign).options(selectinload(models.Campaign.offers)).where(models.Campaign.id == campaign_id))
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if any(o.keitaro_offer_id == payload.offer_id for o in campaign.offers):
        raise HTTPException(409, "Offer is already in this campaign")
    offer = await keitaro.offer(payload.offer_id)
    item = models.CampaignOffer(campaign_id=campaign.id, keitaro_offer_id=payload.offer_id, name=offer.get("name", str(payload.offer_id)), position=len(campaign.offers), weight=0)
    campaign.offers.append(item)
    rebalance_offers(campaign.offers)
    db.flush()
    if campaign.keitaro_id:
        try:
            await keitaro.update_campaign_offers(campaign.keitaro_id, campaign.offers)
        except HTTPException:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            raise HTTPException(502, f"Offer update failed: {exc}") from exc
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


@app.delete("/api/campaigns/{campaign_id}/offers/{offer_row_id}", response_model=CampaignView)
async def delete_offer(campaign_id: int, offer_row_id: int, db: Session = Depends(get_db)):
    campaign = db.scalar(select(models.Campaign).options(selectinload(models.Campaign.offers)).where(models.Campaign.id == campaign_id))
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    row = next((o for o in campaign.offers if o.id == offer_row_id), None)
    if not row:
        raise HTTPException(404, "Offer not found in this campaign")
    campaign.offers.remove(row)
    for position, item in enumerate(campaign.offers):
        item.position = position
    rebalance_offers(campaign.offers)
    db.flush()
    if campaign.keitaro_id:
        try:
            await keitaro.update_campaign_offers(campaign.keitaro_id, campaign.offers)
        except HTTPException:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            raise HTTPException(502, f"Offer update failed: {exc}") from exc
    db.commit()
    db.refresh(campaign)
    return campaign
