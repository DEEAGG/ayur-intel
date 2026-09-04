#!/bin/bash
cd /Users/sahoo/Documents/RationRight/ayur-intel
exec python3 -m uvicorn api.main:app --host 127.0.0.1 --port 8000
