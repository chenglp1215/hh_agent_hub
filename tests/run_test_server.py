"""
Test server launcher for task-cc-config.
Patches TORTOISE_ORM to use in-memory SQLite, starts uvicorn.

Usage: python tests/run_test_server.py
"""
import sys
import os

# Add backend directory to Python path
BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND_DIR))

# Change to backend directory for relative imports in the app code
os.chdir(os.path.abspath(BACKEND_DIR))

# Patch TORTOISE_ORM to use SQLite before any app-level imports
from config import TORTOISE_ORM, Settings

# Override DB settings for testing
TORTOISE_ORM["connections"]["default"] = {
    "engine": "tortoise.backends.sqlite",
    "credentials": {"file_path": ":memory:"},
}

# Disable file logging - just use stderr
import logging
logging.basicConfig(level=logging.INFO)

import uvicorn
from main import app

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False,
    )
