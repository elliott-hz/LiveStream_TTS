"""
Tests for AI Script Generator.

Since the DeepSeek API key is typically not set in test/dev environments,
these tests verify that the template-based fallback generation works correctly.
"""

import pytest

from src.config import ScriptConfig
from src.services.ai_generator import AIGenerator


@pytest.fixture
def config():
    """Create a ScriptConfig for testing (no API key by default)."""
    return ScriptConfig()


@pytest.fixture
def generator(config):
    """Create an AIGenerator instance."""
    return AIGenerator(config)


@pytest.mark.asyncio
async def test_generate_script_template_fallback_basic(generator):
    """Test that template-based generation returns a valid script structure."""
    sections = await generator.generate_script(
        product_name="测试连衣裙",
        industry="女装",
        style="passionate",
        selling_points=["高透气面料", "修身显瘦", "多色可选"],
        target_duration_seconds=120,
    )

    assert isinstance(sections, list)
    assert len(sections) >= 4  # At least 4 sections for any style

    # Check structure of each section
    for section in sections:
        assert "order" in section
        assert "type" in section
        assert "text" in section
        assert "duration_estimate_ms" in section
        assert "emotion" in section
        assert "action" in section
        assert "show_product_card" in section


@pytest.mark.asyncio
async def test_generate_script_all_styles(generator):
    """Test that all script styles produce valid output."""
    styles = ["passionate", "professional", "story", "comparison", "flash_sale"]

    for style in styles:
        sections = await generator.generate_script(
            product_name=f"测试产品-{style}",
            industry="综合",
            style=style,
            selling_points=["卖点A", "卖点B"],
            target_duration_seconds=90,
        )

        assert isinstance(sections, list), f"Style '{style}' failed"
        assert len(sections) >= 3, f"Style '{style}' too few sections"


@pytest.mark.asyncio
async def test_generate_script_duration_distribution(generator):
    """Test that total duration is roughly close to target."""
    target_seconds = 120
    sections = await generator.generate_script(
        product_name="测试产品",
        industry="3C数码",
        style="professional",
        selling_points=["高性能", "长续航"],
        target_duration_seconds=target_seconds,
    )

    total_ms = sum(s["duration_estimate_ms"] for s in sections)
    total_seconds = total_ms / 1000

    # Allow 50% tolerance since template-based distribution is approximate
    assert total_seconds >= target_seconds * 0.5
    assert total_seconds <= target_seconds * 1.5


@pytest.mark.asyncio
async def test_generate_script_with_selling_points(generator):
    """Test that selling points are included in generated sections."""
    selling_points = ["透气面料", "抗菌处理"]
    sections = await generator.generate_script(
        product_name="测试T恤",
        industry="女装",
        style="passionate",
        selling_points=selling_points,
        target_duration_seconds=60,
    )

    # Check that selling points are referenced in highlight_selling_point
    highlights = [s.get("highlight_selling_point", "") for s in sections]
    non_empty = [h for h in highlights if h]
    assert len(non_empty) > 0, "Selling points should be assigned to sections"


@pytest.mark.asyncio
async def test_generate_script_empty_selling_points(generator):
    """Test generation without selling points."""
    sections = await generator.generate_script(
        product_name="测试产品",
        industry="食品",
        style="flash_sale",
        selling_points=[],
        target_duration_seconds=60,
    )

    assert isinstance(sections, list)
    assert len(sections) >= 3


@pytest.mark.asyncio
async def test_generate_script_unknown_style_fallback(generator):
    """Test that unknown styles fall back to passive."""
    sections = await generator.generate_script(
        product_name="测试",
        industry="综合",
        style="nonexistent_style",
        selling_points=[],
        target_duration_seconds=30,
    )

    assert isinstance(sections, list)
    assert len(sections) >= 3


@pytest.mark.asyncio
async def test_generator_close(generator):
    """Test that generator can be closed without error."""
    await generator.close()
    # Closing again should be safe
    await generator.close()


@pytest.mark.asyncio
async def test_generate_script_section_types(generator):
    """Test that generated sections have valid section types."""
    valid_types = {
        "opening", "product_intro", "fabric_detail", "size_guide",
        "try_on", "price_promo", "call_to_action", "closing", "qa",
    }

    sections = await generator.generate_script(
        product_name="测试手机",
        industry="3C数码",
        style="professional",
        selling_points=["高清屏幕", "快速充电"],
        target_duration_seconds=120,
    )

    for section in sections:
        assert section["type"] in valid_types, (
            f"Invalid section type: {section['type']}"
        )


@pytest.mark.asyncio
async def test_generate_script_ordering(generator):
    """Test that sections are sequentially ordered."""
    sections = await generator.generate_script(
        product_name="测试商品",
        industry="综合",
        style="passionate",
        selling_points=["卖点"],
        target_duration_seconds=60,
    )

    orders = [s["order"] for s in sections]
    assert orders == sorted(orders), "Sections should be in order"
    assert orders[0] == 1, "First section should be order 1"
