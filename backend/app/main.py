from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import models
from .database import Base, engine, get_db
from .keitaro import keitaro
from .schemas import CampaignCreate, CampaignUpdate, CampaignView, OfferAdd


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
    remote = await keitaro.create_campaign(name, country, payload.offer_id, offer.get("name", str(payload.offer_id)))
    remote_id = remote.get("id") if isinstance(remote, dict) else None
    alias = remote.get("alias") if isinstance(remote, dict) else None
    record = models.Campaign(name=name, country=country, offer_id=payload.offer_id, keitaro_id=remote_id, keitaro_alias=alias, status="created")
    record.offers.append(models.CampaignOffer(keitaro_offer_id=payload.offer_id, name=offer.get("name", str(payload.offer_id)), position=0, weight=100))
    db.add(record)
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
    share = 100 // len(campaign.offers)
    for i, row in enumerate(campaign.offers):
        row.weight = share + (1 if i < 100 % len(campaign.offers) else 0)
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
    if len(campaign.offers) == 1:
        raise HTTPException(409, "A campaign must retain at least one offer")
    campaign.offers.remove(row)
    share = 100 // len(campaign.offers)
    for i, item in enumerate(campaign.offers):
        item.weight = share + (1 if i < 100 % len(campaign.offers) else 0)
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
