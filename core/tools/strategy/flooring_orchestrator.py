"""
Flooring Lead Orchestrator & Board Provisioning Pipeline.

Chains the FlooringTargetEngine with Kenbun Sovereign Kanban and Planka CRM:
1. Ingests raw building permit / jobsite leads.
2. Classifies leads into the 4 B2B Contractor Archetypes.
3. Calculates automated turnkey take-offs (material + labor + prep).
4. Provisions Kanban cards across the 8-Phase Business Pipeline.
5. Injects automated audit comments with match rationale, field sprint checklists,
   and Tier-3 anti-patterns / learnings.
"""

from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# Ensure core is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "core") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "core"))

from tools.strategy.flooring_target_engine import (
    FlooringTargetEngine,
    FlooringLeadInput,
    TargetedFlooringLead,
    FlooringTargetPersona
)
from tools.strategy.kanban_tools import (
    kanban_create,
    kanban_comment
)


SAMPLE_PERMIT_BATCH: List[Dict[str, Any]] = [
    {
        "address": "100 Grandview Way, Suite 100, Metro 10001",
        "contractor_name": "Grandview Custom Homes LLC",
        "permit_type": "New Single Family Dwelling",
        "valuation": 1450000.0,
        "total_sqft": 5200.0,
        "description": "New custom luxury residential construction, 2-story with finished basement, open floor plan, framing stage",
        "phone": "919-555-0144",
        "city": "Cary",
        "county": "Wake",
        "issue_date": "2026-08-14"
    },
    {
        "address": "200 Commerce Blvd, Suite 200, Metro 10002",
        "contractor_name": "Apex Commercial Builders Inc",
        "permit_type": "Commercial Interior Alteration",
        "valuation": 280000.0,
        "total_sqft": 3400.0,
        "description": "Commercial tenant upfit for new boutique dental clinic and medical consultation suites, self-leveling required",
        "phone": "919-555-0288",
        "city": "Raleigh",
        "county": "Wake",
        "issue_date": "2026-08-22"
    },
    {
        "address": "300 Heritage Dr, Metro 10003",
        "contractor_name": "Atelier Modern Interior Design & Architecture",
        "permit_type": "Residential Alteration / Addition",
        "valuation": 420000.0,
        "total_sqft": 2800.0,
        "description": "High-end bespoke interior architecture remodel, custom French oak specification, luxury bathroom and kitchen expansion",
        "phone": "",  # Unlisted phone test case
        "city": "Wake Forest",
        "county": "Wake",
        "issue_date": "2026-08-30"
    },
    {
        "address": "400 Downtown Ave, Metro 10004",
        "contractor_name": "Tarheel Capital Properties LLC",
        "permit_type": "Residential Alteration",
        "valuation": 65000.0,
        "total_sqft": 1650.0,
        "description": "Turnkey rehab and flip of 1960s ranch, structural repair and full interior cosmetic renovation for quick resale",
        "phone": "919-555-0812",
        "city": "Raleigh",
        "county": "Wake",
        "issue_date": "2026-09-02"
    }
]


class FlooringPipelineOrchestrator:
    """Orchestrates the lifecycle from permit discovery to Kanban board tracking."""

    @classmethod
    def run_pipeline(
        cls,
        leads_raw: Optional[List[Dict[str, Any]]] = None,
        tenant: str = "flooring"
    ) -> Dict[str, Any]:
        """Runs the complete classification, takeoff, and Kanban board provisioning pipeline."""
        if leads_raw is None:
            leads_raw = SAMPLE_PERMIT_BATCH

        results: List[Dict[str, Any]] = []
        created_task_ids: List[str] = []

        print(f"\n🚀 [FLOORING ORCHESTRATOR] Processing {len(leads_raw)} incoming permits/leads...")

        for idx, raw in enumerate(leads_raw, start=1):
            # 1. Ingest into Input Model
            lead_input = FlooringLeadInput(
                address=raw.get("address", "Unknown Address"),
                contractor_name=raw.get("contractor_name", ""),
                permit_type=raw.get("permit_type", ""),
                valuation=float(raw.get("valuation", 0.0)),
                total_sqft=float(raw.get("total_sqft", 0.0)),
                description=raw.get("description", ""),
                phone=raw.get("phone", ""),
                email=raw.get("email", ""),
                city=raw.get("city", ""),
                county=raw.get("county", ""),
                issue_date=raw.get("issue_date", ""),
                metadata=raw
            )

            # 2. Classify Persona & Compute Turnkey Take-Off
            targeted = FlooringTargetEngine.classify_lead(lead_input)
            card_payload = FlooringTargetEngine.format_kanban_card(targeted)

            # 3. Provision Task in Sovereign Kanban DB
            create_res = kanban_create(
                title=card_payload["title"],
                body=card_payload["body"],
                assignee=card_payload["assignee"],
                tenant=tenant,
                priority=card_payload["priority"],
                status="todo"
            )
            try:
                res_obj = json.loads(create_res) if isinstance(create_res, str) else create_res
                real_task_id = res_obj.get("id", create_res)
            except Exception:
                real_task_id = str(create_res)
            created_task_ids.append(real_task_id)

            # 4. Ingest Telemetry & Tactical Audit Comments
            cls._attach_audit_comments(real_task_id, targeted)

            results.append({
                "task_id": real_task_id,
                "address": lead_input.address,
                "contractor": lead_input.contractor_name,
                "persona": targeted.persona.value,
                "persona_label": targeted.persona_label,
                "confidence": targeted.confidence_score,
                "flooring_sqft": targeted.takeoff.flooring_sqft,
                "est_total_bid": targeted.takeoff.est_total_bid,
                "status": "PROVISIONED_ON_KANBAN"
            })

            print(f"  [{idx}/{len(leads_raw)}] ✅ Provisioned: {real_task_id} | {targeted.persona_label} | ${targeted.takeoff.est_total_bid:,.2f}")

        summary = {
            "status": "SUCCESS",
            "total_processed": len(results),
            "created_task_ids": created_task_ids,
            "tasks": results
        }
        return summary

    @classmethod
    def _attach_audit_comments(cls, task_id: str, targeted: TargetedFlooringLead):
        """Attaches structured audit, tactical execution, and Tier-3 anti-pattern comments."""
        lead = targeted.input_data
        takeoff = targeted.takeoff

        # Comment 1: Turnkey Takeoff & Algorithmic Scoring
        comment_1 = (
            f"### 📊 Turnkey Take-Off & Algorithmic Rationale\n"
            f"- **Persona Match:** `{targeted.persona_label}` ({targeted.confidence_score}% confidence)\n"
            f"- **Calculated Flooring Scope:** `{takeoff.flooring_sqft:,.1f} sq ft` (from {lead.total_sqft:,.0f} conditioned sqft)\n"
            f"- **Material Spec:** `{takeoff.material_type}` @ `${takeoff.material_rate_per_sqft:.2f}/sqft` (${takeoff.est_material_total:,.2f})\n"
            f"- **Labor Rate:** `${takeoff.labor_rate_per_sqft:.2f}/sqft` (${takeoff.est_labor_total:,.2f})\n"
            f"- **Subfloor Prep:** `${takeoff.subfloor_prep_rate_per_sqft:.2f}/sqft` (${takeoff.est_prep_total:,.2f})\n"
            f"- **Est. Contract Gross:** **`${takeoff.est_total_bid:,.2f}`**\n"
            f"- **Signals:** {', '.join(targeted.matching_signals)}"
        )
        kanban_comment(task_id, comment_1)

        # Comment 2: 60-Minute Sprint Execution Plan
        comment_2 = (
            f"### 🏃 60-Minute Sprint Action Directive\n"
            f"- **Target Contact:** `{lead.contractor_name or 'Superintendent on Site'}`\n"
            f"- **Sprint Script:** *\"{targeted.pitch_script}\"*\n"
            f"- **Action Required:** Approach trailer during active rough-in/framing stage.\n"
            f"- **Hand-Off:** Present sample package, collect super's direct cell, confirm target finish date."
        )
        kanban_comment(task_id, comment_2)

        # Comment 3: Tier 3 Anti-Patterns & Mistakes to Avoid (System 3 Learnings)
        mistakes_to_avoid = cls._get_mistakes_for_persona(targeted.persona)
        comment_3 = (
            f"### 🛡️ Mistake Prevention & Anti-Pattern Sentinel\n"
            f"{mistakes_to_avoid}"
        )
        kanban_comment(task_id, comment_3)

    @classmethod
    def _get_mistakes_for_persona(cls, persona: FlooringTargetPersona) -> str:
        """Returns specific anti-patterns and learnings for each persona."""
        if persona == FlooringTargetPersona.CUSTOM_HOME_BUILDER:
            return (
                "* ❌ **Mistake:** Pitching cheap builder-grade LVP or standard thin engineered wood. Luxury GCs immediately dismiss subs who don't understand 7\"+ European white oak, flush vents, and stair nosing details.\n"
                "* 💡 **Learning:** Always bring a physical, heavy wire-brushed sample board and prove subfloor moisture testing compliance (ASTM F2170)."
            )
        elif persona == FlooringTargetPersona.COMMERCIAL_PM:
            return (
                "* ❌ **Mistake:** Offering standard daytime-only residential install schedules. Commercial PMs operate under strict liquidated damages and tenant turnover deadlines.\n"
                "* 💡 **Learning:** Emphasize weekend/night crew availability, rapid self-leveling pours, and immediate submission of $2M Commercial COI with project-specific endorsements."
            )
        elif persona == FlooringTargetPersona.HIGH_END_DESIGNER:
            return (
                "* ❌ **Mistake:** Rushing the consultation with generic pricing per square foot without discussing custom stain matching or transition details.\n"
                "* 💡 **Learning:** Present the curated boutique designer sample box, offer on-site custom stain strike-offs, and promise white-glove clean jobsite protocol."
            )
        elif persona == FlooringTargetPersona.VOLUME_FLIPPER:
            return (
                "* ❌ **Mistake:** Quoting high-end custom rates or long 3-week lead times. Investors only care about holding costs, speed, durability, and predictability.\n"
                "* 💡 **Learning:** Provide flat turnkey material+labor pricing, 48-hour installation mobilization, and frictionless digital lockbox coordination."
            )
        return "* 💡 **Learning:** Confirm subfloor condition and existing flooring tear-out scope before final sign-off."


def run_cli():
    import argparse
    parser = argparse.ArgumentParser(description="Flooring Lead Orchestrator CLI")
    parser.add_argument("--run-sample", action="store_true", help="Run sample permit batch")
    parser.add_argument("--tenant", default="flooring", help="Kanban tenant ID")
    args = parser.parse_args()

    if args.run_sample:
        res = FlooringPipelineOrchestrator.run_pipeline(tenant=args.tenant)
        print("\n=== PIPELINE RUN COMPLETE ===")
        print(json.dumps(res, indent=2))
    else:
        print("Usage: python flooring_orchestrator.py --run-sample")


if __name__ == "__main__":
    run_cli()
