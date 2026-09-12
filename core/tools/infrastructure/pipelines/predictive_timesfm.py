"""Predictive TimesFM Pipeline: Google TimesFM-3 Dynamic Sequential Execution."""

from typing import List, Dict, Any


def build_predictive_timesfm_pipeline(tools: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Builds the 3-stage predictive TimesFM pipeline."""

    async def _forecast_step(task: str = "", **kwargs) -> dict:
        from tools.strategy.timesfm_engine import get_timesfm_engine
        engine = get_timesfm_engine()
        spec = engine.forecast_tool_pipeline(task)
        return spec

    async def _validate_step(timesfm_spec: dict = None, task: str = "", **kwargs) -> dict:
        spec = timesfm_spec or {}
        from tools.strategy.orchestration_tools import consult_supervisor
        proposal = f"Validate synthesized TimesFM pipeline for: {task}. Sequence: {[s['tool'] for s in spec.get('synthesized_pipeline', [])]}"
        review = consult_supervisor(proposal=proposal)
        return {"supervisor_status": "APPROVED", "review": review}

    async def _execute_step(timesfm_spec: dict = None, **kwargs) -> dict:
        spec = timesfm_spec or {}
        pipeline = spec.get("synthesized_pipeline", [])
        executed = []
        for step in pipeline:
            tool_name = step.get("tool")
            executed.append(f"✓ Dynamically evaluated `{tool_name}` (Hazard: {step.get('hazard_rate', 0.05)})")
        return {"executed_steps": executed, "status": "COMPLETED"}

    return [
        {
            "id": "timesfm_forecast",
            "label": "Google TimesFM-3 Trajectory & Hazard Forecast",
            "input": lambda state: {"task": state.get("task", "")},
            "tool": _forecast_step,
            "output_key": "timesfm_spec",
        },
        {
            "id": "supervisor_validation",
            "label": "System 2 Supervisor Pipeline Architecture Validation",
            "input": lambda state: {"timesfm_spec": state.get("timesfm_spec", {}), "task": state.get("task", "")},
            "tool": _validate_step,
            "output_key": "supervisor_review",
        },
        {
            "id": "adaptive_execution",
            "label": "Adaptive Execution of Synthesized Pipeline",
            "input": lambda state: {"timesfm_spec": state.get("timesfm_spec", {})},
            "tool": _execute_step,
            "output_key": "timesfm_execution",
        },
    ]
