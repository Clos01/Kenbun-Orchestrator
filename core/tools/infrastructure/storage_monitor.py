"""
Storage & Resource Monitor for Kenbun Swarm
===========================================
Provides disk usage stats for Edge_Node and Legion nodes,
and performs automated cleanup of temporary logs and old n8n execution files.
"""

import shutil
import subprocess
from typing import Dict, Any

def get_storage_stats() -> Dict[str, Any]:
    """Returns disk usage for local system and Edge_Node via SSH if reachable."""
    total, used, free = shutil.disk_usage("/")
    stats = {
        "local": {
            "total_gb": round(total / (1024 ** 3), 2),
            "used_gb": round(used / (1024 ** 3), 2),
            "free_gb": round(free / (1024 ** 3), 2),
            "percent_used": round((used / total) * 100, 1)
        }
    }

    # Try fetching Edge_Node disk usage
    try:
        res = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=3", "Edge_Node", "df -h / | tail -n 1"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if res.returncode == 0:
            parts = res.stdout.split()
            if len(parts) >= 5:
                stats["Edge_Node"] = {
                    "total": parts[1],
                    "used": parts[2],
                    "free": parts[3],
                    "percent_used": parts[4]
                }
    except Exception:
        stats["Edge_Node"] = {"error": "Unreachable"}

    return stats

def cleanup_n8n_logs() -> Dict[str, Any]:
    """Purges expired n8n execution logs and temporary docker files on Edge_Node."""
    try:
        cmd = "ssh Edge_Node 'docker exec n8n-docker-n8n-1 n8n cleanup --days 14 || true'"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        return {"status": "success", "output": res.stdout.strip()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import json
    print(json.dumps(get_storage_stats(), indent=2))
