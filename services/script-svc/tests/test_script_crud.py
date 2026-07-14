"""
Tests for Script CRUD and version management operations.

Uses an in-memory SQLite database via the shared async_db fixture.
"""

import pytest
from sqlalchemy import select

from libs.testing import async_db  # noqa: F401
from src.models.script import Script, ScriptSection, ScriptVersion
from src.services.script_service import ScriptService


@pytest.mark.asyncio
async def test_create_script(async_db):  # noqa: F811
    """Test creating a script with sections."""
    svc = ScriptService(async_db)
    script = await svc.create_script(
        product_id="prod_001",
        store_id="store_001",
        style="passionate",
        sections_data=[
            {"order": 1, "type": "opening", "text": "欢迎来到直播间！"},
            {"order": 2, "type": "product_intro", "text": "今天给大家介绍一款好物"},
        ],
    )

    assert script.product_id == "prod_001"
    assert script.store_id == "store_001"
    assert script.style == "passionate"
    assert script.status == "draft"
    assert script.version == 1

    # Verify sections
    assert len(script.sections) == 2
    assert script.sections[0].type == "opening"
    assert script.sections[1].type == "product_intro"


@pytest.mark.asyncio
async def test_get_script_not_found(async_db):  # noqa: F811
    """Test that getting a non-existent script raises error."""
    svc = ScriptService(async_db)
    from libs.common.errors import AppError

    with pytest.raises(AppError, match="not found"):
        await svc.get_script("00000000-0000-0000-0000-000000000000")


@pytest.mark.asyncio
async def test_create_and_get_script(async_db):  # noqa: F811
    """Test creating and then retrieving a script."""
    svc = ScriptService(async_db)
    created = await svc.create_script(
        product_id="prod_002",
        store_id="store_001",
        style="professional",
        sections_data=[
            {"order": 1, "type": "opening", "text": "大家好！"},
        ],
    )

    fetched = await svc.get_script(str(created.script_id))
    assert fetched.script_id == created.script_id
    assert fetched.product_id == "prod_002"
    assert fetched.style == "professional"


@pytest.mark.asyncio
async def test_update_script_sections(async_db):  # noqa: F811
    """Test updating script sections (replacement)."""
    svc = ScriptService(async_db)
    script = await svc.create_script(
        product_id="prod_003",
        store_id="store_001",
        style="passionate",
        sections_data=[
            {"order": 1, "type": "opening", "text": "原始开场"},
        ],
    )

    updated = await svc.update_script(
        script_id=str(script.script_id),
        sections_data=[
            {"order": 1, "type": "opening", "text": "新的开场"},
            {"order": 2, "type": "closing", "text": "新的结尾"},
        ],
    )

    assert len(updated.sections) == 2
    assert updated.sections[0].text == "新的开场"
    assert updated.sections[1].text == "新的结尾"


@pytest.mark.asyncio
async def test_update_script_style(async_db):  # noqa: F811
    """Test updating just the style of a script."""
    svc = ScriptService(async_db)
    script = await svc.create_script(
        product_id="prod_004",
        store_id="store_001",
        style="passionate",
    )

    updated = await svc.update_script(
        script_id=str(script.script_id),
        style="story",
    )
    assert updated.style == "story"


@pytest.mark.asyncio
async def test_delete_script(async_db):  # noqa: F811
    """Test deleting a script."""
    svc = ScriptService(async_db)
    script = await svc.create_script(
        product_id="prod_005",
        store_id="store_001",
        style="passionate",
    )
    script_id = str(script.script_id)

    await svc.delete_script(script_id)

    from libs.common.errors import AppError
    with pytest.raises(AppError, match="not found"):
        await svc.get_script(script_id)


@pytest.mark.asyncio
async def test_list_scripts_pagination(async_db):  # noqa: F811
    """Test listing scripts with pagination."""
    svc = ScriptService(async_db)

    # Create 5 scripts
    for i in range(5):
        await svc.create_script(
            product_id=f"prod_{i:03d}",
            store_id="store_list_test",
            style="passionate",
        )

    scripts, total = await svc.list_scripts(
        store_id="store_list_test",
        page=1,
        page_size=3,
    )

    assert total == 5
    assert len(scripts) == 3

    # Second page
    scripts2, total2 = await svc.list_scripts(
        store_id="store_list_test",
        page=2,
        page_size=3,
    )
    assert len(scripts2) == 2


@pytest.mark.asyncio
async def test_list_scripts_filter_by_status(async_db):  # noqa: F811
    """Test filtering scripts by status."""
    svc = ScriptService(async_db)

    # Create scripts with different statuses
    s1 = await svc.create_script(product_id="prod_a", store_id="store_filter", style="passionate")
    s2 = await svc.create_script(product_id="prod_b", store_id="store_filter", style="passionate")

    # Manually change statuses via DB
    s1.status = "approved"
    s2.status = "archived"
    await async_db.flush()

    scripts, total = await svc.list_scripts(
        store_id="store_filter",
        status="approved",
    )
    assert total == 1
    assert scripts[0].product_id == "prod_a"


@pytest.mark.asyncio
async def test_publish_version(async_db):  # noqa: F811
    """Test publishing a version creates a snapshot."""
    svc = ScriptService(async_db)
    script = await svc.create_script(
        product_id="prod_010",
        store_id="store_001",
        style="passionate",
        sections_data=[
            {"order": 1, "type": "opening", "text": "开场"},
            {"order": 2, "type": "closing", "text": "结尾"},
        ],
    )

    # Publish version
    published = await svc.publish_version(
        script_id=str(script.script_id),
        note="初始版本",
    )

    assert published.version == 2  # Incremented

    # Check version entry in DB
    stmt = select(ScriptVersion).where(
        ScriptVersion.script_id == script.script_id,
        ScriptVersion.version_number == 1,
    )
    result = await async_db.execute(stmt)
    version_entry = result.scalar_one_or_none()
    assert version_entry is not None
    assert version_entry.note == "初始版本"
    assert len(version_entry.sections_snapshot) == 2


@pytest.mark.asyncio
async def test_rollback_version(async_db):  # noqa: F811
    """Test rolling back to a previous version."""
    svc = ScriptService(async_db)
    script = await svc.create_script(
        product_id="prod_011",
        store_id="store_001",
        style="passionate",
        sections_data=[
            {"order": 1, "type": "opening", "text": "V1 开场"},
        ],
    )

    # Publish V1
    await svc.publish_version(script_id=str(script.script_id), note="V1")
    script_id = str(script.script_id)

    # Modify sections (V2)
    await svc.update_script(
        script_id=script_id,
        sections_data=[
            {"order": 1, "type": "opening", "text": "V2 开场"},
            {"order": 2, "type": "closing", "text": "V2 结尾"},
        ],
    )

    # Rollback to V1
    rolled_back = await svc.rollback_version(script_id=script_id, target_version=1)

    assert rolled_back.version == 3  # New version after rollback
    assert len(rolled_back.sections) == 1
    assert rolled_back.sections[0].text == "V1 开场"


@pytest.mark.asyncio
async def test_list_templates(async_db):  # noqa: F811
    """Test listing built-in templates."""
    svc = ScriptService(async_db)

    # All templates
    templates = await svc.list_templates()
    assert len(templates) >= 3  # At least 3 templates required

    # Filter by industry
    fashion_templates = await svc.list_templates(industry="女装")
    assert len(fashion_templates) >= 1
    assert fashion_templates[0].industry == "女装"

    # Filter by style
    story_templates = await svc.list_templates(style="story")
    assert len(story_templates) >= 1
    assert story_templates[0].style == "story"


@pytest.mark.asyncio
async def test_list_scripts_empty(async_db):  # noqa: F811
    """Test listing scripts when store has none."""
    svc = ScriptService(async_db)
    scripts, total = await svc.list_scripts(store_id="nonexistent_store")
    assert len(scripts) == 0
    assert total == 0


@pytest.mark.asyncio
async def test_create_script_no_sections(async_db):  # noqa: F811
    """Test creating a script without any sections."""
    svc = ScriptService(async_db)
    script = await svc.create_script(
        product_id="prod_no_sec",
        store_id="store_no_sec",
        style="passionate",
    )
    assert script.product_id == "prod_no_sec"
    assert len(script.sections) == 0


@pytest.mark.asyncio
async def test_cascade_delete_sections(async_db):  # noqa: F811
    """Test that deleting a script also deletes its sections."""
    svc = ScriptService(async_db)
    script = await svc.create_script(
        product_id="prod_cascade",
        store_id="store_cascade",
        style="passionate",
        sections_data=[
            {"order": 1, "type": "opening", "text": "会被级联删除"},
        ],
    )

    await svc.delete_script(str(script.script_id))

    # Verify sections are gone
    from sqlalchemy import select, func
    from src.models.script import ScriptSection

    stmt = select(func.count()).select_from(ScriptSection).where(
        ScriptSection.script_id == script.script_id
    )
    count = await async_db.scalar(stmt)
    assert count == 0
