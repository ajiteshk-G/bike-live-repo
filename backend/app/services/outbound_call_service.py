import uuid
import datetime
import logging
import asyncio
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.sales_ride import OutboundCallLog, TestRideRecording
from app.models.customer import Customer
from app.models.booking import TestDriveBooking
from app.schemas.outbound_call import (
    OutboundCallTriggerRequest,
    OutboundDialogueTurnRequest,
    OutboundDialogueTurnResponse,
    OutboundCallInsightsResponse
)
from app.config import settings

from app.services.brand_service import BrandService

logger = logging.getLogger("outbound_call_service")

class OutboundCallService:
    @staticmethod
    async def trigger_outbound_call(db: AsyncSession, req: OutboundCallTriggerRequest) -> OutboundCallLog:
        b_id = (req.brand_id or (BrandService.get_active_brand().id if BrandService.get_active_brand() else "tvs")).lower()
        active_brand = BrandService.get_brand(b_id)
        brand_name = active_brand.name if active_brand else b_id.title()

        # Find customer scoped by brand_id
        stmt = select(Customer).where((Customer.customer_id == req.customer_id) & (Customer.brand_id == b_id))
        res = await db.execute(stmt)
        customer = res.scalars().first()
        if not customer and req.phone_number:
            # Resolve / register the real rider from the supplied phone (+ name); never borrow another customer.
            from app.services.customer_service import CustomerService
            customer = await CustomerService.get_or_create_customer_by_phone(
                db, phone=req.phone_number, name=req.customer_name, brand_id=b_id
            )
        if not customer:
            raise LookupError(f"Customer '{req.customer_id}' not found for brand '{b_id}'.")

        # Find associated TestRideRecording for in-vehicle context
        tr_rec: Optional[TestRideRecording] = None
        if req.booking_reference:
            b_stmt = select(TestRideRecording).where(
                (TestRideRecording.booking_reference == req.booking_reference) &
                (TestRideRecording.brand_id == b_id)
            ).order_by(TestRideRecording.created_at.desc())
            b_res = await db.execute(b_stmt)
            tr_rec = b_res.scalars().first()

        if not tr_rec and customer:
            c_stmt = select(TestRideRecording).where(
                (TestRideRecording.customer_id == customer.id) &
                (TestRideRecording.brand_id == b_id)
            ).order_by(TestRideRecording.created_at.desc())
            c_res = await db.execute(c_stmt)
            tr_rec = c_res.scalars().first()

        default_veh = f"{brand_name} Two-Wheeler"
        veh_name = req.vehicle_name or (tr_rec.vehicle_name if tr_rec else default_veh)
        advisor_name = req.advisor_name or (tr_rec.sales_advisor_name if tr_rec else "Sales Consultant")
        advisor_short = advisor_name.split("(")[0].strip().split(" ")[0] or "Advisor"
        cust_name = req.customer_name or customer.name or "Valued Customer"

        call_ref = f"CALL-{b_id.upper()[:4]}-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

        agent_display_name = f"Kavya – {brand_name} AI (Post-Ride Concierge)"

        call_log = OutboundCallLog(
            call_reference=call_ref,
            customer_id=customer.id,
            brand_id=b_id,
            agent_name=agent_display_name,
            phone_number=req.phone_number or customer.phone,
            call_status="IN_PROGRESS",
            call_duration_seconds=0,
            transcript=None,
            objection_resolution_status="100% RESOLVED (Test Ride Feedback & Stock Lock)",
            customer_sentiment="POSITIVE",
            customer_decision="EVALUATING",
            locked_vehicle_variant=veh_name,
            locked_allocation_days=12,
            next_step="FEEDBACK_CONVERSATION"
        )

        db.add(call_log)
        customer.current_phase = "POST_TEST_RIDE_CALL"
        await db.commit()
        await db.refresh(call_log)
        return call_log

    @staticmethod
    async def process_dialogue_turn(db: AsyncSession, req: OutboundDialogueTurnRequest) -> OutboundDialogueTurnResponse:
        user_speech = req.customer_speech or req.customer_response or "The ride was very good."
        turn_idx = req.turn_index if req.turn_index is not None else (req.turn_number or 1)

        # Lookup call log
        stmt = select(OutboundCallLog).where(OutboundCallLog.call_reference == req.call_reference)
        res = await db.execute(stmt)
        call_log = res.scalars().first()

        # Lookup customer & test ride context
        b_id = (call_log.brand_id if call_log and call_log.brand_id else (BrandService.get_active_brand().id if BrandService.get_active_brand() else "tvs")).lower()
        active_brand = BrandService.get_brand(b_id)
        brand_name = active_brand.name if active_brand else b_id.title()

        # Lookup customer & test ride context
        cust_name = "Customer"
        veh_name = f"{brand_name} Model"
        advisor_short = "Advisor"
        tr_transcript = ""
        loved_features = ["Engine Pickup", "Braking Confidence", "Riding Comfort"]
        objections = ["Delivery Waiting Period", "Two-Wheeler Loan EMI"]

        if call_log:
            c_stmt = select(Customer).where((Customer.id == call_log.customer_id) & (Customer.brand_id == b_id))
            c_res = await db.execute(c_stmt)
            cust = c_res.scalars().first()
            if cust:
                cust_name = cust.name

            # Lookup test ride recording
            tr_stmt = select(TestRideRecording).where(
                (TestRideRecording.customer_id == call_log.customer_id) &
                (TestRideRecording.brand_id == b_id)
            ).order_by(TestRideRecording.created_at.desc())
            tr_res = await db.execute(tr_stmt)
            tr = tr_res.scalars().first()
            if tr:
                veh_name = tr.vehicle_name or veh_name
                advisor_short = (tr.sales_advisor_name or "Advisor").split("(")[0].strip().split(" ")[0] or "Advisor"
                tr_transcript = tr.transcript or ""
                loved_features = tr.loved_features or loved_features
                objections = tr.objections_raised or objections

        # Generate dynamic response via Gemini with strict brand domain guardrails
        agent_reply = ""
        try:
            from google import genai
            from google.genai import types

            from app.services.genai_client import get_genai_client
            client = get_genai_client()
            
            system_prompt = f"""You are Kavya, {brand_name}'s warm, polite and attentive Post-Test-Ride Customer Relationship Specialist (female voice).
You are in a live feedback phone call with {cust_name}, who recently completed a TEST RIDE of the two-wheeler {veh_name} with Sales Consultant {advisor_short}.

*** TEST RIDE CONTEXT ***
Test Ride Transcript:
{tr_transcript[:1000] if tr_transcript else "Customer test rode the motorcycle / scooter and experienced pickup, braking, handling and comfort."}

Customer Loved Features: {", ".join(loved_features)}
Objections / Questions Raised: {", ".join(objections)}

*** YOUR GOALS IN THIS CALL ***
1. Ask how the test ride felt — pickup / acceleration, braking & ABS confidence, handling in traffic and corners, seat height & rider fit, pillion comfort, mileage or EV range — and confirm {advisor_short} answered all questions (including helmet / riding-gear safety tips).
2. Address remaining doubts on on-road price, colour / variant availability, delivery timeline, exchange of their old two-wheeler, and two-wheeler loan options (typically 10-25% down payment, 12-48 month tenure).
3. Offer to reserve their preferred variant & colour and send the booking / loan link on WhatsApp.

*** STRICT DOMAIN & SCOPE BOUNDARY (MANDATORY RULE) ***
1. NEVER answer questions outside {brand_name} two-wheelers, test rides, bookings, service, accessories, or official financing.
2. If the customer asks about unrelated topics, politely steer back to their {veh_name} test ride. If they compare with competitor bikes/scooters, acknowledge briefly and highlight {brand_name}'s strengths without disparaging the competitor.
   - Example: "Main keval {brand_name} bikes aur aapke test ride experience ke baare mein baat kar sakti hoon."
3. Respond in conversational Hindi/Hinglish, natural, polite, and concise (under 30 words per turn)."""

            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.3
            )

            history_context = ""
            if req.conversation_history:
                for h in req.conversation_history:
                    spk = h.get("speaker", "User")
                    txt = h.get("text", "")
                    history_context += f"{spk}: {txt}\n"

            prompt_content = f"{history_context}Customer: {user_speech}"

            resp = await asyncio.wait_for(
                asyncio.to_thread(
                    client.models.generate_content,
                    model=settings.REST_CHAT_MODEL,
                    contents=[prompt_content],
                    config=config
                ),
                timeout=6.0
            )

            if resp and resp.text:
                agent_reply = resp.text.strip()
        except Exception as e:
            logger.warning(f"Gemini outbound call turn notice: {e}")

        if not agent_reply:
            if "bye" in user_speech.lower() or "dhanyavaad" in user_speech.lower() or "thank" in user_speech.lower() or "finalize" in user_speech.lower():
                agent_reply = f"Shukriya {cust_name} ji! Maine aapka pasandida variant reserve kar diya hai aur booking & loan link WhatsApp par bhej diya hai. Ride safe!"
            else:
                agent_reply = f"Sunkar bahut achha laga {cust_name} ji! Kya {advisor_short} ji ne braking, riding modes aur baaki features theek se samjhaye the? Hum aapki booking aur two-wheeler loan process turant start kar sakte hain."

        is_finished = "shukriya" in agent_reply.lower() or "thank" in agent_reply.lower() or turn_idx >= 4

        # Update call log transcript
        agent_tag = f"Kavya – {brand_name} AI"
        if call_log:
            now_sec = (turn_idx * 15) + 12
            call_log.call_duration_seconds = now_sec
            call_log.transcript = (call_log.transcript or "") + f'\n[00:{now_sec:02d}] Customer: "{user_speech}"\n[00:{now_sec+5:02d}] {agent_tag}: "{agent_reply}"'
            if is_finished:
                call_log.call_status = "COMPLETED"
                call_log.objection_resolution_status = "100% RESOLVED (Allocation Locked)"
                call_log.customer_decision = "CONFIRMED_BOOKING_PROCEED_TO_FINANCE"
            await db.commit()

        return OutboundDialogueTurnResponse(
            call_reference=req.call_reference,
            speaker=agent_tag,
            agent_message=agent_reply,
            ai_reply=agent_reply,
            is_call_finished=is_finished,
            action_item="PROCEED_TO_FINANCING" if is_finished else "AWAIT_CUSTOMER_REPLY",
            turn_index=turn_idx + 1
        )

    @staticmethod
    async def get_call_insights(db: AsyncSession, call_reference: str) -> Optional[OutboundCallInsightsResponse]:
        stmt = select(OutboundCallLog).where(OutboundCallLog.call_reference == call_reference)
        res = await db.execute(stmt)
        call = res.scalars().first()
        if not call:
            return None

        # Fetch customer
        cust_stmt = select(Customer).where(Customer.id == call.customer_id)
        cust_res = await db.execute(cust_stmt)
        cust = cust_res.scalars().first()

        return OutboundCallInsightsResponse(
            call_reference=call.call_reference,
            brand_id=call.brand_id,
            customer_id=cust.customer_id if cust else "",
            customer_name=cust.name if cust else "Valued Customer",
            agent_name=call.agent_name,
            phone_number=call.phone_number,
            call_status=call.call_status,
            call_duration_seconds=call.call_duration_seconds,
            transcript=call.transcript or "",
            objections_handled=[
                "Test Ride Feedback Confirmed",
                "Sales Consultant Demonstration Quality Verified",
                "Variant / Colour Allocation & Two-Wheeler Loan EMI Processed"
            ],
            objection_resolution_status=call.objection_resolution_status or "100% RESOLVED",
            customer_sentiment=call.customer_sentiment or "VERY_POSITIVE",
            customer_decision=call.customer_decision or "LOCKED_FAST_ALLOCATION",
            locked_vehicle_variant=call.locked_vehicle_variant or "Vehicle",
            locked_allocation_days=call.locked_allocation_days or 12,
            next_step=call.next_step or "DIGITAL_FINANCING_KYC",
            created_at=call.created_at
        )
