#!/usr/bin/env python3
"""Start AYUR-INTEL server in the background."""
import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "server.log")

proc = subprocess.Popen(
    [sys.executable, "-c", "import uvicorn; uvicorn.run('api.main:app', host='127.0.0.1', port=8000)"],
    stdout=open(log_path, "a"),
    stderr=subprocess.STDOUT,
)
print(f"Server PID: {proc.pid}")
