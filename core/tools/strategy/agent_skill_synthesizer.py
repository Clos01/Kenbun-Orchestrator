"""
Agent & Skill Synthesizer (core/tools/strategy/agent_skill_synthesizer.py)
=========================================================================
Autonomous agent and skill evolution engine for Kenbun.

Lifecycle:
  1. Gap Discovery: Scans runtime fallbacks, failed queries, and domain backlog.
  2. Blueprint & Synthesis: Generates complete Star-Variant SKILL.md and tools.
  3. Sandbox Verification: AST syntax checks, YAML frontmatter validation, schema audit.
  4. Registry Promotion: Injects into SKILLS_REGISTRY.md and keyword decision router.
  5. Telemetry & Hivemind: Records evolution ledger in brain_health/.
"""

import ast
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger("tools.agent_skill_synthesizer")


class AgentSkillSynthesizer:
    """
    Autonomous evolution engine that synthesizes, tests, and promotes
    new specialized agents and skills for Kenbun.
    """

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).resolve().parent.parent.parent.parent
        self.skills_dir = self.project_root / ".agents" / "skills"
        self.registry_file = self.project_root / "core" / "SKILLS_REGISTRY.md"
        self.keyword_file = self.project_root / "core" / "tools" / "strategy" / "keyword_processor.py"
        self.brain_health_dir = self.project_root / "brain_health"
        self.evolution_log = self.brain_health_dir / "agent_evolution_log.jsonl"
        self.backlog_file = self.brain_health_dir / "agent_backlog.json"

        # Ensure directories exist
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.brain_health_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # Phase 1: Gap Discovery
    # -------------------------------------------------------------------------

    def discover_agent_gaps(self) -> List[Dict[str, Any]]:
        """
        Scans runtime logs, fallback history, and domain backlogs to discover
        capabilities where Kenbun lacks a dedicated specialized agent.
        """
        existing_skills = set()
        if self.skills_dir.exists():
            for p in self.skills_dir.iterdir():
                if p.is_dir() and (p / "SKILL.md").exists():
                    existing_skills.add(p.name)

        candidates: List[Dict[str, Any]] = []

        # 1. Inspect explicit backlog if present
        if self.backlog_file.exists():
            try:
                with open(self.backlog_file, "r", encoding="utf-8") as f:
                    backlog_items = json.load(f)
                    for item in backlog_items:
                        if item.get("name") not in existing_skills:
                            candidates.append(item)
            except Exception as e:
                logger.warning(f"Error reading agent backlog: {e}")

        # 2. Inspect dispatch fallbacks in brain_health/
        fallback_file = self.brain_health_dir / "dispatch_fallbacks.jsonl"
        if fallback_file.exists():
            try:
                with open(fallback_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        entry = json.loads(line)
                        workflow = entry.get("workflow", "")
                        reason = entry.get("reason", "")
                        if "not found" in reason.lower() and workflow:
                            candidate_name = f"{workflow.replace('_', '-')}-sentinel"
                            if candidate_name not in existing_skills and not any(c["name"] == candidate_name for c in candidates):
                                candidates.append({
                                    "name": candidate_name,
                                    "domain": "infrastructure",
                                    "title": f"{workflow.replace('_', ' ').title()} Sentinel",
                                    "description": f"Autonomous sentinel for {workflow} workflows and failure remediation.",
                                    "priority": 85,
                                    "triggers": [workflow, f"{workflow}_pipeline", f"fix {workflow}"],
                                    "keywords": [workflow, f"{workflow}-fix", "remediation"]
                                })
            except Exception as e:
                logger.warning(f"Error parsing dispatch fallbacks: {e}")

        # 3. Transcript & Intent Mining (scans user conversation transcripts from the last 48 hours)
        try:
            from tools.strategy.transcript_intent_miner import transcript_intent_miner
            mined_candidates = transcript_intent_miner.mine_capability_gaps(lookback_hours=48.0)
            for item in mined_candidates:
                if item.get("name") not in existing_skills and not any(c["name"] == item.get("name") for c in candidates):
                    candidates.append(item)
        except Exception as e:
            logger.warning(f"Error mining transcripts for agent gaps: {e}")

        # 4. Built-in High-Value Sovereign Blueprints (Software Decisions & Production Development)
        seed_blueprints = [
            {
                "name": "software-decision-architect",
                "domain": "software_architecture",
                "title": "Software Decision Architect & ADR Sentinel",
                "description": "Autonomous software decision engine that evaluates architectural tradeoffs, data structures, state management patterns, and distributed paradigms to author formal Architectural Decision Records (ADRs) with zero tech debt.",
                "priority": 98,
                "triggers": [
                    "making major software design decisions",
                    "evaluating architectural tradeoffs (sync vs async, SQL vs NoSQL, monolith vs micro)",
                    "authoring or auditing Architectural Decision Records (ADRs)",
                    "resolving technical debt or selecting frameworks, protocols, and data models",
                    "choosing concurrency, state machine, or caching strategies"
                ],
                "keywords": [
                    "software decision", "architecture tradeoff", "adr record", "architectural decision",
                    "design pattern", "state management decision", "tech debt audit", "system architecture"
                ],
                "sops": [
                    {
                        "title": "1. Tradeoff & Constraint Analysis",
                        "content": "Evaluate proposed designs across 5 core dimensions: Latency/Throughput, Operational Complexity, Sovereign Resilience (local homelab execution without cloud lock-in), Type Safety, and Reversibility."
                    },
                    {
                        "title": "2. Structured ADR Generation",
                        "content": "Synthesize formal Architectural Decision Records (ADRs) covering Context, Considered Alternatives (pros/cons), Decision Outcome, Consequences, and Rollback Procedures."
                    },
                    {
                        "title": "3. Decision Sentinel Pre-Flight",
                        "content": "Audit incoming implementation plans against existing ADRs to prevent architectural divergence, tight coupling, and premature optimization."
                    }
                ]
            },
            {
                "name": "test-driven-synthesis-sentinel",
                "domain": "software_development",
                "title": "Test-Driven Development (TDD) & Spec Synthesizer",
                "description": "Autonomous test-driven development engine that synthesizes exhaustive unit, integration, boundary, and regression test suites before code is written, ensuring 100% test passing and zero defect leaks.",
                "priority": 95,
                "triggers": [
                    "implementing new features with strict Test-Driven Development (TDD)",
                    "writing unit and integration tests before writing code",
                    "synthesizing mock contracts, boundary tests, and failure mode fixtures",
                    "verifying code correctness and preventing regression leaks"
                ],
                "keywords": [
                    "tdd", "test driven", "synthesize tests", "unit test suite",
                    "boundary test", "regression test", "mock fixture", "test spec", "test first"
                ],
                "sops": [
                    {
                        "title": "1. Specification & Contract Deconstruction",
                        "content": "Extract explicit preconditions, postconditions, and invariant contracts from the task description, type hints, and tool definitions."
                    },
                    {
                        "title": "2. Exhaustive Test Suite Synthesis (Red Phase)",
                        "content": "Generate comprehensive unit, boundary, error-state, and mock tests with pytest or vitest before writing implementation code."
                    },
                    {
                        "title": "3. Verification & Refactor Loop (Green/Refactor Phase)",
                        "content": "Verify tests fail on initial state, run implementation against tests, and ensure 100% pass rate before committing."
                    }
                ]
            },
            {
                "name": "autonomous-refactoring-engine",
                "domain": "software_engineering",
                "title": "Autonomous Refactoring & Clean Architecture Governor",
                "description": "Continuous code modernization and clean architecture sentinel that identifies code smells, eliminates cyclomatic complexity, enforces dependency injection, and safely refactors modules with zero behavioral regression.",
                "priority": 92,
                "triggers": [
                    "refactoring complex or monolithic files",
                    "reducing cyclomatic complexity and eliminating code smells",
                    "decoupling modules using clean architecture and dependency injection",
                    "pruning dead code, zombie imports, and stale abstractions"
                ],
                "keywords": [
                    "refactor", "clean architecture", "code smell", "cyclomatic complexity",
                    "decouple", "extract class", "dependency injection", "zombie code", "modernize code"
                ],
                "sops": [
                    {
                        "title": "1. Code Smell & AST Complexity Audit",
                        "content": "Scan target modules for cyclomatic complexity >10, God classes (>500 lines), long functions, and tight coupling."
                    },
                    {
                        "title": "2. Safe Structural Transformation",
                        "content": "Apply proven refactoring transformations (Extract Function, Introduce Parameter Object, Strategy Pattern) while strictly preserving external interfaces."
                    },
                    {
                        "title": "3. Regression & Invariant Verification",
                        "content": "Execute full regression test suites before and after refactoring to prove 100% behavioral equivalence."
                    }
                ]
            }
        ]

        for seed in seed_blueprints:
            if seed["name"] not in existing_skills and not any(c["name"] == seed["name"] for c in candidates):
                candidates.append(seed)

        # Sort by priority descending
        candidates.sort(key=lambda c: c.get("priority", 50), reverse=True)
        return candidates

    # -------------------------------------------------------------------------
    # Phase 2: Blueprint & Synthesis
    # -------------------------------------------------------------------------

    def synthesize_skill(self, spec: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """
        Synthesizes a production-grade Star-Variant SKILL.md and accompanying scaffolding.
        """
        name = spec.get("name", "").strip().lower().replace(" ", "-")
        if not name or not re.match(r"^[a-z0-9-]+$", name):
            raise ValueError(f"Invalid skill name format: '{name}'. Must be alphanumeric-kebab-case.")

        title = spec.get("title", f"{name.replace('-', ' ').title()}")
        description = spec.get("description", f"Autonomous sentinel and skill for {name}.")
        triggers = spec.get("triggers", [f"working with {name}"])
        sops = spec.get("sops", [
            {
                "title": "1. Initial Inspection & Context Gathering",
                "content": "Verify system state, target inputs, and environmental constraints."
            },
            {
                "title": "2. Autonomous Execution & Verification",
                "content": "Execute targeted actions with non-blocking error handling and immediate feedback."
            },
            {
                "title": "3. Reporting & State Preservation",
                "content": "Record outcomes in the local ledger and emit telemetry signals to the dashboard."
            }
        ])

        # Render complete SKILL.md content
        triggers_rendered = "\n".join(f"- {t}" for t in triggers)
        sops_rendered = "\n\n".join(f"### {sop['title']}\n{sop['content']}" for sop in sops)

        skill_md_content = f"""---
name: {name}
description: {description}
---

# 🛡️ {title}

The **{title}** extends Kenbun's autonomous capabilities with domain-specific sentinels, automated verification, and self-healing procedures.

---

## 🎯 When to Activate

Trigger this skill immediately when:
{triggers_rendered}

---

## 📋 Standard Operating Procedures (SOPs)

{sops_rendered}

---

## 🛡️ Defensive Guardrails & Star-Variant Protocols

1. **Non-Blocking Fallback**: If external endpoints fail, immediately fall back to local telemetry or cached models without halting execution.
2. **Schema Integrity**: Validate all payloads, arguments, and return envelopes before passing to downstream pipelines.
3. **Stdout Protocol Shield**: All background diagnostics must route to stderr or log files, preserving standard tool execution streams.

---

## 📊 Telemetry & Verification Ledger

Every execution of this skill logs execution latency, tokens consumed, and validation results to `brain_health/agent_evolution_log.jsonl`.
"""

        skill_dir = self.skills_dir / name
        skill_md_path = skill_dir / "SKILL.md"

        if not dry_run:
            skill_dir.mkdir(parents=True, exist_ok=True)
            with open(skill_md_path, "w", encoding="utf-8") as f:
                f.write(skill_md_content)

        return {
            "name": name,
            "title": title,
            "skill_dir": str(skill_dir),
            "skill_md_path": str(skill_md_path),
            "spec": spec,
            "dry_run": dry_run
        }

    # -------------------------------------------------------------------------
    # Phase 3: Sandbox Verification
    # -------------------------------------------------------------------------

    def verify_skill(self, skill_name: str) -> Dict[str, Any]:
        """
        Validates the newly synthesized skill in an AST and schema sandbox.
        """
        skill_dir = self.skills_dir / skill_name
        skill_md_path = skill_dir / "SKILL.md"

        errors: List[str] = []

        if not skill_dir.exists() or not skill_dir.is_dir():
            return {"valid": False, "score": 0.0, "errors": [f"Directory {skill_dir} does not exist"]}

        if not skill_md_path.exists():
            return {"valid": False, "score": 0.0, "errors": ["Missing SKILL.md"]}

        try:
            content = skill_md_path.read_text(encoding="utf-8")
        except Exception as e:
            return {"valid": False, "score": 0.0, "errors": [f"Failed to read SKILL.md: {e}"]}

        # 1. Frontmatter Validation
        if not content.startswith("---"):
            errors.append("SKILL.md does not start with YAML frontmatter delimiter (---)")
        else:
            parts = content.split("---", 2)
            if len(parts) < 3:
                errors.append("Malformed YAML frontmatter: missing closing delimiter (---)")
            else:
                try:
                    meta = yaml.safe_load(parts[1])
                    if not isinstance(meta, dict):
                        errors.append("Frontmatter is not a valid YAML dictionary")
                    else:
                        if not meta.get("name"):
                            errors.append("Frontmatter missing required 'name' field")
                        elif meta["name"] != skill_name:
                            errors.append(f"Frontmatter name '{meta['name']}' != directory name '{skill_name}'")
                        if not meta.get("description"):
                            errors.append("Frontmatter missing required 'description' field")
                except Exception as e:
                    errors.append(f"YAML parsing error in frontmatter: {e}")

        # 2. Section Headings Check
        required_headings = ["When to Activate", "Standard Operating Procedures", "Defensive Guardrails"]
        for heading in required_headings:
            if heading.lower() not in content.lower():
                errors.append(f"SKILL.md missing recommended section: '{heading}'")

        # 3. Python AST Verification for any bundled scripts
        python_files = list(skill_dir.rglob("*.py"))
        for py_file in python_files:
            try:
                with open(py_file, "r", encoding="utf-8") as pf:
                    code = pf.read()
                ast.parse(code, filename=str(py_file))
            except SyntaxError as se:
                errors.append(f"Python syntax error in {py_file.name}: {se}")

        is_valid = len(errors) == 0
        score = 1.0 if is_valid else max(0.0, 1.0 - (len(errors) * 0.25))

        return {
            "valid": is_valid,
            "score": score,
            "errors": errors,
            "files_scanned": 1 + len(python_files)
        }

    # -------------------------------------------------------------------------
    # Phase 4: Registry Promotion & Keyword Injection
    # -------------------------------------------------------------------------

    def promote_and_register(self, skill_name: str, spec: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """
        Promotes the validated skill into the Kenbun Master Skills Registry
        and updates the KeywordProcessor so DecisionRouter can route to it.
        """
        results: Dict[str, Any] = {
            "skill_name": skill_name,
            "registry_updated": False,
            "keywords_injected": False,
            "evolution_logged": False
        }

        # 1. Update SKILLS_REGISTRY.md
        if self.registry_file.exists() and not dry_run:
            try:
                reg_text = self.registry_file.read_text(encoding="utf-8")
                if skill_name not in reg_text:
                    # Determine next number
                    matches = re.findall(r"^\|\s*(\d+)\s*\|", reg_text, re.MULTILINE)
                    next_num = max(int(m) for m in matches) + 1 if matches else 30

                    title = spec.get("title", skill_name.replace("-", " ").title())
                    desc = spec.get("description", "Autonomous specialized agent skill.")
                    short_desc = desc.split(".")[0] + "."

                    new_row = f"| {next_num} | [`{skill_name}`](.agents/skills/{skill_name}/SKILL.md) | **[AUTO-SYNTHESIZED]** {short_desc} | Autonomous Evolution Engine, System 2 Sentinel |\n"

                    # Update header count if present
                    reg_text = re.sub(
                        r"catalog of all \d+ specialized agent skills",
                        f"catalog of all {next_num} specialized agent skills",
                        reg_text
                    )
                    reg_text = re.sub(
                        r"## 📦 Complete Inventory of All \d+ Skills",
                        f"## 📦 Complete Inventory of All {next_num} Skills",
                        reg_text
                    )

                    reg_text = reg_text.rstrip() + "\n" + new_row
                    self.registry_file.write_text(reg_text, encoding="utf-8")
                    results["registry_updated"] = True
                    results["registry_index"] = next_num
            except Exception as e:
                logger.error(f"Failed updating SKILLS_REGISTRY.md: {e}")

        # 2. Inject Keywords into KeywordProcessor
        keywords = spec.get("keywords", [])
        domain = spec.get("domain", "autonomous")
        if keywords and self.keyword_file.exists() and not dry_run:
            try:
                kp_content = self.keyword_file.read_text(encoding="utf-8")
                if f'"{domain}"' in kp_content:
                    for kw in keywords:
                        if f'"{kw}"' not in kp_content:
                            pattern = rf'("{domain}":\s*\[)([^\]]*)(\])'
                            match = re.search(pattern, kp_content)
                            if match:
                                current_items = match.group(2).rstrip()
                                updated_items = f'{current_items}, "{kw}"' if current_items else f'"{kw}"'
                                kp_content = kp_content[:match.start(2)] + updated_items + kp_content[match.end(2):]
                                results["keywords_injected"] = True
                else:
                    kw_list_str = json.dumps(keywords)
                    insertion = f'            "{domain}": {kw_list_str},\n'
                    dict_end_pos = kp_content.find("        }")
                    if dict_end_pos != -1:
                        kp_content = kp_content[:dict_end_pos] + insertion + kp_content[dict_end_pos:]
                        results["keywords_injected"] = True

                self.keyword_file.write_text(kp_content, encoding="utf-8")
            except Exception as e:
                logger.error(f"Failed updating keyword_processor.py: {e}")

        # 3. Log to brain_health/agent_evolution_log.jsonl
        if not dry_run:
            try:
                log_entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "skill_name": skill_name,
                    "domain": spec.get("domain", "general"),
                    "title": spec.get("title", ""),
                    "status": "promoted",
                    "keywords": keywords,
                    "event": "AUTONOMOUS_SKILL_PROMOTION"
                }
                with open(self.evolution_log, "a", encoding="utf-8") as f:
                    f.write(json.dumps(log_entry) + "\n")
                results["evolution_logged"] = True
            except Exception as e:
                logger.error(f"Failed logging evolution entry: {e}")

        return results

    # -------------------------------------------------------------------------
    # High-Level Orchestrated Cycle
    # -------------------------------------------------------------------------

    def run_evolution_cycle(self, max_candidates: int = 1, dry_run: bool = False) -> Dict[str, Any]:
        """
        Executes the end-to-end evolution cycle:
          Discover -> Synthesize -> Verify -> Promote.
        """
        gaps = self.discover_agent_gaps()
        if not gaps:
            return {
                "status": "idle",
                "message": "No new agent gaps detected; skills matrix is fully populated.",
                "synthesized_count": 0,
                "skills": []
            }

        synthesized = []
        for candidate in gaps[:max_candidates]:
            name = candidate["name"]
            logger.info(f"🧬 Synthesizing candidate agent skill: '{name}'...")

            synth_res = self.synthesize_skill(candidate, dry_run=dry_run)
            verify_res = self.verify_skill(name) if not dry_run else {"valid": True, "score": 1.0, "errors": []}

            if verify_res["valid"]:
                promote_res = self.promote_and_register(name, candidate, dry_run=dry_run)
                synthesized.append({
                    "name": name,
                    "title": candidate.get("title", name),
                    "domain": candidate.get("domain", "general"),
                    "status": "promoted" if not dry_run else "simulated",
                    "score": verify_res["score"],
                    "registry": promote_res
                })
                logger.info(f"✨ Successfully promoted '{name}' to Kenbun Master Skills Registry!")
            else:
                logger.warning(f"⚠️ Synthesis verification failed for '{name}': {verify_res['errors']}")
                synthesized.append({
                    "name": name,
                    "status": "rejected",
                    "score": verify_res["score"],
                    "errors": verify_res["errors"]
                })

        return {
            "status": "completed",
            "synthesized_count": len(synthesized),
            "skills": synthesized
        }


# Global Singleton
agent_skill_synthesizer = AgentSkillSynthesizer()
