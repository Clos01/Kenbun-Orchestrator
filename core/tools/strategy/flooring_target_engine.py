"""
Flooring Lead Targeting & Persona Classification Engine.

Implements the 4 High-Yield B2B Contractor Archetypes:
1. Custom Home Builders & GCs ($800k-$3M+ specs, 3k-6k sq ft European oak / luxury tile)
2. Commercial Project Managers (Tenant buildouts, restaurants, medical, 20mil LVP)
3. High-End Interior Designers & Specifiers (Material selection, custom stains, zero-flake)
4. Volume Real Estate Flippers (5-10 flips/quarter, quick turnaround durable LVP)

Designed for integration with the ArcGIS / OpenGov Permit Engine, Planka CRM,
and 60-minute guerrilla jobsite sprints.
"""

from __future__ import annotations
import re
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List


class FlooringTargetPersona(str, Enum):
    CUSTOM_HOME_BUILDER = "custom_home_builder"
    COMMERCIAL_PM = "commercial_pm"
    HIGH_END_DESIGNER = "high_end_designer"
    VOLUME_FLIPPER = "volume_flipper"
    GENERAL_RESIDENTIAL = "general_residential"


PERSONA_PROFILES: Dict[FlooringTargetPersona, Dict[str, Any]] = {
    FlooringTargetPersona.CUSTOM_HOME_BUILDER: {
        "title": "Custom Home Builder & Luxury GC",
        "tag": "custom-builder",
        "description": "Builders managing $800k-$3M+ residential specs requiring high-touch craftsmanship, tight scheduling, and architectural-grade materials.",
        "primary_materials": "7-9\" Engineered European White Oak, Herringbone, Chevron, Luxury Porcelain Tile",
        "est_material_rate": 6.50,
        "est_labor_rate": 4.50,
        "subfloor_prep_rate": 0.85,
        "sqft_coverage_ratio": 0.75,  # 75% of total conditioned square footage
        "sprint_pitch": (
            "Hey {contact}, I'm {rep_name} with {company_name}. We're wrapping up a 3,500 sq ft custom "
            "white oak install down the road. Saw your framing is almost set. Who handles your hardwoods and trim packages?"
        ),
        "value_proposition": "Bespoke craftsman finishing, seamless flush stair nosings, moisture-tested subfloors, and guaranteed start dates.",
        "collateral_checklist": [
            "Luxury European White Oak & Herringbone sample board",
            "Proof of General Liability ($2M) & Workers' Comp",
            "60-second video portfolio of flush vents & custom stair nosings",
            "Take-off specification sheet"
        ]
    },
    FlooringTargetPersona.COMMERCIAL_PM: {
        "title": "Commercial Project Manager",
        "tag": "commercial-pm",
        "description": "Project Managers directing tenant improvements, medical clinics, boutique retail, and restaurants on rigid turnover deadlines.",
        "primary_materials": "20-28mil Commercial Glue-Down LVP, Modular Carpet Tile, Commercial Moisture Barrier",
        "est_material_rate": 4.25,
        "est_labor_rate": 2.75,
        "subfloor_prep_rate": 1.10,  # Commercial subfloors often require extensive leveling
        "sqft_coverage_ratio": 0.65,
        "sprint_pitch": (
            "What's going on {contact}? {rep_name} from {company_name}. We specialize in commercial tenant buildouts with after-hours "
            "and weekend mobilization so you never blow your certificate of occupancy deadline. Who is pricing your flooring scope here?"
        ),
        "value_proposition": "Night/weekend crews, rapid self-leveling pours, commercial COI with additional insured endorsement, 0 schedule slippage.",
        "collateral_checklist": [
            "Commercial LVP 20mil architectural binder",
            "AC4/AC5 heavy-traffic spec documentation",
            "COI with $2M aggregate commercial liability",
            "Standard subcontract W-9 & trade references"
        ]
    },
    FlooringTargetPersona.HIGH_END_DESIGNER: {
        "title": "High-End Interior Designer & Specifier",
        "tag": "luxury-designer",
        "description": "Interior designers and architectural consultants who dictate material selections for luxury renovations and demand perfection.",
        "primary_materials": "Select Grade Wire-Brushed French Oak, Custom Stains, Hand-Scraped Walnut, Custom Inlays",
        "est_material_rate": 8.00,
        "est_labor_rate": 5.50,
        "subfloor_prep_rate": 1.00,
        "sqft_coverage_ratio": 0.70,
        "sprint_pitch": (
            "Hello {contact}, {rep_name} from {company_name}. We partner with luxury design firms to execute exact custom "
            "stain matching and wide-plank installations with zero client drama. We'd love to drop off our curated 2026 designer box."
        ),
        "value_proposition": "Custom on-site stain samples, white-glove clean jobsite protocol, direct architect coordination, flawless bevel transitions.",
        "collateral_checklist": [
            "Handcrafted boutique wood species box (Wire-Brushed, Reactive Stains)",
            "Luxury lookbook with high-resolution macro photography",
            "Direct cell for dedicated trade concierge",
            "Client sample delivery service agreement"
        ]
    },
    FlooringTargetPersona.VOLUME_FLIPPER: {
        "title": "Volume Real Estate Flipper / Investor",
        "tag": "volume-flipper",
        "description": "Real estate investors and turnkey operators cycling 5-10 properties per quarter needing fast, budget-predictable installations.",
        "primary_materials": "12-20mil Waterproof Rigid Core SPC LVP, Builder Grade Engineered Oak",
        "est_material_rate": 2.80,
        "est_labor_rate": 2.10,
        "subfloor_prep_rate": 0.40,
        "sqft_coverage_ratio": 0.80,
        "sprint_pitch": (
            "Hey {contact}, {rep_name} with {company_name}. We do turnkey volume LVP and hardwoods for active investors across the county. "
            "We supply and install in under 48 hours at flat contractor rates so your money isn't sitting idle. What's your target finish date?"
        ),
        "value_proposition": "Turnkey material + labor packages, 48-hour install turnaround, investor volume discount tiers, no-nonsense billing.",
        "collateral_checklist": [
            "Turnkey Investor Price Sheet (Material + Labor per sq ft)",
            "Standard 3-Color Top Seller Ring (Grey Oak, Natural Honey, Warm Walnut)",
            "Digital lockbox dispatch protocol"
        ]
    },
    FlooringTargetPersona.GENERAL_RESIDENTIAL: {
        "title": "General Residential Remodel",
        "tag": "residential-remodel",
        "description": "Standard residential renovations and homeowner additions requiring dependable craftsmanship.",
        "primary_materials": "Solid Hardwood, Premium LVP, Carpet Replacement",
        "est_material_rate": 3.75,
        "est_labor_rate": 3.00,
        "subfloor_prep_rate": 0.50,
        "sqft_coverage_ratio": 0.75,
        "sprint_pitch": (
            "Hi {contact}, {rep_name} with {company_name}. We're working on a home right down the street and noticed your renovation permit. "
            "Are you looking to keep your existing subfloors or upgrade to durable new hardwoods?"
        ),
        "value_proposition": "Family-owned reliability, dustless sanding, lifetime installation warranty, honest upfront pricing.",
        "collateral_checklist": [
            "Trade portfolio & consumer finish brochure",
            "Local references & Google review QR card",
            "Turnkey estimate sheet"
        ]
    }
}


@dataclass
class FlooringLeadInput:
    address: str
    lead_id: str = field(default_factory=lambda: f"lead_{uuid.uuid4().hex[:8]}")
    contractor_name: str = ""
    permit_type: str = ""
    valuation: float = 0.0
    total_sqft: float = 0.0
    description: str = ""
    phone: str = ""
    email: str = ""
    source: str = "arcgis_permits"
    city: str = ""
    county: str = ""
    issue_date: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TurnkeyTakeoff:
    flooring_sqft: float
    material_type: str
    material_rate_per_sqft: float
    labor_rate_per_sqft: float
    subfloor_prep_rate_per_sqft: float
    est_material_total: float
    est_labor_total: float
    est_prep_total: float
    est_total_bid: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TargetedFlooringLead:
    lead_id: str
    persona: FlooringTargetPersona
    persona_label: str
    tag: str
    confidence_score: int
    matching_signals: List[str]
    input_data: FlooringLeadInput
    takeoff: TurnkeyTakeoff
    pitch_script: str
    value_proposition: str
    collateral_checklist: List[str]
    recommended_phase: str = "Phase 1: Inbound Lead Capture"

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["persona"] = self.persona.value
        return res


class FlooringTargetEngine:
    """Core algorithmic engine for scoring, classifying, and pricing flooring leads."""

    COMMERCIAL_KEYWORDS = {
        "commercial", "retail", "restaurant", "suite", "medical", "clinic", "office",
        "tenant", "buildout", "upfit", "warehouse", "store", "salon", "hospitality",
        "cafe", "brewery", "church", "school", "facility"
    }

    CUSTOM_BUILDER_KEYWORDS = {
        "custom", "estate", "single family", "sfd", "new dwelling", "addition",
        "luxury", "mansion", "residence", "high end", "spec", "builder", "homes",
        "craftsman", "architectural", "detached"
    }

    DESIGNER_KEYWORDS = {
        "interior design", "designer", "architect", "finishes", "custom remodel",
        "renovation", "interior alteration", "historic", "aesthetic", "decor"
    }

    FLIPPER_KEYWORDS = {
        "flip", "rehab", "as-is", "investor", "holdings", "properties llc", "capital",
        "turnkey", "quick turn", "residential alteration", "repair", "remodel"
    }

    @classmethod
    def calculate_takeoff(
        cls,
        persona: FlooringTargetPersona,
        total_sqft: float,
        valuation: float
    ) -> TurnkeyTakeoff:
        """Computes turnkey material, labor, and subfloor prep pricing."""
        profile = PERSONA_PROFILES[persona]
        coverage_ratio = profile["sqft_coverage_ratio"]

        # If total_sqft is missing or unreasonable, infer from valuation heuristics
        if total_sqft <= 0:
            if valuation > 0:
                sqft_factor = 250.0 if persona == FlooringTargetPersona.CUSTOM_HOME_BUILDER else 180.0
                total_sqft = max(600.0, min(12000.0, valuation / sqft_factor))
            else:
                total_sqft = 2200.0  # Industry median for single family / small commercial

        flooring_sqft = round(total_sqft * coverage_ratio, 1)
        # Cap flooring sqft to realistic jobsite boundaries
        flooring_sqft = max(200.0, flooring_sqft)

        mat_rate = profile["est_material_rate"]
        lab_rate = profile["est_labor_rate"]
        prep_rate = profile["subfloor_prep_rate"]

        mat_total = round(flooring_sqft * mat_rate, 2)
        lab_total = round(flooring_sqft * lab_rate, 2)
        prep_total = round(flooring_sqft * prep_rate, 2)
        total_bid = round(mat_total + lab_total + prep_total, 2)

        return TurnkeyTakeoff(
            flooring_sqft=flooring_sqft,
            material_type=profile["primary_materials"],
            material_rate_per_sqft=mat_rate,
            labor_rate_per_sqft=lab_rate,
            subfloor_prep_rate_per_sqft=prep_rate,
            est_material_total=mat_total,
            est_labor_total=lab_total,
            est_prep_total=prep_total,
            est_total_bid=total_bid
        )

    @classmethod
    def classify_lead(
        cls,
        lead: FlooringLeadInput,
        company_name: str = "PlankMap Partner",
        rep_name: str = "Estimator"
    ) -> TargetedFlooringLead:
        """Classifies a lead into one of the 4 personas using multi-factor heuristics."""
        text_corpus = f"{lead.description} {lead.permit_type} {lead.contractor_name}".lower()
        signals: List[str] = []

        scores: Dict[FlooringTargetPersona, float] = {
            FlooringTargetPersona.CUSTOM_HOME_BUILDER: 0.0,
            FlooringTargetPersona.COMMERCIAL_PM: 0.0,
            FlooringTargetPersona.HIGH_END_DESIGNER: 0.0,
            FlooringTargetPersona.VOLUME_FLIPPER: 0.0,
            FlooringTargetPersona.GENERAL_RESIDENTIAL: 10.0  # Base fallback score
        }

        # 1. Commercial Keyword Analysis
        comm_matches = [w for w in cls.COMMERCIAL_KEYWORDS if re.search(rf"\b{re.escape(w)}\b", text_corpus)]
        is_commercial = bool(comm_matches) or "commercial" in lead.permit_type.lower()
        if comm_matches:
            scores[FlooringTargetPersona.COMMERCIAL_PM] += len(comm_matches) * 25.0
            signals.append(f"Commercial keywords detected: {', '.join(comm_matches[:3])}")

        if is_commercial and lead.valuation >= 200000.0:
            scores[FlooringTargetPersona.COMMERCIAL_PM] += 30.0
            signals.append(f"High commercial project valuation (${lead.valuation:,.0f})")

        # 2. High-End Designer Analysis (Check before custom builder to give designer priority when entity is design/architecture firm)
        designer_matches = [w for w in cls.DESIGNER_KEYWORDS if re.search(rf"\b{re.escape(w)}\b", text_corpus)]
        if designer_matches:
            scores[FlooringTargetPersona.HIGH_END_DESIGNER] += len(designer_matches) * 20.0
            signals.append(f"Designer keywords: {', '.join(designer_matches[:3])}")

        if any(term in lead.contractor_name.lower() for term in ("design", "architect", "interiors", "atelier", "studio")):
            scores[FlooringTargetPersona.HIGH_END_DESIGNER] += 60.0
            signals.append("Contractor/Entity represents design/architecture practice")

        # 3. Custom Home Builder Valuation & Keyword Analysis (Only if not explicitly commercial)
        if not is_commercial:
            if lead.valuation >= 800000.0:
                scores[FlooringTargetPersona.CUSTOM_HOME_BUILDER] += 50.0
                signals.append(f"High residential permit valuation (${lead.valuation:,.0f} >= $800k)")
            elif lead.valuation >= 400000.0:
                scores[FlooringTargetPersona.CUSTOM_HOME_BUILDER] += 25.0
                signals.append(f"Solid residential valuation (${lead.valuation:,.0f})")

            builder_matches = [w for w in cls.CUSTOM_BUILDER_KEYWORDS if re.search(rf"\b{re.escape(w)}\b", text_corpus)]
            if builder_matches:
                scores[FlooringTargetPersona.CUSTOM_HOME_BUILDER] += len(builder_matches) * 15.0
                signals.append(f"Custom builder keywords: {', '.join(builder_matches[:3])}")

        # 4. Volume Real Estate Flipper Analysis
        flipper_matches = [w for w in cls.FLIPPER_KEYWORDS if re.search(rf"\b{re.escape(w)}\b", text_corpus)]
        if flipper_matches:
            scores[FlooringTargetPersona.VOLUME_FLIPPER] += len(flipper_matches) * 15.0

        # Investor LLC patterns (e.g., 'Oak Creek Holdings LLC', 'Triad Flippers LLC')
        if re.search(r"\b(properties|holdings|investments|capital|homes llc|ventures)\b", lead.contractor_name.lower()):
            scores[FlooringTargetPersona.VOLUME_FLIPPER] += 35.0
            signals.append(f"Investor/Holding corporate name signature: '{lead.contractor_name}'")

        if 20000.0 <= lead.valuation <= 120000.0 and ("remodel" in text_corpus or "alteration" in text_corpus) and not is_commercial:
            scores[FlooringTargetPersona.VOLUME_FLIPPER] += 20.0
            signals.append(f"Moderate valuation range typical of investor flips (${lead.valuation:,.0f})")

        # Select winner
        best_persona = max(scores, key=lambda k: scores[k])
        raw_score = scores[best_persona]
        confidence = min(98, max(50, int(raw_score)))

        profile = PERSONA_PROFILES[best_persona]
        contact_name = lead.contractor_name or "there"
        pitch = profile["sprint_pitch"].format(
            contact=contact_name,
            company_name=company_name,
            rep_name=rep_name
        )

        takeoff = cls.calculate_takeoff(best_persona, lead.total_sqft, lead.valuation)

        checklist = list(profile["collateral_checklist"])
        # If phone is missing, prepend the guerrilla sprint priority
        if not lead.phone or lead.phone == "No Phone":
            checklist.insert(0, "🚨 SPRINT ACTION: Walk on-site and get Superintendent direct mobile number")

        return TargetedFlooringLead(
            lead_id=lead.lead_id,
            persona=best_persona,
            persona_label=profile["title"],
            tag=profile["tag"],
            confidence_score=confidence,
            matching_signals=signals or ["Standard residential permit parameters"],
            input_data=lead,
            takeoff=takeoff,
            pitch_script=pitch,
            value_proposition=profile["value_proposition"],
            collateral_checklist=checklist,
            recommended_phase="Phase 1: Inbound Lead Capture"
        )

    @classmethod
    def format_kanban_card(cls, targeted: TargetedFlooringLead) -> Dict[str, Any]:
        """Formats the classified lead into a comprehensive Kenbun / Planka card payload."""
        lead = targeted.input_data
        takeoff = targeted.takeoff

        title = f"[{targeted.tag.upper()}] {lead.address} — {lead.contractor_name or 'Unassigned Lead'}"

        body_lines = [
            f"## 🎯 Targeted Persona: {targeted.persona_label}",
            f"**Confidence Match:** `{targeted.confidence_score}%` | **Tag:** `#{targeted.tag}`",
            "",
            "### 📍 Site & Contact Information",
            f"* **Address:** `{lead.address}` ({lead.city or 'Local'}, {lead.county or 'NC'})",
            f"* **Contractor / Entity:** `{lead.contractor_name or 'Unknown (Field Recon Required)'}`",
            f"* **Phone:** `{lead.phone or '⚠️ Unlisted — capture in 60-min sprint'}`",
            f"* **Permit Type:** `{lead.permit_type}` | **Issue Date:** `{lead.issue_date or 'Recent'}`",
            f"* **Permit Valuation:** `${lead.valuation:,.2f}`",
            "",
            "### 📐 Automated Turnkey Takeoff (PlankMap AI)",
            f"* **Estimated Flooring Area:** `{takeoff.flooring_sqft:,.1f} sq ft`",
            f"* **Recommended Material:** `{takeoff.material_type}` (${takeoff.material_rate_per_sqft:.2f}/sqft)",
            f"* **Installation Labor:** `${takeoff.labor_rate_per_sqft:.2f}/sqft`",
            f"* **Subfloor Leveling & Prep:** `${takeoff.subfloor_prep_rate_per_sqft:.2f}/sqft`",
            f"* **Total Estimated Turnkey Contract:** **`${takeoff.est_total_bid:,.2f}`**",
            "",
            "### 🎙️ 60-Minute Sprint Elevator Pitch",
            f"> *\"{targeted.pitch_script}\"*",
            "",
            "### 💼 Value Proposition",
            f"{targeted.value_proposition}",
            "",
            "### 🛠️ Field Sprint Checklist",
        ]

        for item in targeted.collateral_checklist:
            body_lines.append(f"- [ ] {item}")

        body_lines.extend([
            "",
            "### 🧠 Match Signals & Rationale",
        ])
        for sig in targeted.matching_signals:
            body_lines.append(f"* {sig}")

        return {
            "title": title,
            "body": "\n".join(body_lines),
            "assignee": "field_contractor",
            "tenant": "flooring",
            "priority": 1 if targeted.confidence_score >= 75 else 0,
            "status": "todo",
            "metadata": {
                "persona": targeted.persona.value,
                "lead_id": targeted.lead_id,
                "total_bid": takeoff.est_total_bid,
                "flooring_sqft": takeoff.flooring_sqft,
                "confidence": targeted.confidence_score
            }
        }
