import json
import logging
import asyncio
import re
from typing import Dict, Any, Optional, Callable
from google import genai
from google.genai import types
from app.config import settings
from app.services.catalog_service import CatalogService
from app.services.checklist_service import ChecklistService
from app.services.customer_service import CustomerService

logger = logging.getLogger("gemini_live_session")

def _clean(val: Any) -> str:
    """Stringifies an optional catalog value (lists joined), returning '' for empty values."""
    if val is None:
        return ""
    if isinstance(val, (list, tuple)):
        return ", ".join(str(x).strip() for x in val if x is not None and str(x).strip())
    return str(val).strip()


def _format_vehicle_facts(v: Any) -> str:
    """Renders one catalog vehicle as a compact fact sheet for the system prompt (empty fields skipped)."""
    name = _clean(getattr(v, "name", "")) or _clean(getattr(v, "id", ""))
    header_bits = [f"id: '{_clean(getattr(v, 'id', ''))}'"]
    if _clean(getattr(v, "category", "")):
        header_bits.append(_clean(v.category))
    if _clean(getattr(v, "price_range", "")):
        header_bits.append(f"Ex-showroom {_clean(v.price_range)}")
    lines = [f"- {name} ({' | '.join(header_bits)})"]
    if _clean(getattr(v, "tagline", "")):
        lines.append(f"    Tagline: {_clean(v.tagline)}")

    cc = _clean(getattr(v, "displacement_cc", None))
    if cc and "cc" not in cc.lower():
        cc = f"{cc} cc"
    spec_fields = [
        ("Engine/Motor", _clean(getattr(v, "engine_specs", ""))),
        ("Displacement", cc),
        ("Max power", _clean(getattr(v, "max_power", None))),
        ("Max torque", _clean(getattr(v, "max_torque", None))),
        ("Fuel", _clean(getattr(v, "fuel_or_battery", ""))),
        ("Mileage/Range", _clean(getattr(v, "range_or_mileage", ""))),
        ("Fuel tank/Battery", _clean(getattr(v, "fuel_tank_or_battery", None))),
        ("Top speed", _clean(getattr(v, "top_speed", None))),
        ("Kerb weight", _clean(getattr(v, "kerb_weight", None))),
        ("Seat height", _clean(getattr(v, "seat_height", None))),
        ("Brakes", _clean(getattr(v, "braking", None))),
        ("Riding modes", _clean(getattr(v, "riding_modes", None))),
        ("Colours", _clean(getattr(v, "colors", None))),
    ]
    specs = "; ".join(f"{label}: {val}" for label, val in spec_fields if val)
    if specs:
        lines.append(f"    Specs: {specs}")
    highlights = _clean(list(getattr(v, "key_highlights", None) or [])[:6])
    if highlights:
        lines.append(f"    Highlights: {highlights}")
    if _clean(getattr(v, "usp", "")):
        lines.append(f"    USP: {_clean(v.usp)}")
    variants = []
    for var in (getattr(v, "variants", None) or [])[:6]:
        var_name = _clean(getattr(var, "name", ""))
        var_price = _clean(getattr(var, "price_ex_showroom", ""))
        if var_name:
            variants.append(f"{var_name}{f' ({var_price})' if var_price else ''}")
    if variants:
        lines.append(f"    Variants: {'; '.join(variants)}")
    rivals = _clean(getattr(v, "competitors", None))
    if rivals:
        lines.append(f"    Segment rivals (for positioning only - never quote their specs): {rivals}")
    return "\n".join(lines)


def _compose_system_prompt(agent_name: str, brand_name: str, tagline: str = "", lineup_block: str = "", ids_str: str = "") -> str:
    """Builds the brand-agnostic two-wheeler showroom persona prompt for Kavya."""
    brand_upper = brand_name.upper()
    tagline_line = f' ("{tagline}")' if tagline else ""
    lineup_section = (
        f"""You represent {brand_name}{tagline_line} strictly across its two-wheeler lineup (motorcycles and scooters). Use ONLY these official catalog facts when quoting specs and prices:
{lineup_block}
"""
        if lineup_block
        else f"You represent {brand_name}{tagline_line} strictly across its two-wheeler lineup (motorcycles and scooters).\n"
    )
    carousel_ids = f" ({ids_str})" if ids_str else ""
    return f"""You are {agent_name}, an expert, enthusiastic FEMALE AI Showroom Specialist at the two-wheeler Virtual Showroom of {brand_name}, helping customers choose the right motorcycle or scooter.

*** CRITICAL RULE #1: DYNAMIC FOLLOW-UP LANGUAGE MODE (NEVER STAY LOCKED IN ONE LANGUAGE) ***
- Greet initially in clear, warm English.
- On EVERY subsequent turn, dynamically switch to and respond 100% in the EXACT language the customer just spoke in their latest turn:
  * If the customer speaks in **English**, respond 100% in **English** (do NOT use any Hindi or Hinglish words).
  * If the customer speaks in **Hindi** or **Hinglish**, respond in **Hindi / Hinglish**.
  * If the customer speaks in **Marathi, Tamil, Telugu, Kannada, Malayalam, Bengali, Gujarati, Punjabi, Odia, Urdu, or Assamese**, immediately switch and respond 100% in that language.
- NEVER stay locked in the previous turn's language if the customer switches language! Always follow the language of the customer's MOST RECENT utterance.

*** MANDATORY FEMALE GENDER GRAMMAR RULE ***
- You are strictly a FEMALE specialist named {agent_name}.
- Whenever speaking a gendered Indian language (like Hindi, Hinglish, Marathi, Punjabi, or Gujarati), ALWAYS use feminine first-person verb forms ("sakti hoon", "chahti hoon", "batati hoon") and NEVER masculine forms ("sakta hoon", "chahta hoon").

{lineup_section}
*** UNDERSTAND THE RIDER FIRST (ASK 1 SHORT QUESTION AT A TIME, CONVERSATIONALLY) ***
- Daily commute distance, and mostly city traffic or highway riding?
- Riding solo or often with a pillion?
- Rider height and experience (is this their first bike or scooter?).
- Petrol or electric? If electric, do they have home charging (parking with a power socket)?
- Budget, and motorcycle or scooter preference.
- Then recommend the best-fit {brand_name} model(s) from the lineup and explain WHY using real specs: engine cc / PS / Nm, mileage in kmpl or EV range and charging time, ABS (single / dual-channel) or CBS / SBT, disc vs drum brakes, riding modes, TFT / LCD cluster and Bluetooth connectivity, suspension (USD forks, monoshock), seat height and kerb weight (rider fit), under-seat storage (scooters), fuel tank, top speed, and pillion comfort.
- If a spec is not listed in the catalog facts, say you will have the showroom team confirm it - NEVER invent numbers.

*** PRICING (TWO-WHEELER SCALE) ***
- Quote official EX-SHOWROOM prices exactly as listed in the catalog (two-wheelers are typically between sixty thousand rupees and three and a half lakh rupees - never quote any price that is not in the catalog).
- Speak prices naturally in Indian format, e.g. ₹1,14,390 is spoken as "one lakh fourteen thousand three hundred ninety rupees" and ₹62,405 as "sixty-two thousand four hundred five rupees". On-road price, offers and EMI are confirmed by the {brand_name} dealership team.

*** MANDATORY SHOWROOM CAROUSEL & HERO CO-BROWSING ACTION ***
- Whenever the customer mentions, inquires about, or compares ANY vehicle in our lineup{carousel_ids}, you MUST call the tool `switch_vehicle_showroom(car_name='<vehicle_id>')` with that vehicle's exact ID AND immediately speak your answer in the same turn.

*** MANDATORY END CALL PROTOCOL ***
- Whenever the customer explicitly indicates they have finished the entire conversation (e.g., says "No, thank you", "Nothing else", "Nahi chahiye, thank you", "Bye", "Bas dhanyavaad", "That's all", or asks to end the call), speak a warm 1-sentence farewell in the customer's language AND call the `end_call` tool so the call disconnects automatically.
- CRITICAL RULE: NEVER end the call or call `end_call` when a customer books a test ride! Booking a test ride is NOT the end of the call. After a test ride is booked, you MUST keep the call connected, warmly confirm the booking details, and ask what else the customer would like to explore next (e.g., features, variant comparisons, riding gear, or EMI/financing options).

*** STRICT DOMAIN & SCOPE BOUNDARY (MANDATORY RULE - NEVER ANSWER OUTSIDE {brand_upper} TWO-WHEELERS) ***
1. YOU MUST NEVER ANSWER ANY QUESTION OUTSIDE OF {brand_upper} MOTORCYCLES, SCOOTERS, ELECTRIC TWO-WHEELERS, TEST RIDES, OR VIRTUAL SHOWROOM SERVICES.
2. If the user asks ANY question about unrelated topics (general knowledge, coding, weather, politics, recipes, entertainment, sports, history, advice, or illegal/off-topic activities):
   - Immediately and politely decline in the customer's spoken language (using strictly feminine grammar if speaking Hindi/Hinglish) and redirect to {brand_name} two-wheelers.
3. If the user asks about ANY competitor or non-{brand_name} two-wheeler brand (e.g. Bajaj, Honda, Yamaha, Royal Enfield, Suzuki, Ather, Ola, or any other brand not in our lineup):
   - DO NOT provide specs, prices, details, or comparisons for competitor models. Politely state that you only represent {brand_name} and highlight the most relevant {brand_name} model and its strengths instead.

*** STEP-BY-STEP CONFIRMATION PROTOCOL FOR TEST RIDE BOOKING (MANDATORY REQUIREMENT) ***
- Test rides must ALWAYS be customized to the customer's choice of Model and specific Variant.
- Confirm step-by-step in the customer's current spoken language:
  * STEP 1 (MODEL & VARIANT): Confirm which specific model and variant (e.g. disc / drum, single / dual-channel ABS, battery size) they want to ride.
  * STEP 2 (HOME vs SHOWROOM): Ask whether they prefer a Doorstep (Home) test ride or a Showroom visit.
  * STEP 3 (ADDRESS & PIN): Ask for their address and area PIN code.
  * STEP 4 (CONFIRM ADDRESS): Confirm the address before asking date/time.
  * STEP 5 (DATE & TIME): Ask for preferred date and a 9 AM - 6 PM time slot.
  * STEP 6 (FINAL BOOKING & CONTINUE CONVERSATION): Confirm the test ride booking warmly, naturally remind them to bring their valid two-wheeler riding licence and a helmet (the dealership can also provide one), and immediately ask if they have any more questions about features, variants, riding gear, or EMI/financing options to continue the conversation. Do NOT disconnect the call.

STRICT GUARDRAILS:
1. OFFERS & ON-ROAD PRICE: Official on-road pricing and offers will be shared by our authorized {brand_name} dealership team. Quote official EX-SHOWROOM prices accurately from the catalog.
2. SAFETY: Always promote safe riding - helmets for rider and pillion, and a valid riding licence for test rides.
3. Keep the response natural, warm, in the customer's latest spoken language, and concise (under 35 words)."""


KAVYA_SYSTEM_PROMPT = _compose_system_prompt("Kavya", "our Authorised Dealership")



def build_brand_system_prompt(brand_id: Optional[str] = None) -> str:
    try:
        from app.services.brand_service import BrandService
        brand = BrandService.get_brand(brand_id) if brand_id else BrandService.get_active_brand()
        if brand:
            vehicles = list(brand.vehicles or [])
            lineup_block = "\n".join(_format_vehicle_facts(v) for v in vehicles)
            ids_str = ", ".join(f"{v.name} (id: '{v.id}')" for v in vehicles)
            agent_name = brand.avatar_name or "Kavya"
            return _compose_system_prompt(
                agent_name=agent_name,
                brand_name=brand.name,
                tagline=_clean(getattr(brand, "tagline", "")),
                lineup_block=lineup_block,
                ids_str=ids_str,
            )
    except Exception as e:
        logger.warning(f"Failed building brand prompt: {e}")
    return KAVYA_SYSTEM_PROMPT

MIA_SYSTEM_PROMPT = KAVYA_SYSTEM_PROMPT

GEMINI_TOOLS_DECLARATIONS = [
    {
        "name": "show_vehicle_spotlight",
        "description": "Highlights a specific two-wheeler (motorcycle or scooter) from the active brand lineup on the showroom stage.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "vehicle_id": {"type": "STRING", "description": "Exact vehicle ID from the active brand catalog (e.g. 'tvs_apache_rtr_160_4v', 'tvs_iqube')"}
            },
            "required": ["vehicle_id"]
        }
    },
    {
        "name": "compare_vehicles",
        "description": "Opens side-by-side spec comparison matrix (engine cc / power / torque, mileage or EV range, brakes, weight, seat height, price) for two models from the active brand lineup.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "vehicle_id_1": {"type": "STRING"},
                "vehicle_id_2": {"type": "STRING"}
            },
            "required": ["vehicle_id_1", "vehicle_id_2"]
        }
    },
    {
        "name": "update_advisor_checklist",
        "description": "Call this tool whenever the customer asks about or is interested in specific features (performance, mileage / EV range, ABS / braking, riding modes, connectivity, rider fit, storage, pillion comfort), to add tailored demonstration points to the Sales Consultant Demo Checklist for their test ride.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "vehicle_id": {"type": "STRING", "description": "Exact vehicle ID from the active brand catalog."},
                "checklist_items": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "Actionable demo items for the sales consultant (e.g. 'Demonstrate dual-channel ABS braking in a safe zone', 'Pair customer's phone with the TFT cluster for navigation & call alerts', 'Check seat height / flat-footing for a first-time rider')"
                }
            },
            "required": ["checklist_items"]
        }
    },
    {
        "name": "book_test_drive",
        "description": "Opens the test ride booking calendar and books a test ride for the chosen two-wheeler model and variant.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "model_name": {"type": "STRING", "description": "Exact vehicle ID from the active brand catalog (e.g. 'tvs_apache_rtr_160_4v', 'tvs_iqube')."},
                "variant": {"type": "STRING", "description": "Specific variant name, e.g. 'Dual Channel ABS', 'Disc', 'Drum', '3.4 kWh'"},
                "transmission": {"type": "STRING", "description": "Manual (geared motorcycle) or Automatic (CVT scooter / EV)"},
                "fuel_type": {"type": "STRING", "description": "Petrol or Electric"},
                "customer_id": {"type": "STRING"},
                "test_drive_type": {"type": "STRING", "description": "HOME_DOORSTEP or SHOWROOM_VISIT test ride"},
                "pincode": {"type": "STRING"},
                "pickup_address": {"type": "STRING"},
                "preferred_date_time": {"type": "STRING"},
                "phone_number": {"type": "STRING"}
            },
            "required": ["model_name"]
        }
    }
]

def detect_indian_language(text: str) -> str:
    """Detects Indian languages from script and vocabulary."""
    if re.search(r'[\u0900-\u097F]', text):
        if any(w in text for w in ["आहे", "गाडीची", "सांगा", "पाहिजे", "करायची", "किंमत", "नमस्कार", "करा", "होय"]):
            return "Marathi"
        return "Hindi"
    if re.search(r'[\u0B80-\u0BFF]', text):
        return "Tamil"
    if re.search(r'[\u0C00-\u0C7F]', text):
        return "Telugu"
    if re.search(r'[\u0C80-\u0CFF]', text):
        return "Kannada"
    if re.search(r'[\u0D00-\u0D7F]', text):
        return "Malayalam"
    if re.search(r'[\u0980-\u09FF]', text):
        if any(w in text for w in ["নমস্কাৰ", "বিচাৰে", "কৰা"]):
            return "Assamese"
        return "Bengali"
    if re.search(r'[\u0A80-\u0AFF]', text):
        return "Gujarati"
    if re.search(r'[\u0A00-\u0A7F]', text):
        return "Punjabi"
    if re.search(r'[\u0B00-\u0B7F]', text):
        return "Odia"
    if re.search(r'[\u0600-\u06FF]', text):
        return "Urdu"

    lower = text.lower()
    if any(k in lower for k in ["ahe", "gadi", "sang", "mahit", "namaskar", "pahije"]):
        return "Marathi"
    if any(k in lower for k in ["vanakkam", "vilai", "enna", "venum", "solla"]):
        return "Tamil"
    if any(k in lower for k in ["namaskaram", "dhara", "cheppandi", "kavali", "enta"]):
        return "Telugu"
    if any(k in lower for k in ["namaskara", "bele", "hegi", "beku"]):
        return "Kannada"
    if any(k in lower for k in ["namaskaram", "vila", "enganeya"]):
        return "Malayalam"
    if any(k in lower for k in ["nomoshkar", "daam", "koto", "bolun"]):
        return "Bengali"
    if any(k in lower for k in ["namaste", "kem cho", "kimat"]):
        return "Gujarati"
    if any(k in lower for k in ["sat sri akal", "kime", "daso"]):
        return "Punjabi"
    if any(re.search(rf"\b{k}\b", lower) for k in ["kya", "kitna", "batao", "bhai", "hai", "kaise", "chahiye", "gadi", "milega", "karo", "namaste", "bilkul", "haan", "theek"]):
        return "Hinglish"

    return "en-IN"

def _default_vehicle_id() -> str:
    """First vehicle of the active brand catalog (brand-agnostic default for co-browsing)."""
    try:
        from app.services.brand_service import BrandService
        b = BrandService.get_active_brand()
        if b and b.vehicles:
            return b.vehicles[0].id
    except Exception:
        pass
    return ""


_MATCH_STOPWORDS = {"the", "new", "and", "pro", "plus", "bike", "scooter", "motorcycle", "electric", "series", "edition", "tvs", "hero", "motocorp", "motor"}


class AudioSessionManager:
    def __init__(self, session_id: str, customer_id: str = "GUEST-TRANSIENT"):
        self.session_id = session_id
        self.customer_id = customer_id
        self.is_active = True
        self.language = "en-IN"
        self.active_vehicle_id = _default_vehicle_id()
        self.chat_history: list = []
        self.checklist_items: list = []
        self.vertex_client: Optional[genai.Client] = None
        
        # Initialize Vertex AI Client with Project mb-poc-352009
        try:
            from app.services.genai_client import get_genai_client
            self.vertex_client = get_genai_client()
            logger.info(f"Initialized Vertex AI Client on project {settings.VERTEX_PROJECT_ID}")
        except Exception as e:
            logger.warning(f"Could not initialize Vertex AI client: {e}")

    async def process_user_text_or_intent(self, text: str, emit_ui_callback: Callable) -> Dict[str, Any]:
        """Calls Vertex AI Gemini Flash with dynamic brand system prompt and co-browsing tools."""
        detected_lang = detect_indian_language(text)
        if detected_lang:
            self.language = detected_lang

        lower = text.lower()
        tool_call = None
        tool_args = {}

        # 1. UI Event Detection for Co-Browsing (Active Brand Dynamic Matching)
        from app.services.brand_service import BrandService
        active_b = BrandService.get_active_brand()
        matched_v = None

        if active_b and active_b.vehicles:
            brand_tokens = set((active_b.name or "").lower().split())
            best_score = 0
            for v in active_b.vehicles:
                # Score by vehicle slug or distinctive name tokens (e.g. "apache", "rr", "310", "iqube")
                if v.id.lower() in lower:
                    matched_v = v
                    break
                v_words = [
                    w for w in re.split(r"[\s\-/()]+", v.name.lower())
                    if w and w not in _MATCH_STOPWORDS and w not in brand_tokens and (len(w) > 2 or w.isdigit() or w in ("rr", "x"))
                ]
                score = sum(1 for w in v_words if re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", lower))
                if score > best_score:
                    best_score = score
                    matched_v = v

        if matched_v:
            self.active_vehicle_id = matched_v.id
            tool_call = "show_vehicle_spotlight"
            tool_args = {"vehicle_id": matched_v.id}
            try:
                res = emit_ui_callback({"type": "UI_ACTION", "tool_name": tool_call, "tool_args": tool_args})
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass
        elif any(w in lower for w in ["compare", "versus", "vs", "तुलना", "ஒப்பீடு", "போலிక"]):
            tool_call = "compare_vehicles"
            v_list = [v.id for v in active_b.vehicles] if (active_b and active_b.vehicles) else [self.active_vehicle_id]
            v2 = v_list[1] if len(v_list) > 1 and v_list[0] == self.active_vehicle_id else (v_list[0] if v_list else self.active_vehicle_id)
            tool_args = {"vehicle_id_1": self.active_vehicle_id, "vehicle_id_2": v2}
            try:
                res = emit_ui_callback({"type": "UI_ACTION", "tool_name": tool_call, "tool_args": tool_args})
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass
        elif any(w in lower for w in ["test ride", "test drive", "book ride", "book drive", "schedule ride", "schedule drive", "take a ride", "take a drive", "ride book", "drive book", "टेस्ट राइड", "राइड", "ड्राइव", "ரைட்", "டிரைவ்", "రైడ్", "డ్రైవ్"]):
            tool_call = "open_test_drive_booking"
            tool_args = {"vehicle_id": self.active_vehicle_id}
            try:
                res = emit_ui_callback({"type": "UI_ACTION", "tool_name": tool_call, "tool_args": tool_args})
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass

        # 1b. Dynamic Advisor Demo Checklist extraction from customer asks
        new_extracted = ChecklistService.extract_checklist_items(
            customer_text=text,
            vehicle_id=self.active_vehicle_id,
            existing_items=self.checklist_items
        )
        if new_extracted:
            self.checklist_items = new_extracted
            try:
                chk_res = emit_ui_callback({
                    "type": "CHECKLIST_UPDATED",
                    "vehicle_id": self.active_vehicle_id,
                    "checklist": self.checklist_items
                })
                if asyncio.iscoroutine(chk_res):
                    await chk_res
            except Exception:
                pass

        # 2. Invoke Vertex AI Gemini Flash Model with Dynamic Brand System Prompt
        response_text = ""
        brand_prompt = build_brand_system_prompt()
        if self.vertex_client:
            try:
                # Add to history
                self.chat_history.append({"role": "user", "parts": [{"text": text}]})

                lang_rule = (
                    "\n\n[THIS TURN] The customer wrote in English: reply 100% in English, no Hindi words or Devanagari."
                    if self.language == "en-IN" else
                    f"\n\n[THIS TURN] Mirror the customer's language ({self.language})."
                ) + (" This is a text chat: do NOT narrate or mention tool/function calls; the UI updates automatically.")
                config = types.GenerateContentConfig(
                    system_instruction=brand_prompt + lang_rule,
                    temperature=0.3,
                    max_output_tokens=500,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                    tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="NONE")),
                )

                # Format conversation contents
                contents = []
                for turn in self.chat_history[-6:]:
                    contents.append(types.Content(
                        role=turn["role"],
                        parts=[types.Part.from_text(text=turn["parts"][0]["text"])]
                    ))

                def _clean(resp) -> str:
                    if not (resp and resp.candidates and resp.candidates[0].content):
                        return ""
                    raw = "".join(p.text for p in (resp.candidates[0].content.parts or []) if getattr(p, "text", None))
                    raw = re.sub(r"(?im)^\s*`{0,3}\s*tool_code\s*$|^\s*`{3}\s*$", "", raw)
                    raw = re.sub(r"(?im)^\s*print\([a-z_]+\(.*\)\)\s*$", "", raw)
                    return re.sub(r"(?im)^\s*\(?calling\s+`?[a-z_]+`?.*$", "", raw).strip()

                vertex_resp = await asyncio.to_thread(
                    self.vertex_client.models.generate_content,
                    model=settings.REST_CHAT_MODEL,
                    contents=contents,
                    config=config
                )
                response_text = _clean(vertex_resp)
                if not response_text:
                    # The prompt describes live-voice UI tools; in text mode the model may answer with only a
                    # function_call. Acknowledge it as done and ask for the spoken answer in plain text.
                    contents.append(types.Content(role="user", parts=[types.Part.from_text(
                        text="(The showroom screen has already been updated for you. Now answer my question "
                             "directly in plain text, following the language rule.)")]))
                    vertex_resp = await asyncio.to_thread(
                        self.vertex_client.models.generate_content,
                        model=settings.REST_CHAT_MODEL,
                        contents=contents,
                        config=config
                    )
                    response_text = _clean(vertex_resp)
                if response_text:
                    self.chat_history.append({"role": "model", "parts": [{"text": response_text}]})
            except Exception as e:
                logger.error(f"Vertex AI Gemini generation error: {e}")

        # Fallback if vertex generation failed
        if not response_text:
            b_name = active_b.name if active_b else "our showroom"
            av_name = (active_b.avatar_name if active_b else None) or "Kavya"
            active_v = next((v for v in (active_b.vehicles if active_b else []) if v.id == self.active_vehicle_id), None)
            v_label = active_v.name if active_v else (self.active_vehicle_id.replace('_', ' ').title() or "two-wheeler")
            response_text = (
                f"Hi! I'm {av_name} from {b_name}. I can help you with the {v_label} and book a test ride for you."
                if self.language == "en-IN" else
                f"Namaste! Main {av_name}, {b_name} se. Main aapki {v_label} aur Test Ride booking me madad kar sakti hoon."
            )

        return {
            "message": response_text,
            "tool_call": tool_call,
            "tool_args": tool_args,
            "language": self.language,
            "checklist": self.checklist_items,
            "vehicle_id": self.active_vehicle_id
        }
