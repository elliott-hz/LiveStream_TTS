"""
Integration tests: Avatar CRUD (create -> get -> update -> list -> delete)
and clone task management.
"""

import pytest

from services.platform_svc.src.modules.avatar.services.avatar_service import AvatarService


@pytest.mark.asyncio
async def test_create_avatar(db_session):
    """Create an avatar and verify it's persisted."""
    svc = AvatarService(db=db_session)
    avatar = await svc.create_avatar(
        store_id="store_001",
        name="测试数字人A",
        avatar_type="2d_real",
        custom_params={"skin_smooth": 0.8, "face_thin": 0.5, "eye_size": 0.3, "lip_thickness": 0.4},
    )
    assert avatar.avatar_id is not None
    assert avatar.name == "测试数字人A"
    assert avatar.store_id == "store_001"
    assert avatar.avatar_type == "2d_real"
    assert avatar.status == "active"
    assert avatar.custom_params == {"skin_smooth": 0.8, "face_thin": 0.5, "eye_size": 0.3, "lip_thickness": 0.4}
    assert avatar.created_at is not None
    assert avatar.updated_at is not None


@pytest.mark.asyncio
async def test_get_avatar(db_session):
    """Create and then fetch an avatar by ID."""
    svc = AvatarService(db=db_session)
    created = await svc.create_avatar(
        store_id="store_001",
        name="可查询的数字人",
    )
    fetched = await svc.get_avatar(created.avatar_id)
    assert fetched.avatar_id == created.avatar_id
    assert fetched.name == "可查询的数字人"


@pytest.mark.asyncio
async def test_get_avatar_not_found(db_session):
    """Fetching a non-existent avatar should raise AppError."""
    svc = AvatarService(db=db_session)
    with pytest.raises(Exception) as excinfo:
        await svc.get_avatar("non_existent_id")
    assert "not found" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_update_avatar(db_session):
    """Update name and custom_params of an avatar."""
    svc = AvatarService(db=db_session)
    avatar = await svc.create_avatar(
        store_id="store_001", name="原名"
    )
    updated = await svc.update_avatar(
        avatar_id=avatar.avatar_id,
        name="新名",
        custom_params={"skin_smooth": 0.9, "face_thin": 0.6, "eye_size": 0.5, "lip_thickness": 0.3},
    )
    assert updated.name == "新名"
    assert updated.custom_params["skin_smooth"] == 0.9


@pytest.mark.asyncio
async def test_list_avatars(db_session):
    """List avatars with pagination and filters."""
    svc = AvatarService(db=db_session)
    for i in range(5):
        atype = "2d_real" if i % 2 == 0 else "3d_cartoon"
        await svc.create_avatar(
            store_id="store_001",
            name=f"数字人{i}",
            avatar_type=atype,
        )

    # All avatars
    avatars, total = await svc.list_avatars(store_id="store_001")
    assert total == 5
    assert len(avatars) == 5

    # Type filter
    avatars, total = await svc.list_avatars(store_id="store_001", avatar_type="2d_real")
    assert total == 3

    # Pagination
    avatars, total = await svc.list_avatars(store_id="store_001", page=1, page_size=2)
    assert len(avatars) == 2
    assert total == 5

    # Different store
    avatars, total = await svc.list_avatars(store_id="store_002")
    assert total == 0


@pytest.mark.asyncio
async def test_delete_avatar(db_session):
    """Delete an avatar and verify it's gone."""
    svc = AvatarService(db=db_session)
    avatar = await svc.create_avatar(
        store_id="store_001", name="待删除数字人"
    )
    await svc.delete_avatar(avatar.avatar_id)

    with pytest.raises(Exception) as excinfo:
        await svc.get_avatar(avatar.avatar_id)
    assert "not found" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_create_avatar_invalid(db_session):
    """Creating an avatar without required fields should raise."""
    svc = AvatarService(db=db_session)
    with pytest.raises(Exception) as excinfo:
        await svc.create_avatar(store_id="", name="")
    assert "store_id" in str(excinfo.value).lower() or "name" in str(excinfo.value).lower()

    with pytest.raises(Exception) as excinfo:
        await svc.create_avatar(store_id="s1", name="valid", avatar_type="unknown")
    assert "avatar_type" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_start_clone_and_get_task(db_session):
    """Start a clone task and retrieve it."""
    svc = AvatarService(db=db_session)
    avatar = await svc.create_avatar(
        store_id="store_001", name="待克隆数字人"
    )

    task = await svc.start_clone(avatar_id=avatar.avatar_id)
    assert task.task_id is not None
    assert task.avatar_id == avatar.avatar_id
    assert task.status == "uploading"
    assert task.progress_percent == 0

    # Verify avatar status changed to cloning
    updated = await svc.get_avatar(avatar.avatar_id)
    assert updated.status == "cloning"

    # Fetch the task
    fetched = await svc.get_clone_task(task.task_id)
    assert fetched.task_id == task.task_id
    assert fetched.status == "uploading"


@pytest.mark.asyncio
async def test_create_avatar_with_3d_type(db_session):
    """Create an avatar with 3D cartoon type."""
    svc = AvatarService(db=db_session)
    avatar = await svc.create_avatar(
        store_id="store_001",
        name="3D卡通角色",
        avatar_type="3d_cartoon",
    )
    assert avatar.avatar_type == "3d_cartoon"
    assert avatar.status == "active"
