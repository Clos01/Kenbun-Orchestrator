# Initialize agents module
import importlib.util
import os

_agents_py = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agents.py")
if os.path.exists(_agents_py):
    _spec = importlib.util.spec_from_file_location("agents_personas_module", _agents_py)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    PERSONAS = getattr(_mod, "PERSONAS", {})
    AgentPersona = getattr(_mod, "AgentPersona", None)
else:
    PERSONAS = {}
    AgentPersona = None
