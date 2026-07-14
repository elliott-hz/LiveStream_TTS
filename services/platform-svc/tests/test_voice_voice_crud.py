"""
Integration tests: Voice CRUD (create -> get -> update -> list -> delete),
clone task management, and preview.
"""

import pytest

from services.platform_svc.src.modules.voice.services.voice_service import VoiceService


@pytest.mark.asyncio
async def test_create_voice(db_session):
    """Create a voice and verify it's persisted."""
    svc = VoiceService(db=db_session)
    voice = await svc.create_voice(
        store_id="store_001",
        name="测试音色A",
        gender="female",
        age_range="25-35",
        language="zh-CN",
        style="professional",
        is_public=True,
    )
    assert voice.voice_id is not None
    assert voice.name == "测试音色A"
    assert voice.store_id == "store_001"
    assert voice.gender == "female"
    assert voice.style == "professional"
    assert voice.status == "active"
    assert voice.is_public is True
    assert voice.created_at is not None
    assert voice.updated_at is not None


@pytest.mark.asyncio
async def test_get_voice(db_session):
    """Create and then fetch a voice by ID."""
    svc = VoiceService(db=db_session)
    created = await svc.create_voice(
        store_id="store_001",
        name="可查询的音色",
    )
    fetched = await svc.get_voice(created.voice_id)
    assert fetched.voice_id == created.voice_id
    assert fetched.name == "可查询的音色"


@pytest.mark.asyncio
async def test_get_voice_not_found(db_session):
    """Fetching a non-existent voice should raise AppError."""
    svc = VoiceService(db=db_session)
    with pytest.raises(Exception) as excinfo:
        await svc.get_voice("non_existent_id")
    assert "not found" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_update_voice(db_session):
    """Update name, age_range, and style of a voice."""
    svc = VoiceService(db=db_session)
    voice = await svc.create_voice(
        store_id="store_001", name="原名称"
    )
    updated = await svc.update_voice(
        voice_id=voice.voice_id,
        name="新名称",
        style="lively",
        is_public=True,
    )
    assert updated.name == "新名称"
    assert updated.style == "lively"
    assert updated.is_public is True


@pytest.mark.asyncio
async def test_list_voices(db_session):
    """List voices with pagination and filters."""
    svc = VoiceService(db=db_session)
    for i in range(5):
        gender = "female" if i % 2 == 0 else "male"
        style = "professional" if i < 3 else "lively"
        await svc.create_voice(
            store_id="store_001",
            name=f"音色{i}",
            gender=gender,
            style=style,
        )

    # All voices
    voices, total = await svc.list_voices(store_id="store_001")
    assert total == 5
    assert len(voices) == 5

    # Gender filter
    voices, total = await svc.list_voices(store_id="store_001", gender="female")
    assert total == 3

    # Style filter
    voices, total = await svc.list_voices(store_id="store_001", style="lively")
    assert total == 2

    # Pagination
    voices, total = await svc.list_voices(store_id="store_001", page=1, page_size=2)
    assert len(voices) == 2
    assert total == 5

    # Different store
    voices, total = await svc.list_voices(store_id="store_002")
    assert total == 0


@pytest.mark.asyncio
async def test_delete_voice(db_session):
    """Delete a voice and verify it's gone."""
    svc = VoiceService(db=db_session)
    voice = await svc.create_voice(
        store_id="store_001", name="待删除音色"
    )
    await svc.delete_voice(voice.voice_id)

    with pytest.raises(Exception) as excinfo:
        await svc.get_voice(voice.voice_id)
    assert "not found" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_create_voice_invalid(db_session):
    """Creating a voice without required fields should raise."""
    svc = VoiceService(db=db_session)
    with pytest.raises(Exception) as excinfo:
        await svc.create_voice(store_id="", name="")
    assert "store_id" in str(excinfo.value).lower() or "name" in str(excinfo.value).lower()

    with pytest.raises(Exception) as excinfo:
        await svc.create_voice(store_id="s1", name="valid", gender="unknown")
    assert "gender" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_start_clone_and_get_task(db_session):
    """Start a clone task and retrieve it."""
    svc = VoiceService(db=db_session)
    voice = await svc.create_voice(
        store_id="store_001", name="待克隆音色"
    )

    task = await svc.start_clone(voice_id=voice.voice_id)
    assert task.task_id is not None
    assert task.voice_id == voice.voice_id
    assert task.status == "uploading"
    assert task.progress_percent == 0

    # Verify voice status changed to cloning
    updated_voice = await svc.get_voice(voice.voice_id)
    assert updated_voice.status == "cloning"

    # Fetch the task
    fetched = await svc.get_clone_task(task.task_id)
    assert fetched.task_id == task.task_id
    assert fetched.status == "uploading"


@pytest.mark.asyncio
async def test_preview_voice(db_session):
    """Preview a voice and get a URL + duration."""
    svc = VoiceService(db=db_session)
    voice = await svc.create_voice(
        store_id="store_001", name="预览音色"
    )

    result = await svc.preview_voice(
        voice_id=voice.voice_id,
        text="欢迎来到我的直播间",
    )
    assert "preview_url" in result
    assert result["preview_url"].startswith("https://")
    assert result["duration_ms"] > 0
    assert result["duration_ms"] == len("欢迎来到我的直播间") * 80
