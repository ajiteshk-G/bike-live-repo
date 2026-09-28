import time
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.claim import InsuranceClaim
from app.schemas.diagnostics import (
    DamageAssessmentRequest,
    DamageAssessmentResponse,
    WarningLightScanRequest,
    WarningLightScanResponse,
    ClaimSubmissionRequest,
    ClaimSubmissionResponse
)

class DiagnosticsService:
    @staticmethod
    def assess_damage(req: DamageAssessmentRequest) -> DamageAssessmentResponse:
        """Processes multimodal vision input to classify exterior damage and map OEM replacement parts."""
        # Simulated Gemini Multimodal Vision Damage Inspection Engine
        mock_type = req.mock_damage_type or "bumper_foglamp"
        
        if mock_type == "bumper_foglamp":
            parts = [
                "Scratches and paint abrasion on front mudguard and headlamp cowl",
                "Cracked lens on Right Front LED Turn Indicator"
            ]
            part_no = "#2W-88301"
            part_desc = "OEM Front LED Turn Indicator Assembly (RH)"
            part_cost = 1450.0
            labor_cost = 350.0
            summary = "Gemini Vision detected minor surface scrapes on the front mudguard / headlamp cowl and an impact crack on the RH indicator. No fork, handlebar or frame misalignment detected. Safe to ride to the workshop."
        elif mock_type == "windshield_chip":
            parts = ["Stone chip and crack on front visor / flyscreen (12mm)"]
            part_no = "#2W-44102"
            part_desc = "OEM Front Visor / Flyscreen"
            part_cost = 1200.0
            labor_cost = 250.0
            summary = "Gemini Vision detected an isolated stone chip with a hairline crack on the front visor. Replacement recommended for rider wind protection and visibility."
        else:
            parts = ["Side panel scratch and tank-shroud scuff (low-speed slide)"]
            part_no = "#2W-22904"
            part_desc = "OEM Side Panel / Tank Shroud (Painted)"
            part_cost = 1800.0
            labor_cost = 400.0
            summary = "Gemini Vision identified cosmetic scuffing on the painted side panel and tank shroud. No frame, footpeg or lever damage detected."

        return DamageAssessmentResponse(
            damage_detected=True,
            severity="MINOR",
            detected_parts=parts,
            structural_damage=False,
            recommended_oem_part=part_desc,
            oem_part_number=part_no,
            estimated_part_cost=part_cost,
            estimated_labor_cost=labor_cost,
            estimated_out_of_pocket=0.0, # Zero depreciation
            recommended_workshop="Authorised Two-Wheeler Service Workshop",
            parts_dispatch_eta="Tomorrow Morning ahead of scheduled service",
            gemini_vision_summary=summary
        )

    @staticmethod
    def scan_warning_light(req: WarningLightScanRequest) -> WarningLightScanResponse:
        symbol = (req.light_symbol or "engine_oil_pressure").lower()
        if "oil" in symbol:
            return WarningLightScanResponse(
                symbol_name="Engine Oil Viscosity / Service Required (Amber)",
                severity="WARNING",
                explanation="Service reminder triggered: engine oil is due for change based on odometer and time since last service.",
                recommended_action="Book a periodic service (engine oil, oil filter, chain lube & adjustment) within the next 200 km.",
                safe_to_drive=True
            )
        elif "tpms" in symbol or "tyre" in symbol or "tire" in symbol:
            return WarningLightScanResponse(
                symbol_name="Tyre Pressure Monitoring System (TPMS Low - Amber)",
                severity="WARNING",
                explanation="Rear tyre pressure is low (26 PSI vs recommended 33 PSI rider-only / 36 PSI with pillion).",
                recommended_action="Inflate tyres to the recommended pressure at the nearest fuel station before riding with a pillion.",
                safe_to_drive=True
            )
        else:
            return WarningLightScanResponse(
                symbol_name="ABS Indicator (Amber)",
                severity="INFO",
                explanation="The ABS lamp glows at start-up and switches off once the bike crosses ~5 km/h after the wheel-speed sensors self-check.",
                recommended_action="If the ABS lamp stays ON while riding, ABS may be inactive — ride carefully and get the wheel-speed sensors checked at an authorised workshop.",
                safe_to_drive=True
            )

    @staticmethod
    async def file_insurance_claim(db: AsyncSession, customer_db_id: int, req: ClaimSubmissionRequest, brand_id: Optional[str] = None) -> InsuranceClaim:
        from app.services.brand_service import BrandService
        b_id = (brand_id or (BrandService.get_active_brand().id if BrandService.get_active_brand() else "tvs")).lower()
        active_b = BrandService.get_brand(b_id)
        claim_id = f"{b_id.upper()[:3]}-INS-{int(time.time()) % 100000}"
        claim = InsuranceClaim(
            claim_id=claim_id,
            customer_id=customer_db_id,
            brand_id=b_id,
            vin=req.vin,
            vehicle_model=req.vehicle_model,
            incident_description=req.incident_description,
            damage_severity="MINOR",
            detected_damages=req.detected_damages,
            oem_part_number=req.oem_part_number,
            oem_part_description="OEM Replacement Assembly",
            estimated_part_cost=1450.0,
            estimated_labor_cost=350.0,
            customer_out_of_pocket=0.0,
            insurer_name="ICICI Lombard General Insurance",
            policy_number=f"POL-{b_id.upper()[:3]}-{claim_id[-6:]}",
            claim_status="DIGITALLY_APPROVED",
            workshop_name=req.workshop_name,
            parts_delivery_estimate="Tomorrow Morning 9:00 AM"
        )
        db.add(claim)
        await db.commit()
        await db.refresh(claim)
        return claim
