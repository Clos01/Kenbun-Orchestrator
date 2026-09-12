import re
from typing import List, Dict

class KeywordProcessor:
    """
    Handles keyword definitions and regex matching for System 4b.
    """
    def __init__(self, keywords: Dict[str, List[str]] = None):
        self.keywords = keywords or {
            "ui": ["css", "layout", "style", "tailwind", "flexbox", "grid", "component", "button", "center", "form", "validation", "zod", "input", "ui", "aesthetic", "brutalist", "glassmorphic", "animation", "gsap"],
            "security": ["sql", "injection", "auth", "jwt", "password", "data leak", "bypass", "permission", "cors", "vulnerability", "rate-limit", "brute-force", "ddos", "xss", "sanitization", "secure", "hardening", "encrypt", "breach", "leak", "harden"],
            "performance": ["slow", "lag", "optimize", "cache", "memory leak", "memory", "bottleneck", "fps", "glsl", "perf", "revalidation"],
            "bug": ["error", "fail", "crash", "bug", "broken", "broke", "regression", "not working", "fix", "issue", "resolve"],
            "architecture": ["architect", "design", "strategy", "research", "migrate", "transition", "pros and cons", "scalable", "infrastructure", "refactor"],
            "deep_code": ["implement", "build feature", "generate tests", "write module", "create module", "full implementation", "multi-file", "overhaul", "rewrite", "scaffold", "build out", "wire up"],
            "noise": ["story", "joke", "tell me", "dragon", "pizza", "movie", "game", "chat", "random"],
            "software_architecture": ["software decision", "architecture tradeoff", "adr record", "architectural decision", "design pattern", "state management decision", "tech debt audit", "system architecture"],
            "software_development": ["tdd", "test driven", "synthesize tests", "unit test suite", "boundary test", "regression test", "mock fixture", "test spec", "test first"],
            "software_engineering": ["refactor", "clean architecture", "code smell", "cyclomatic complexity", "decouple", "extract class", "dependency injection", "zombie code", "modernize code"],
            "infrastructure_automation": ["nightwatch", "cron automation", "dynamic scheduler", "permit scrapers", "nightly runner", "self-updating cron", "discovery matrix"],
            "voice_ai_evaluation": ["voice eval", "atomic eval", "rubric architect", "eval check", "voice agent telemetry", "dialogue evaluation", "prompt scoring"],
            "ai_safety_governance": ["alignment guardian", "epistemic humility", "two-zone boundary", "ai safety sentinel", "recursive alignment", "socratic option mapping", "superintelligence safety"],
            "ai_safety": ["ai safety", "alignment", "indifference", "red zone", "safety gate", "epistemic guardrail"],
            "voice_ai": ["voice agent", "audio latency", "speech evaluation", "elevenlabs", "tts benchmark", "audio stream"],
        }

    def match_categories(self, text: str) -> Dict[str, List[str]]:
        if not text:
            return {cat: [] for cat in self.keywords}

        text_lower = text.lower()
        matched = {cat: [] for cat in self.keywords}

        for category, kws in self.keywords.items():
            for k in kws:
                try:
                    # Security keywords use fuzzy matching (no word boundary)
                    if category == "security":
                        if k in text_lower:
                            matched[category].append(k)
                    else:
                        if re.search(rf"\b{re.escape(k)}\b", text_lower):
                            matched[category].append(k)
                except re.error:
                    continue
        return matched
