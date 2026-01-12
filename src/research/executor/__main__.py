"""
Entry point for running as module: python -m src.research.executor
"""

# Load environment variables BEFORE importing modules that depend on them
from dotenv import load_dotenv
load_dotenv()

import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())
