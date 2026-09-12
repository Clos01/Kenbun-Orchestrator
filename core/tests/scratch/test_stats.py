import subprocess
import os

env = os.environ.copy()
env["PYTHONPATH"] = "~/Dev/Kenbun/core:~/Dev/Kenbun/core/tools:~/Dev/Kenbun"

p = subprocess.Popen(
    ["~/Dev/Kenbun/core/.venv/bin/python3", "-u", "~/Dev/Kenbun/core/tools/infrastructure/server.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env=env,
    text=True
)

init_req = '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0.0"}}}\n'
p.stdin.write(init_req)
p.stdin.flush()
print("Init response:", p.stdout.readline().strip())

req = '{"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "get_intelligence_stats", "arguments": {}}}\n'
p.stdin.write(req)
p.stdin.flush()

try:
    print("Response:", p.stdout.readline().strip())
except Exception as e:
    print("Exception:", e)

print("Stderr:", p.stderr.read())
