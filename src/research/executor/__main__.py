"""
Entry point for running as module: python -m src.research.executor
"""

import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())
