from datetime import datetime
from pydantic import BaseModel, Field


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    country: str = Field(min_length=2, max_length=2)
    offer_id: int = Field(gt=0)


class OfferAdd(BaseModel):
    offer_id: int = Field(gt=0)


class CampaignUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    country: str = Field(min_length=2, max_length=2)


class OfferView(BaseModel):
    id: int
    keitaro_offer_id: int
    name: str
    position: int
    weight: int

    class Config:
        from_attributes = True


class CampaignView(BaseModel):
    id: int
    name: str
    country: str
    offer_id: int
    keitaro_id: int | None
    keitaro_alias: str | None
    status: str
    created_at: datetime
    offers: list[OfferView]

    class Config:
        from_attributes = True
