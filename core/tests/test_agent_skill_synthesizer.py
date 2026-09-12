"""
Unit tests for Autonomous Agent & Skill Synthesizer.
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.strategy.agent_skill_synthesizer import AgentSkillSynthesizer


class TestAgentSkillSynthesizer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        
        # Create mock directories
        (self.root / ".agents" / "skills").mkdir(parents=True)
        (self.root / "core" / "tools" / "strategy").mkdir(parents=True)
        (self.root / "brain_health").mkdir(parents=True)

        # Mock SKILLS_REGISTRY.md
        self.registry_file = self.root / "core" / "SKILLS_REGISTRY.md"
        self.registry_file.write_text(
            "# 🏛️ Kenbun Master Skills Registry\n\n"
            "This document is the sovereign catalog of all 29 specialized agent skills.\n\n"
            "## 📦 Complete Inventory of All 29 Skills\n\n"
            "| # | Skill Identifier | Primary Mission | Tools |\n"
            "|---|---|---|---|\n"
            "| 1 | [`test-skill`](SKILL.md) | Test skill | Tools |\n"
        )

        # Mock keyword_processor.py
        self.keyword_file = self.root / "core" / "tools" / "strategy" / "keyword_processor.py"
        self.keyword_file.write_text(
            "class KeywordProcessor:\n"
            "    def __init__(self):\n"
            "        self.keywords = {\n"
            '            "ui": ["css", "style"],\n'
            '            "security": ["auth", "jwt"]\n'
            "        }\n"
        )

        self.synthesizer = AgentSkillSynthesizer(project_root=self.root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_discover_agent_gaps(self):
        gaps = self.synthesizer.discover_agent_gaps()
        self.assertIsInstance(gaps, list)
        self.assertGreater(len(gaps), 0)
        # Verify software-decision-architect is among high-priority candidates
        names = [g["name"] for g in gaps]
        self.assertIn("software-decision-architect", names)

    def test_synthesize_skill(self):
        spec = {
            "name": "test-evaluator",
            "domain": "voice_ai",
            "title": "Test Evaluator Sentinel",
            "description": "Autonomous test evaluator for voice calls.",
            "triggers": ["evaluating test voice calls"],
            "sops": [{"title": "1. Test SOP", "content": "Execute test."}],
            "keywords": ["test eval", "call test"]
        }

        res = self.synthesizer.synthesize_skill(spec)
        self.assertEqual(res["name"], "test-evaluator")
        
        skill_md = Path(res["skill_md_path"])
        self.assertTrue(skill_md.exists())
        content = skill_md.read_text()
        self.assertIn("name: test-evaluator", content)
        self.assertIn("# 🛡️ Test Evaluator Sentinel", content)

    def test_verify_skill_valid(self):
        spec = {
            "name": "valid-sentinel",
            "domain": "telemetry",
            "title": "Valid Sentinel",
            "description": "Autonomous valid sentinel.",
            "triggers": ["checking valid telemetry"],
            "keywords": ["valid kw"]
        }
        self.synthesizer.synthesize_skill(spec)
        v_res = self.synthesizer.verify_skill("valid-sentinel")
        self.assertTrue(v_res["valid"])
        self.assertEqual(v_res["score"], 1.0)
        self.assertEqual(len(v_res["errors"]), 0)

    def test_verify_skill_invalid(self):
        # Create malformed skill
        bad_dir = self.synthesizer.skills_dir / "bad-skill"
        bad_dir.mkdir(parents=True)
        bad_md = bad_dir / "SKILL.md"
        bad_md.write_text("No frontmatter content")

        v_res = self.synthesizer.verify_skill("bad-skill")
        self.assertFalse(v_res["valid"])
        self.assertGreater(len(v_res["errors"]), 0)

    def test_promote_and_register(self):
        spec = {
            "name": "promoted-skill",
            "domain": "voice_ai",
            "title": "Promoted Skill",
            "description": "Skill promoted to registry.",
            "keywords": ["voice stream", "turn taking"]
        }
        self.synthesizer.synthesize_skill(spec)
        p_res = self.synthesizer.promote_and_register("promoted-skill", spec)

        self.assertTrue(p_res["registry_updated"])
        self.assertTrue(p_res["keywords_injected"])
        self.assertTrue(p_res["evolution_logged"])

        # Check registry content
        reg_text = self.registry_file.read_text()
        self.assertIn("catalog of all 2 specialized agent skills", reg_text)
        self.assertIn("promoted-skill", reg_text)

        # Check keyword processor content
        kp_text = self.keyword_file.read_text()
        self.assertIn("voice_ai", kp_text)
        self.assertIn("voice stream", kp_text)

    def test_full_evolution_cycle(self):
        cycle_res = self.synthesizer.run_evolution_cycle(max_candidates=1, dry_run=False)
        self.assertEqual(cycle_res["status"], "completed")
        self.assertEqual(cycle_res["synthesized_count"], 1)
        skill = cycle_res["skills"][0]
        self.assertEqual(skill["status"], "promoted")
        self.assertEqual(skill["score"], 1.0)


if __name__ == "__main__":
    unittest.main()
