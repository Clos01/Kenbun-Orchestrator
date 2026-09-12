"""
Unit and Edge-Case Test Suite for the Flooring Target Engine & Orchestrator.
"""

import unittest
import sys
from pathlib import Path

# Add core and root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "core"))

from tools.strategy.flooring_target_engine import (
    FlooringTargetEngine,
    FlooringLeadInput,
    FlooringTargetPersona,
    PERSONA_PROFILES
)
from tools.strategy.flooring_orchestrator import FlooringPipelineOrchestrator


class TestFlooringTargetEngine(unittest.TestCase):

    def test_custom_home_builder_classification(self):
        lead = FlooringLeadInput(
            address="104 Meadow View Ct, Cary, NC",
            contractor_name="Heritage Custom Builders LLC",
            permit_type="New Single Family Dwelling",
            valuation=1500000.0,
            total_sqft=5400.0,
            description="Custom luxury estate residence with open layout and 3-car garage, rough framing complete",
            phone="919-555-1122"
        )
        targeted = FlooringTargetEngine.classify_lead(lead)
        self.assertEqual(targeted.persona, FlooringTargetPersona.CUSTOM_HOME_BUILDER)
        self.assertGreaterEqual(targeted.confidence_score, 70)
        self.assertIn("custom-builder", targeted.tag)
        self.assertIn("European White Oak", targeted.takeoff.material_type)
        # 5400 * 0.75 = 4050 sq ft
        self.assertEqual(targeted.takeoff.flooring_sqft, 4050.0)
        self.assertGreater(targeted.takeoff.est_total_bid, 40000.0)

    def test_commercial_pm_classification(self):
        lead = FlooringLeadInput(
            address="500 Fayetteville St #200, Metropolitan Area",
            contractor_name="Summit Commercial Contracting",
            permit_type="Commercial Interior Alteration",
            valuation=320000.0,
            total_sqft=4000.0,
            description="Tenant upfit for Italian restaurant and bar, kitchen tile and commercial LVP dining room",
            phone="919-555-3344"
        )
        targeted = FlooringTargetEngine.classify_lead(lead)
        self.assertEqual(targeted.persona, FlooringTargetPersona.COMMERCIAL_PM)
        self.assertGreaterEqual(targeted.confidence_score, 70)
        self.assertIn("commercial-pm", targeted.tag)
        self.assertIn("Commercial Glue-Down LVP", targeted.takeoff.material_type)
        # 4000 * 0.65 = 2600 sq ft
        self.assertEqual(targeted.takeoff.flooring_sqft, 2600.0)

    def test_high_end_designer_classification(self):
        lead = FlooringLeadInput(
            address="220 Country Club Dr, Metropolitan Area",
            contractor_name="Vanguard Architecture & Interior Design",
            permit_type="Residential Addition / Remodel",
            valuation=480000.0,
            total_sqft=3200.0,
            description="Interior architecture redesign, bespoke finishes, custom wide-plank wood throughout main floor",
            phone="919-555-5566"
        )
        targeted = FlooringTargetEngine.classify_lead(lead)
        self.assertEqual(targeted.persona, FlooringTargetPersona.HIGH_END_DESIGNER)
        self.assertGreaterEqual(targeted.confidence_score, 70)
        self.assertIn("French Oak", targeted.takeoff.material_type)
        self.assertIn("boutique wood species box", targeted.collateral_checklist[0])

    def test_volume_flipper_classification(self):
        lead = FlooringLeadInput(
            address="714 E Martin St, Metropolitan Area",
            contractor_name="Triangle Turnkey Properties LLC",
            permit_type="Residential Alteration",
            valuation=58000.0,
            total_sqft=1400.0,
            description="Rehab and flip of single story cottage, full cosmetic upgrade and new floors for rapid sale",
            phone="919-555-7788"
        )
        targeted = FlooringTargetEngine.classify_lead(lead)
        self.assertEqual(targeted.persona, FlooringTargetPersona.VOLUME_FLIPPER)
        self.assertGreaterEqual(targeted.confidence_score, 70)
        self.assertIn("SPC LVP", targeted.takeoff.material_type)
        self.assertIn("48 hours", targeted.pitch_script)

    def test_edge_case_missing_sqft_fallback_to_valuation(self):
        # When total_sqft is 0, engine must estimate sqft from valuation without crashing
        lead = FlooringLeadInput(
            address="800 Pinehurst Way, Apex, NC",
            contractor_name="Apex Luxury Homes",
            permit_type="New Single Family",
            valuation=1000000.0,
            total_sqft=0.0,
            description="Custom new home construction"
        )
        targeted = FlooringTargetEngine.classify_lead(lead)
        self.assertEqual(targeted.persona, FlooringTargetPersona.CUSTOM_HOME_BUILDER)
        # $1,000,000 / 250 = 4,000 sq ft total -> 75% = 3,000 sq ft flooring
        self.assertEqual(targeted.takeoff.flooring_sqft, 3000.0)
        self.assertGreater(targeted.takeoff.est_total_bid, 0.0)

    def test_edge_case_missing_valuation_fallback_to_sqft(self):
        # When valuation is 0, engine must still compute takeoff from sqft
        lead = FlooringLeadInput(
            address="99 Commercial Blvd, Durham, NC",
            contractor_name="Durham Retail Upfits",
            permit_type="Commercial Tenant Upfit",
            valuation=0.0,
            total_sqft=2000.0,
            description="Retail store alteration"
        )
        targeted = FlooringTargetEngine.classify_lead(lead)
        self.assertEqual(targeted.persona, FlooringTargetPersona.COMMERCIAL_PM)
        self.assertEqual(targeted.takeoff.flooring_sqft, 1300.0)

    def test_edge_case_missing_phone_injects_sprint_action(self):
        lead = FlooringLeadInput(
            address="12 Hidden Creek Ln, Chapel Hill, NC",
            contractor_name="Carolina Custom Craftsmen",
            permit_type="New Residence",
            valuation=950000.0,
            total_sqft=4200.0,
            description="New custom single family dwelling",
            phone=""  # Missing phone
        )
        targeted = FlooringTargetEngine.classify_lead(lead)
        first_checklist_item = targeted.collateral_checklist[0]
        self.assertIn("SPRINT ACTION: Walk on-site and get Superintendent direct mobile number", first_checklist_item)

    def test_edge_case_extreme_values_sanitization(self):
        # Extreme tiny permit ($1,000 repair)
        small_lead = FlooringLeadInput(
            address="5 Small St, Metropolitan Area",
            valuation=1000.0,
            total_sqft=100.0,
            description="Minor repair"
        )
        small_res = FlooringTargetEngine.classify_lead(small_lead)
        # Minimum clamp at 200 sqft
        self.assertGreaterEqual(small_res.takeoff.flooring_sqft, 200.0)

        # Extreme mega development ($30M complex)
        mega_lead = FlooringLeadInput(
            address="1 Mega Tower Pl, Metropolitan Area",
            valuation=30000000.0,
            total_sqft=0.0,
            description="Commercial high-rise medical center"
        )
        mega_res = FlooringTargetEngine.classify_lead(mega_lead)
        # Capped to 12,000 max sqft heuristic * 0.65 = 7,800 sqft
        self.assertLessEqual(mega_res.takeoff.flooring_sqft, 8000.0)

    def test_format_kanban_card_schema(self):
        lead = FlooringLeadInput(
            address="123 Test St, Cary, NC",
            contractor_name="Test Builders",
            valuation=900000.0,
            total_sqft=3500.0,
            description="Custom estate residence"
        )
        targeted = FlooringTargetEngine.classify_lead(lead)
        card = FlooringTargetEngine.format_kanban_card(targeted)

        self.assertIn("title", card)
        self.assertIn("body", card)
        self.assertEqual(card["tenant"], "flooring")
        self.assertIn("[CUSTOM-BUILDER]", card["title"])
        self.assertIn("Automated Turnkey Takeoff", card["body"])


class TestFlooringOrchestrator(unittest.TestCase):

    def test_orchestrator_batch_execution(self):
        test_batch = [
            {
                "address": "901 Spec Lane, Apex, NC",
                "contractor_name": "Apex Custom Works",
                "permit_type": "New Single Family",
                "valuation": 1100000.0,
                "total_sqft": 4500.0,
                "description": "Luxury custom spec home",
                "phone": "919-555-0901"
            },
            {
                "address": "400 Main St, Wake Forest, NC",
                "contractor_name": "Wake Medical PM",
                "permit_type": "Commercial Alteration",
                "valuation": 210000.0,
                "total_sqft": 2500.0,
                "description": "Medical clinic upfit",
                "phone": "919-555-0400"
            }
        ]
        result = FlooringPipelineOrchestrator.run_pipeline(test_batch, tenant="test_flooring")
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["total_processed"], 2)
        self.assertEqual(len(result["created_task_ids"]), 2)


if __name__ == "__main__":
    unittest.main()
