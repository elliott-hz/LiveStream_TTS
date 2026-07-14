"""
Pipeline modules for the interact-svc.

Processing chain:
  Collector → ProfileLookup → Router → Orchestrator → Moderator

Each stage is self-contained, testable, and communicates via DanmakuEvent.
"""

from .collector import DanmakuCollector
from .profile_lookup import ProfileLookup
from .router import ChannelRouter
from .orchestrator import PromptOrchestrator
from .moderator import TextModerator

__all__ = [
    "DanmakuCollector",
    "ProfileLookup",
    "ChannelRouter",
    "PromptOrchestrator",
    "TextModerator",
]
