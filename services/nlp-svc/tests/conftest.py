"""
Shared test fixtures for nlp-svc tests.

Sets up the Python path for test imports.
"""

import sys
from pathlib import Path

# Add repo root + nlp-svc src to sys.path for test imports
_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
_SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")

for _p in (_REPO_ROOT, _SRC_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)
