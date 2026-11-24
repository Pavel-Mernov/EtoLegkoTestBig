from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    country: Mapped[str] = mapped_column(String(2))
    offer_id: Mapped[int] = mapped_column(Integer)
    keitaro_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    keitaro_alias: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    offers: Mapped[list["CampaignOffer"]] = relationship(back_populates="campaign", cascade="all, delete-orphan", order_by="CampaignOffer.position")


class CampaignOffer(Base):
    __tablename__ = "campaign_offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    keitaro_offer_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(255))
    position: Mapped[int] = mapped_column(Integer, default=0)
    weight: Mapped[float] = mapped_column(Float, default=100)
    campaign: Mapped[Campaign] = relationship(back_populates="offers")
