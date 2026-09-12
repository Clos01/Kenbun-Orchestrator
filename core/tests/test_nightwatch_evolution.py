"""
Test Nightwatch Autonomous Evolution & Refactor Engine
=====================================================
Validates Transcript & Intent Mining, Core Refactoring,
and Autonomous Skill Synthesis for Kenbun Nightwatch.
"""

import unittest
from pathlib import Path
import tempfile
import json
import ast

from tools.strategy.transcript_intent_miner import TranscriptIntentMiner
from tools.strategy.core_refactor_cleaner import CoreRefactorCleaner
from tools.strategy.agent_skill_synthesizer import AgentSkillSynthesizer


class TestNightwatchEvolution(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.brain_dir = self.tmp_path / "brain"
        self.brain_dir.mkdir(parents=True, exist_ok=True)
        self.project_root = self.tmp_path / "Kenbun"
        self.project_root.mkdir(parents=True, exist_ok=True)
        self.core_dir = self.project_root / "core"
        self.core_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir = self.project_root / ".agents" / "skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_transcript_mining(self):
        # Create a mock transcript with user request
        conv_dir = self.brain_dir / "conv1" / ".system_generated" / "logs"
        conv_dir.mkdir(parents=True, exist_ok=True)
        transcript_file = conv_dir / "transcript.jsonl"
        
        sample_entries = [
            {"type": "USER_INPUT", "content": "<USER_REQUEST>How do we evaluate voice agent latency in real-time with Elevenlabs?</USER_REQUEST>"},
            {"type": "USER_INPUT", "content": "<USER_REQUEST>Check our Pi-hole and Tailscale mesh cluster</USER_REQUEST>"}
        ]
        with open(transcript_file, "w") as f:
            for entry in sample_entries:
                f.write(json.dumps(entry) + "\n")

        miner = TranscriptIntentMiner(brain_dir=self.brain_dir, project_root=self.project_root)
        transcripts = miner.get_recent_transcripts(lookback_hours=24)
        self.assertEqual(len(transcripts), 1)

        queries = miner.extract_user_queries(transcripts[0])
        self.assertEqual(len(queries), 2)
        self.assertIn("Elevenlabs", queries[0])

        gaps = miner.mine_capability_gaps(lookback_hours=24)
        gap_names = [g["name"] for g in gaps]
        self.assertIn("voice-agent-latency-evaluator", gap_names)
        self.assertIn("homelab-mesh-dns-governor", gap_names)

    def test_core_refactor_cleaner(self):
        # Create a mock python file with trailing spaces and extra lines
        test_file = self.core_dir / "sample.py"
        with open(test_file, "w") as f:
            f.write("import os\nimport sys\n\n\n\ndef hello():   \n    return 42   \n")

        cleaner = CoreRefactorCleaner(project_root=self.project_root)
        analysis = cleaner.scan_file_complexity(test_file)
        self.assertEqual(analysis["functions"], 1)

        changed, msg = cleaner.clean_file_formatting(test_file, dry_run=False)
        self.assertTrue(changed)

        with open(test_file) as f:
            cleaned_content = f.read()
        self.assertNotIn("   \n", cleaned_content)
        # Verify valid AST
        ast.parse(cleaned_content)


if __name__ == "__main__":
    unittest.main()
