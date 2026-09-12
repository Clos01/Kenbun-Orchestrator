"""
Transcript & Intent Miner (core/tools/strategy/transcript_intent_miner.py)
========================================================================
Autonomous intent mining engine that scans local conversation transcripts
from the last 24-48 hours, extracting recurring user requests, architectural
intentions, and capability gaps to synthesize forward-thinking agent skills.
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("tools.transcript_intent_miner")


class TranscriptIntentMiner:
    """
    Mines conversation transcripts from ~/.gemini/antigravity-cli/brain/
    to discover actionable domain gaps and propose new agent skills.
    """

    def __init__(self, brain_dir: Optional[Path] = None, project_root: Optional[Path] = None):
        self.brain_dir = brain_dir or (Path.home() / ".gemini" / "antigravity-cli" / "brain")
        self.project_root = project_root or Path(__file__).resolve().parent.parent.parent.parent
        self.skills_dir = self.project_root / ".agents" / "skills"

    def get_recent_transcripts(self, lookback_hours: float = 48.0) -> List[Path]:
        """Returns paths to transcript.jsonl modified within lookback_hours."""
        if not self.brain_dir.exists():
            return []

        recent = []
        now = time.time()
        for p in self.brain_dir.glob("*/.system_generated/logs/transcript.jsonl"):
            try:
                mtime = p.stat().st_mtime
                if (now - mtime) <= (lookback_hours * 3600):
                    recent.append(p)
            except Exception:
                continue
        return sorted(recent, key=lambda p: p.stat().st_mtime, reverse=True)

    def extract_user_queries(self, transcript_path: Path) -> List[str]:
        """Extracts clean text from USER_INPUT records in a transcript file."""
        queries = []
        try:
            with open(transcript_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    obj = json.loads(line)
                    if obj.get("type") == "USER_INPUT":
                        content = obj.get("content", "")
                        cleaned = re.sub(r"<[^>]+>", "", content).strip()
                        if cleaned:
                            queries.append(cleaned)
        except Exception as e:
            logger.warning(f"Error reading transcript {transcript_path}: {e}")
        return queries

    def get_existing_skills(self) -> Set[str]:
        """Returns the set of existing skill directory names."""
        skills = set()
        if self.skills_dir.exists():
            for p in self.skills_dir.iterdir():
                if p.is_dir() and (p / "SKILL.md").exists():
                    skills.add(p.name)
        return skills

    def mine_capability_gaps(self, lookback_hours: float = 48.0) -> List[Dict[str, Any]]:
        """
        Analyzes recent conversation logs, identifies recurring intentions,
        and returns structured skill blueprints for discovered capability gaps.
        """
        transcripts = self.get_recent_transcripts(lookback_hours=lookback_hours)
        all_queries: List[str] = []
        for t in transcripts:
            all_queries.extend(self.extract_user_queries(t))

        existing_skills = self.get_existing_skills()
        candidates: List[Dict[str, Any]] = []

        domain_patterns = [
            {
                "name": "epistemic-alignment-sentinel",
                "domain": "ai_safety",
                "title": "Epistemic Alignment & Red-Zone Safety Sentinel",
                "description": "Autonomous guardian enforcing strict boundaries against AI indifference, power-seeking, and unauthorized operational escalation.",
                "pattern": r"(indifference|ai safety|alignment|red.?zone|human boundaries|kill.?switch|anthill)",
                "priority": 96,
                "triggers": [
                    "enforcing AI alignment and safety guardrails",
                    "preventing agent indifference and autonomous drift",
                    "handling red-zone violations and supervisor gates"
                ],
                "keywords": ["ai safety", "alignment", "indifference", "red zone", "safety gate", "epistemic guardrail"],
                "sops": [
                    {"title": "1. Boundary & Policy Enforcement", "content": "Intercept actions violating operator intent or human boundary red-lines."},
                    {"title": "2. Epistemic Downshifting", "content": "Immediately drop capability tier upon safety challenge."},
                    {"title": "3. Operator Verification", "content": "Halt autonomous action and request supervisor attestation."}
                ]
            },
            {
                "name": "model-collapse-and-data-drift-sentinel",
                "domain": "machine_learning",
                "title": "Model Collapse & Distributional Drift Sentinel",
                "description": "Monitors training datasets, fine-tuning corpuses, and runtime inputs for data leakage, covariate shift, and synthetic model collapse degradation.",
                "pattern": r"(model collapse|data drift|covariate shift|synthetic data|target leakage|clever hans|shortcut learning)",
                "priority": 94,
                "triggers": [
                    "evaluating data quality and synthetic model degradation",
                    "detecting covariate shift and target leakage in pipelines",
                    "preventing recursive model collapse in LLM pipelines"
                ],
                "keywords": ["model collapse", "data drift", "covariate shift", "synthetic degradation", "target leakage", "data audit"],
                "sops": [
                    {"title": "1. Distributional Drift Audit", "content": "Compare incoming runtime embedding distributions against baseline training bounds."},
                    {"title": "2. Synthetic Contamination Check", "content": "Filter and penalize ungrounded recursive AI-generated inputs."},
                    {"title": "3. Temporal Boundary Validation", "content": "Ensure training and evaluation splits strictly obey temporal causal order."}
                ]
            },
            {
                "name": "homelab-mesh-dns-governor",
                "domain": "infrastructure",
                "title": "Homelab Mesh & Sovereign DNS Governor",
                "description": "Autonomous sentinel monitoring Tailscale peers, Pi-hole DNS blocking, SSH tunnels, and local cluster health across Edge_Node and sentry nodes.",
                "pattern": r"(pi.?hole|dns blocking|tailscale|mesh|Edge_Node|legion.?sentry|local cluster)",
                "priority": 92,
                "triggers": [
                    "managing homelab DNS and Pi-hole instances",
                    "auditing Tailscale mesh topology and peer latency",
                    "verifying local node health on Edge_Node and sentry servers"
                ],
                "keywords": ["homelab", "mesh", "pi-hole", "dns", "tailscale", "Edge_Node", "cluster topology"],
                "sops": [
                    {"title": "1. Peer Liveness & Routing Verification", "content": "Ping all configured Tailscale nodes and check advertised routes."},
                    {"title": "2. Pi-hole Status Inspection", "content": "Query local DNS server to verify active ad-blocking and upstream resolution."},
                    {"title": "3. Automated Fallback Activation", "content": "Switch DNS upstream or mirror route if any primary node disconnects."}
                ]
            },
            {
                "name": "voice-agent-latency-evaluator",
                "domain": "voice_ai",
                "title": "Voice Agent Latency & Audio Stream Evaluator",
                "description": "Autonomous benchmarking engine for evaluating end-to-end voice latency, ElevenLabs audio streaming, barge-in response, and speech clarity.",
                "pattern": r"(voice agent|audio stream|elevenlabs|latency|barge.?in|tts|speech evaluation)",
                "priority": 90,
                "triggers": [
                    "evaluating real-time voice latency and audio streams",
                    "benchmarking speech-to-speech turn-taking and interruptions",
                    "profiling TTS generation speed and token-to-speech delay"
                ],
                "keywords": ["voice agent", "audio latency", "speech evaluation", "elevenlabs", "tts benchmark", "audio stream"],
                "sops": [
                    {"title": "1. Time-to-First-Audio (TTFA) Measurement", "content": "Profile milliseconds between user voice cessation and initial audio packet."},
                    {"title": "2. Barge-in & Interruption Testing", "content": "Inject overlapping voice samples to test graceful cancellation."},
                    {"title": "3. Audio Integrity Verification", "content": "Measure waveform clipping and speech intelligibility score."}
                ]
            }
        ]

        combined_text = " ".join(all_queries).lower()
        for dp in domain_patterns:
            name = dp["name"]
            if name in existing_skills:
                continue
            if re.search(dp["pattern"], combined_text, re.IGNORECASE):
                candidates.append(dp)

        return candidates


transcript_intent_miner = TranscriptIntentMiner()
