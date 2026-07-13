"""
M2 — Session Manager
POC: 内存 dict 实现。生产环境换 Redis。
"""

import time
import threading
from dataclasses import dataclass, asdict, field
from typing import Optional


@dataclass
class SessionState:
    session_id: str
    voice_id: str = "default"
    emotion: str = "neutral"
    speed: float = 1.0
    text_buffer: str = ""
    total_chunks: int = 0
    created_at: float = field(default_factory=time.time)
    last_active_at: float = field(default_factory=time.time)

    def to_dict(self):
        d = asdict(self)
        return d


class SessionManager:
    """
    流式会话管理器。
    POC: 内存 dict + 后台超时清理。
    """

    def __init__(self, idle_timeout_seconds: int = 30, cleanup_interval_seconds: int = 10):
        self._sessions: dict[str, SessionState] = {}
        self.idle_timeout = idle_timeout_seconds
        self._lock = threading.Lock()
        # 后台超时清理
        self._cleaner = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleaner.start()

    # --- 对内接口 (被 M1 调用) ---

    def create_session(self, session_id: str, voice_id: str = "default",
                       emotion: str = "neutral", speed: float = 1.0) -> SessionState:
        state = SessionState(
            session_id=session_id,
            voice_id=voice_id,
            emotion=emotion,
            speed=speed,
        )
        with self._lock:
            self._sessions[session_id] = state
        return state

    def get_session(self, session_id: str) -> Optional[SessionState]:
        with self._lock:
            state = self._sessions.get(session_id)
            if state:
                state.last_active_at = time.time()
            return state

    def update_session(self, session_id: str, **fields) -> Optional[SessionState]:
        with self._lock:
            state = self._sessions.get(session_id)
            if not state:
                return None
            for k, v in fields.items():
                if hasattr(state, k):
                    setattr(state, k, v)
            state.last_active_at = time.time()
            return state

    def destroy_session(self, session_id: str) -> bool:
        with self._lock:
            existed = session_id in self._sessions
            if existed:
                del self._sessions[session_id]
            return existed

    def _cleanup_loop(self):
        """定期清理超时会话。"""
        while True:
            time.sleep(self.idle_timeout)
            now = time.time()
            with self._lock:
                expired = [
                    sid for sid, state in self._sessions.items()
                    if now - state.last_active_at > self.idle_timeout
                ]
                for sid in expired:
                    del self._sessions[sid]
