"""Shared pytest bootstrap.

``skills/risk-assessment`` is source-controlled with a hyphen in its path, which
Python cannot dot-import through. Its bundled engine package lives at
``skills/risk-assessment/scripts/risk_engine`` and is a normal (non-hyphenated)
import root once that ``scripts/`` directory is on ``sys.path`` — the same
``PYTHONPATH=skills/risk-assessment/scripts`` prefix used to invoke
``risk_engine``'s CLI entry points (``run_risk.py``, ``fetch_http.py``) from the
command line.
"""

import sys
from pathlib import Path

_RISK_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skills" / "risk-assessment" / "scripts"
if str(_RISK_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_RISK_SCRIPTS_DIR))
