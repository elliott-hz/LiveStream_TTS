"""
Package redirector: services.tts_svc -> services/tts-svc/

This allows importing the tts-svc source tree as:

    from services.tts_svc.src.main import main

The ``__path__`` is overridden to point to the real directory
(``services/tts-svc/``) so that sub-packages (``src``, ``modules``)
resolve to the hyphenated directory.
"""

from pathlib import Path

__path__ = [str(Path(__file__).resolve().parent.parent / "tts-svc")]
