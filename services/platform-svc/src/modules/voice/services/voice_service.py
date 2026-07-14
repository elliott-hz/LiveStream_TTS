"""
VoiceService — business logic for voice/timbre CRUD, clone task management, preview.

Every public method corresponds to one RPC. Methods raise AppError on failure.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common.errors import AppError, ErrorCode, not_found, invalid_arg
from libs.common.logging import get_logger

from models.voice import Voice, VoiceCloneTask

logger = get_logger(__name__)

# ── Constants ──

VALID_GENDERS = {"male", "female"}
VALID_STYLES = {"passionate", "professional", "gentle", "lively"}
VALID_VOICE_STATUSES = {"active", "cloning", "failed"}
VALID_CLONE_STATUSES = {"uploading", "processing", "success", "failed"}
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class VoiceService:
    """Voice business logic — injected with a DB session."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ──────────────────────────────────────────────────────────
    #  Voice CRUD
    # ──────────────────────────────────────────────────────────

    async def create_voice(
        self,
        store_id: str,
        name: str,
        gender: str = "male",
        age_range: str = "25-35",
        language: str = "zh-CN",
        style: str = "professional",
        is_public: bool = False,
        prompt_audio: bytes | None = None,
        prompt_transcript: str | None = None,
        created_by: str | None = None,
    ) -> Voice:
        """Create a new voice in active status."""
        if not store_id:
            raise invalid_arg("store_id", "must not be empty")
        if not name or not name.strip():
            raise invalid_arg("name", "must not be empty")
        gender_norm = gender.lower()
        if gender_norm not in VALID_GENDERS:
            raise invalid_arg("gender", f"must be one of {VALID_GENDERS}")
        style_norm = style.lower()
        if style_norm not in VALID_STYLES:
            raise invalid_arg("style", f"must be one of {VALID_STYLES}")

        voice = Voice(
            store_id=store_id,
            name=name.strip(),
            gender=gender_norm,
            age_range=age_range,
            language=language,
            style=style_norm,
            status="active",
            is_public=is_public,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(voice)
        await self.db.flush()
        await self.db.refresh(voice)

        logger.info("voice.created", voice_id=voice.voice_id, store_id=store_id)
        return voice

    async def get_voice(self, voice_id: str) -> Voice:
        """Fetch a single voice by ID."""
        if not voice_id:
            raise invalid_arg("voice_id", "must not be empty")

        stmt = select(Voice).where(Voice.voice_id == voice_id)
        result = await self.db.execute(stmt)
        voice = result.scalars().one_or_none()
        if not voice:
            raise not_found("Voice", voice_id)
        return voice

    async def update_voice(
        self,
        voice_id: str,
        name: str | None = None,
        age_range: str | None = None,
        style: str | None = None,
        is_public: bool | None = None,
        updated_by: str | None = None,
    ) -> Voice:
        """Partially update a voice's scalar fields."""
        voice = await self.get_voice(voice_id)

        if name is not None:
            if not name.strip():
                raise invalid_arg("name", "must not be empty")
            voice.name = name.strip()
        if age_range is not None:
            voice.age_range = age_range
        if style is not None:
            style_norm = style.lower()
            if style_norm not in VALID_STYLES:
                raise invalid_arg("style", f"must be one of {VALID_STYLES}")
            voice.style = style_norm
        if is_public is not None:
            voice.is_public = is_public
        if updated_by is not None:
            voice.updated_by = updated_by

        voice.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(voice)
        logger.info("voice.updated", voice_id=voice_id)
        return voice

    async def delete_voice(self, voice_id: str) -> None:
        """Hard-delete a voice."""
        voice = await self.get_voice(voice_id)
        await self.db.delete(voice)
        await self.db.flush()
        logger.info("voice.deleted", voice_id=voice_id)

    async def list_voices(
        self,
        store_id: str,
        gender: str | None = None,
        style: str | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[Voice], int]:
        """Paginated voice listing with optional filters."""
        if not store_id:
            raise invalid_arg("store_id", "must not be empty")

        page = max(page, 1)
        page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

        conditions = [Voice.store_id == store_id]

        if gender:
            gender_norm = gender.lower()
            if gender_norm not in VALID_GENDERS:
                raise invalid_arg("gender", f"must be one of {VALID_GENDERS}")
            conditions.append(Voice.gender == gender_norm)

        if style:
            style_norm = style.lower()
            if style_norm not in VALID_STYLES:
                raise invalid_arg("style", f"must be one of {VALID_STYLES}")
            conditions.append(Voice.style == style_norm)

        # Count
        count_stmt = select(func.count()).select_from(Voice).where(*conditions)
        total_result = await self.db.execute(count_stmt)
        total_count: int = total_result.scalar() or 0

        # Fetch page
        offset = (page - 1) * page_size
        stmt = (
            select(Voice)
            .where(*conditions)
            .order_by(Voice.updated_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        voices = list(result.scalars().all())

        return voices, total_count

    # ──────────────────────────────────────────────────────────
    #  Clone Task Management
    # ──────────────────────────────────────────────────────────

    async def start_clone(
        self,
        voice_id: str,
        prompt_audio: bytes | None = None,
        prompt_transcript: str | None = None,
    ) -> VoiceCloneTask:
        """Start a voice clone task for a given voice."""
        voice = await self.get_voice(voice_id)

        if voice.status != "active":
            raise AppError(
                ErrorCode.RESOURCE_IN_USE,
                f"Voice {voice_id} is not in active status (current: {voice.status})",
            )

        voice.status = "cloning"
        task = VoiceCloneTask(
            voice_id=voice_id,
            status="uploading",
            progress_percent=0,
        )
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)
        logger.info("voice.clone.started", voice_id=voice_id, task_id=task.task_id)
        return task

    async def get_clone_task(self, task_id: str) -> VoiceCloneTask:
        """Fetch a clone task by ID."""
        if not task_id:
            raise invalid_arg("task_id", "must not be empty")

        stmt = select(VoiceCloneTask).where(VoiceCloneTask.task_id == task_id)
        result = await self.db.execute(stmt)
        task = result.scalars().one_or_none()
        if not task:
            raise not_found("VoiceCloneTask", task_id)
        return task

    # ──────────────────────────────────────────────────────────
    #  Preview
    # ──────────────────────────────────────────────────────────

    async def preview_voice(
        self,
        voice_id: str,
        text: str,
    ) -> dict[str, Any]:
        """Generate a preview URL for a voice speaking the given text.

        Returns a mock preview URL and estimated duration.
        """
        voice = await self.get_voice(voice_id)

        if not text or not text.strip():
            raise invalid_arg("text", "must not be empty")

        duration_ms = len(text) * 80  # rough estimate: 80ms per character
        preview_url = f"https://cdn.livestream-tts.example.com/preview/{voice_id}/{_hash_text(text)}.mp3"

        logger.info("voice.preview", voice_id=voice_id, duration_ms=duration_ms)
        return {
            "preview_url": preview_url,
            "duration_ms": duration_ms,
        }


# ── Internal helpers ──


def _hash_text(text: str) -> str:
    """Simple hash for demo purposes."""
    import hashlib
    return hashlib.md5(text.encode()).hexdigest()[:12]
