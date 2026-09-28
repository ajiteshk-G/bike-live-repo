from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict

class TestRideStartRequest(BaseModel):
    customer_id: str = Field(..., description="Customer ID returned by /customer/identify")
    vehicle_id: str = Field(default="tvs_apache_rtr_160_4v", description="Vehicle model ID")
    variant: str = Field(default="Dual Channel ABS", description="Vehicle variant")
    sales_advisor_name: str = Field(default="Rahul Nair (Sales Consultant)", description="Advisor Name")
    dealership_name: str = Field(default="TVS Motor Authorised Dealer – Andheri West", description="Dealership name")

class TestRideRecordingUploadRequest(BaseModel):
    session_id: Optional[str] = Field(None, description="Test Ride session ID")
    customer_id: str = Field(..., description="Customer ID")
    booking_reference: Optional[str] = Field(None, description="Booking reference, e.g. BK-TVS-16859")
    customer_name: Optional[str] = Field(None, description="Customer Name")
    brand_id: Optional[str] = Field(None, description="Brand identifier, e.g. tvs, hero_motocorp")
    vehicle_id: str = Field(default="tvs_apache_rtr_160_4v")
    variant: str = Field(default="Dual Channel ABS")
    sales_advisor_name: str = Field(default="Rahul Nair (Sales Consultant)")
    audio_base64: Optional[str] = Field(None, description="Base64 encoded audio recording from mobile device")
    audio_format: str = Field(default="audio/wav")
    duration_seconds: int = Field(default=184)
    simulated_scenario: Optional[str] = Field(default="city_test_ride_simulation")
    advisor_checklist: Optional[List[str]] = Field(None, description="Demonstrated checklist items")

class TestRideInsightResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    brand_id: Optional[str] = "tvs"
    booking_reference: Optional[str] = None
    customer_id: Union[str, int]
    vehicle_id: str
    vehicle_name: str
    sales_advisor_name: str
    gcs_uri: str
    gcs_bucket: str
    gcs_object_path: Optional[str] = None
    duration_seconds: int
    transcript: str
    customer_sentiment_score: float
    purchase_intent_score: float
    loved_features: List[str]
    objections_raised: List[str]
    advisor_pitch_score: float
    advisor_coaching_feedback: str
    recommended_action: str
    status: str
    created_at: datetime

class ConversationTurnItem(BaseModel):
    speaker: str
    role: str
    message: str
    timestamp: Optional[str] = ""

class ConversationSessionSummary(BaseModel):
    session_id: str
    date_key: str
    date_label: str
    time_label: str
    channel: str = "LIVE_VOICE"
    interested_car: str
    interested_features: List[str] = []
    budget: str
    key_points_summary: str
    turn_count: int = 0
    turns: List[ConversationTurnItem] = []

class DailyConversationGroup(BaseModel):
    date_key: str
    date_label: str
    conversation_count: int
    cars_discussed: List[str] = []
    features_interested: List[str] = []
    budget_mentioned: str
    sessions: List[ConversationSessionSummary] = []

class TestRideLeadItem(BaseModel):
    customer_id: str
    brand_id: Optional[str] = "tvs"
    name: str
    phone: str
    email: Optional[str] = None
    city: str
    preferred_vehicle: str
    vehicle_name: Optional[str] = None
    vehicle_id: Optional[str] = "tvs_apache_rtr_160_4v"
    variant: Optional[str] = "Dual Channel ABS"
    booking_reference: Optional[str] = None
    dealership_id: Optional[str] = None
    dealership_name: Optional[str] = None
    booking_type: Optional[str] = "HOME_DOORSTEP"
    delivery_address: Optional[str] = None
    booking_status: str
    scheduled_slot: Optional[str] = None
    presales_notes: Optional[str] = None
    advisor_checklist: Optional[List[str]] = None
    is_custom_checklist: Optional[bool] = False
    total_conversations: int = 0
    interested_cars: List[str] = []
    interested_features: List[str] = []
    budget_range: Optional[str] = None
    conversations_by_day: List[DailyConversationGroup] = []
