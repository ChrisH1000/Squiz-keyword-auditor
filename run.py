#!/usr/bin/env python3
"""Entry point for running the Squiz Keyword Auditor."""

import sys
from pathlib import Path

# Add the squiz-keyword-auditor directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "squiz-keyword-auditor"))

# Now import and run the main app
from main import app

if __name__ == "__main__":
    app()
