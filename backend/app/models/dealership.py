from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Float, Boolean
from app.database import Base

class Dealership(Base):
    __tablename__ = "dealerships"

    id = Column(String(64), primary_key=True, index=True) # e.g. "tvs_mumbai_andheri"
    brand_id = Column(String(64), index=True, default="tvs", nullable=False)
    name = Column(String(128), nullable=False) # "TVS Motor Authorised Dealer – Andheri West"
    city = Column(String(64), index=True, nullable=False) # "Mumbai", "Pune", "Delhi", "Bengaluru", "Chennai"
    state = Column(String(64), nullable=False) # "Maharashtra", "Delhi", "Karnataka", "Tamil Nadu"
    area = Column(String(128), nullable=True) # "Andheri West", "Koramangala"
    address = Column(Text, nullable=False)
    pin_code = Column(String(16), nullable=False)
    phone = Column(String(32), nullable=False)
    email = Column(String(128), nullable=True)
    map_url = Column(String(256), nullable=True)
    rating = Column(Float, default=4.8)
    available_advisors = Column(JSON, nullable=True) # ["Rahul Nair (Sales Consultant)"]
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
