# models.py

from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey
from database import Base


class StorageUnit(Base):
    __tablename__ = "storage_units"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    location = Column(String, nullable=True)
    owner = Column(String, nullable=True)
    purchase_price = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)


class StorageItem(Base):
    __tablename__ = "storage_items"

    id = Column(Integer, primary_key=True, index=True)
    unit_id = Column(Integer, ForeignKey("storage_units.id"), index=True, nullable=False)

    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=True)
    condition = Column(String, nullable=True)  # e.g. GOOD / FAIR / EXCELLENT

    estimated_value = Column(Float, nullable=True)
    quick_sell_value = Column(Float, nullable=True)  # Tony mode
    target_value = Column(Float, nullable=True)      # Andrew mode

    status = Column(String, nullable=True)  # KEEP / SELL_NOW / RESEARCH / SCRAP
