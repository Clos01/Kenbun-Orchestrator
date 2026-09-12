#!/usr/bin/env python3
"""
Dynamic Cluster Mesh & Zero-Drift Configuration Synthesizer
===========================================================
Autonomously probes the Kenbun multi-node cluster (LG 2025, Edge_Node, Local Mac, Pi),
resolves active service endpoints (PostgreSQL, ChromaDB, LM Studio, Honcho),
guards against Tailscale LAN subnet collisions, and generates synchronized,
drift-free mcp_config.json files across all nodes.
"""
from __future__ import annotations

import json
import os
import platform
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def probe_socket(host: str, port: int, timeout: float = 1.5) -> bool:
    """Fast non-blocking socket probe to verify service availability."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        res = s.connect_ex((host, port))
        return res == 0
    except Exception:
        return False
    finally:
        s.close()


def get_local_node_type() -> str:
    """Identifies whether the script is running on Mac, Edge_Node, or LG 2025."""
    system = platform.system().lower()
    if system == "darwin":
        return "mac_workstation"

    try:
        hostname = socket.gethostname().lower()
        if "automation" in hostname or "Edge_Node" in hostname:
            return "Edge_Node"
        if "legion" in hostname:
            return "sentry"
    except Exception:
        pass

    if (Path.home() / "Dev" / "Kenbun").exists():
        return "Edge_Node"
    return "unknown"


def resolve_cluster_endpoints() -> Dict[str, Any]:
    """Probes LG 2025 and determines the optimal working IP/port for each service."""
    lg_host = "<ORCHESTRATOR_IP>"
    lg_sidecar = "<VECTOR_DB_IP>"

    pg_host_open = probe_socket(lg_host, 5432)
    pg_sidecar_open = probe_socket(lg_sidecar, 5432)

    chroma_sidecar_open = probe_socket(lg_sidecar, 8000)
    chroma_host_open = probe_socket(lg_host, 8000)
    chroma_ip = lg_sidecar if chroma_sidecar_open else (lg_host if chroma_host_open else lg_sidecar)

    lm_host_open = probe_socket(lg_host, 2065)

    honcho_sidecar_open = probe_socket(lg_sidecar, 8001)
    honcho_host_open = probe_socket(lg_host, 8001)
    honcho_ip = lg_sidecar if honcho_sidecar_open else (lg_host if honcho_host_open else lg_sidecar)

    return {
        "postgres": {
            "host": lg_host if pg_host_open else lg_sidecar,
            "port": 5432,
            "user": "appuser",
            "password": "kenbun",
            "db": "kenbun_intelligence",
            "status": "online" if (pg_host_open or pg_sidecar_open) else "offline"
        },
        "chromadb": {
            "host": chroma_ip,
            "port": 8000,
            "status": "online" if (chroma_sidecar_open or chroma_host_open) else "offline"
        },
        "lm_studio": {
            "host": lg_host,
            "port": 2065,
            "model": "qwen/qwen2.5-coder-14b",
            "status": "online" if lm_host_open else "offline"
        },
        "honcho": {
            "host": honcho_ip,
            "port": 8001,
            "status": "online" if (honcho_sidecar_open or honcho_host_open) else "offline"
        }
    }


def guard_tailscale_lan_collision() -> Dict[str, Any]:
    """Ensures local Mac does not accept colliding subnet routes while on home LAN."""
    if platform.system().lower() != "darwin":
        return {"action": "skipped", "reason": "non-darwin"}

    ts_bin = Path("/Applications/Tailscale.app/Contents/MacOS/Tailscale")
    if not ts_bin.exists():
        return {"action": "skipped", "reason": "tailscale_bin_missing"}

    try:
        out = subprocess.check_output([str(ts_bin), "debug", "prefs"], text=True)
        prefs = json.loads(out)
        route_all = prefs.get("RouteAll", False)

        if route_all:
            subprocess.check_call([str(ts_bin), "set", "--accept-routes=false", "--exit-node="])
            return {"action": "disarmed", "status": "route_collision_prevented"}
        return {"action": "verified", "status": "accept_routes_already_false"}
    except Exception as e:
        return {"action": "error", "error": str(e)}


def generate_node_mcp_config(node_type: str, endpoints: Dict[str, Any]) -> Dict[str, Any]:
    """Generates a clean, typed mcp_config.json matching the target node's paths."""
    local_home = Path.home()
    if node_type == "mac_workstation":
        kenbun_root = local_home / "Dev" / "Kenbun"
        py_bin = str(kenbun_root / "core" / ".venv" / "bin" / "python3")
        server_path = str(kenbun_root / "core" / "tools" / "infrastructure" / "server.py")
        proj_root = str(kenbun_root)
        python_path = f"{proj_root}/core:{proj_root}/core/tools:{proj_root}"
    else:  # Edge_Node (Edge Compute Node)
        if platform.system().lower() == "linux":
            kenbun_root = local_home / "Dev" / "Kenbun"
        else:
            # Constructed dynamically for remote Edge_Node node when running from Mac
            kenbun_root = Path(os.sep + "home") / "user" / "Dev" / "Kenbun"
        py_bin = str(kenbun_root / "venv" / "bin" / "python")
        server_path = str(kenbun_root / "core" / "tools" / "infrastructure" / "server.py")
        proj_root = str(kenbun_root)
        python_path = f"{proj_root}/core:{proj_root}/core/tools:{proj_root}"

    server_block = {
        "command": py_bin,
        "args": ["-u", server_path],
        "env": {
            "PROJECT_ROOT": proj_root,
            "PYTHONPATH": python_path,
            "CHROMA_HOST": endpoints["chromadb"]["host"],
            "CHROMA_PORT": str(endpoints["chromadb"]["port"]),
            "INTERNAL_API_URL": f"http://{endpoints['honcho']['host']}:{endpoints['honcho']['port']}",
            "HONCHO_BASE_URL": f"http://{endpoints['honcho']['host']}:{endpoints['honcho']['port']}",
            "PC_IP_ADDRESS": endpoints["honcho"]["host"],
            "PRIMARY_LLM_URL": f"http://{endpoints['lm_studio']['host']}:{endpoints['lm_studio']['port']}/v1",
            "PRIMARY_LLM_MODEL": endpoints["lm_studio"]["model"],
            "LM_Studio": f"http://{endpoints['lm_studio']['host']}:{endpoints['lm_studio']['port']}/v1",
            "PLANKA_BASE_URL": f"http://{endpoints['honcho']['host']}:3000",
            "POSTGRES_HOST": endpoints["postgres"]["host"],
            "POSTGRES_PORT": str(endpoints["postgres"]["port"]),
            "POSTGRES_USER": endpoints["postgres"]["user"],
            "POSTGRES_PASSWORD": endpoints["postgres"]["password"],
            "POSTGRES_DB": endpoints["postgres"]["db"],
            "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY", "")
        }
    }

    return {
        "mcpServers": {
            "Kenbun-tools": server_block,
            "kenbun-agent": server_block
        }
    }


def write_local_configs(config: Dict[str, Any]) -> list[str]:
    """Writes mcp_config.json to all known Antigravity config paths on local machine."""
    written = []
    base_dirs = [
        Path.home() / ".gemini" / "antigravity",
        Path.home() / ".gemini" / "antigravity-ide",
        Path.home() / ".gemini" / "antigravity-cli",
        Path.home() / ".gemini" / "config"
    ]
    for d in base_dirs:
        d.mkdir(parents=True, exist_ok=True)
        target = d / "mcp_config.json"
        with open(target, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        written.append(str(target))
    return written


def sync_remote_p330(endpoints: Dict[str, Any]) -> Dict[str, Any]:
    """Syncs configuration to Edge_Node over SSH."""
    p330_ip = os.environ.get("P330_IP_ADDRESS", os.environ.get("P330_IP", os.getenv("COMPUTE_NODE_IP", "127.0.0.1")))
    p330_cfg = generate_node_mcp_config("Edge_Node", endpoints)
    cfg_json = json.dumps(p330_cfg)

    remote_cmd = f"""
python3 -c '
import json
from pathlib import Path
config = {cfg_json}
for d in [Path.home() / ".gemini" / sub for sub in ["config", "antigravity", "antigravity-ide", "antigravity-cli"]]:
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "mcp_config.json", "w") as f:
        json.dump(config, f, indent=2)
'
"""
    try:
        subprocess.check_call([
            "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=3",
            f"user@{p330_ip}", remote_cmd
        ])
        return {"status": "success", "peer": f"user@{p330_ip}"}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


def run_full_mesh_audit(sync_peers: bool = True) -> Dict[str, Any]:
    """Top-level audit and sync runner."""
    local_node = get_local_node_type()
    endpoints = resolve_cluster_endpoints()
    lan_guard = guard_tailscale_lan_collision()
    local_cfg = generate_node_mcp_config(local_node, endpoints)
    written_files = write_local_configs(local_cfg)

    remote_res = None
    if sync_peers and local_node == "mac_workstation":
        remote_res = sync_remote_p330(endpoints)

    return {
        "local_node": local_node,
        "endpoints": endpoints,
        "tailscale_guard": lan_guard,
        "written_local_configs": written_files,
        "remote_p330_sync": remote_res
    }


if __name__ == "__main__":
    sync_peers = "--no-peers" not in sys.argv
    res = run_full_mesh_audit(sync_peers=sync_peers)
    print(json.dumps(res, indent=2))
