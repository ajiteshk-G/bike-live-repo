from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class OutboundCallTriggerRequest(BaseModel):
    customer_id: str = Field(..., description="Customer ID returned by /customer/identify")
    test_ride_session_id: Optional[str] = Field(None, description="Associated Test Ride Session ID")
    booking_reference: Optional[str] = Field(None, description="Booking reference, e.g. BK-TVS-12345")
    phone_number: Optional[str] = Field(default=None, description="Customer phone (used to resolve / register the rider if customer_id is unknown)")
    customer_name: Optional[str] = Field(default=None)
    vehicle_name: str = Field(default="TVS Apache RTR 160 4V")
    variant: Optional[str] = Field(default=None)
    dealership_name: Optional[str] = Field(default=None)
    advisor_name: Optional[str] = Field(default=None)
    call_channel: Optional[str] = Field(default="BROWSER_GEMINI_LIVE")
    brand_id: Optional[str] = Field(default=None, description="Brand ID, e.g. tvs, hero_motocorp")

class OutboundDialogueTurnRequest(BaseModel):
    call_reference: str = Field(..., description="Call Reference ID")
    customer_speech: str = Field(..., description="Customer spoken message or response")
    customer_response: Optional[str] = Field(None, description="Alternative field for customer speech")
    turn_index: int = Field(default=0)
    turn_number: Optional[int] = Field(None)
    conversation_history: Optional[List[Dict[str, str]]] = Field(default=None)

class OutboundDialogueTurnResponse(BaseModel):
    call_reference: str
    speaker: str = "Kavya (AI Specialist)"
    agent_message: str
    ai_reply: Optional[str] = None
    audio_tts_url: Optional[str] = None
    is_call_finished: bool = False
    action_item: Optional[str] = None
    turn_index: int

class OutboundCallInsightsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    call_reference: str
    brand_id: Optional[str] = None
    customer_id: Any
    customer_name: str
    agent_name: str
    phone_number: str
    call_status: str
    call_duration_seconds: int
    transcript: str
    objections_handled: List[str]
    objection_resolution_status: str
    customer_sentiment: str
    customer_decision: str
    locked_vehicle_variant: str
    locked_allocation_days: int
    next_step: str
    created_at: datetime
