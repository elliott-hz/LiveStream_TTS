"""
Script Service — CRUD, version management, and template listing.

All business logic lives here. The gRPC and HTTP layers are thin adapters
that call into this service.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from libs.common.errors import (
    AppError,
    ErrorCode,
    Domain,
    not_found,
    invalid_arg,
    internal,
)

from src.models.script import (
    Script,
    ScriptSection,
    ScriptVersion,
    ScriptTemplateData,
)


# ── Built-in industry templates ──

_BUILTIN_TEMPLATES: list[ScriptTemplateData] = [
    ScriptTemplateData(
        template_id="tpl_fashion_001",
        name="女装直播带货脚本 (激情带货)",
        industry="女装",
        style="passionate",
        template_sections=[
            {"order": 1, "type": "opening", "text": "欢迎各位宝宝来到我的直播间！今天给大家带来一款超值的{product_name}！", "emotion": "excited", "duration_estimate_ms": 15000},
            {"order": 2, "type": "product_intro", "text": "首先来看看这款{product_name}，它的面料是{highlight_1}，穿在身上特别舒服！", "emotion": "happy", "duration_estimate_ms": 20000},
            {"order": 3, "type": "fabric_detail", "text": "大家看这个面料细节，{highlight_1}，透气性特别好，夏天穿完全没问题。", "emotion": "professional", "duration_estimate_ms": 25000},
            {"order": 4, "type": "size_guide", "text": "关于尺码，我身高{height}，体重{weight}，穿这个{size}码刚刚好，大家可以根据尺码表选择。", "emotion": "neutral", "duration_estimate_ms": 20000},
            {"order": 5, "type": "try_on", "text": "来，我给大家上身试穿一下，大家看看效果怎么样？", "emotion": "excited", "duration_estimate_ms": 30000},
            {"order": 6, "type": "price_promo", "text": "今天直播间专属价，只要{price}元！外面至少要卖{double_price}元，今天在我这里直接省一半！", "emotion": "excited", "duration_estimate_ms": 15000},
            {"order": 7, "type": "call_to_action", "text": "只有{stock}件库存，宝宝们赶紧点击下方小黄车下单，手慢无！", "emotion": "passionate", "duration_estimate_ms": 10000},
            {"order": 8, "type": "closing", "text": "感谢大家的支持，下单的宝宝记得给主播点个关注，后续更多好货等着你！", "emotion": "warm", "duration_estimate_ms": 10000},
        ],
        description="适用于服装类产品的激情带货风格脚本，包含面料介绍、尺码推荐、试穿展示、限时促销等环节",
    ),
    ScriptTemplateData(
        template_id="tpl_3c_001",
        name="3C数码产品专业评测脚本",
        industry="3C数码",
        style="professional",
        template_sections=[
            {"order": 1, "type": "opening", "text": "大家好，欢迎来到评测时间！今天我们来深度评测这款{product_name}。", "emotion": "neutral", "duration_estimate_ms": 10000},
            {"order": 2, "type": "product_intro", "text": "先看外观设计，{product_name}采用了{highlight_1}工艺，整机重量只有{weight}克，非常便携。", "emotion": "professional", "duration_estimate_ms": 20000},
            {"order": 3, "type": "fabric_detail", "text": "核心配置方面，搭载了{highlight_2}处理器，{highlight_3}内存，跑分达到{score}分，性能释放非常激进。", "emotion": "professional", "duration_estimate_ms": 25000},
            {"order": 4, "type": "size_guide", "text": "尺寸为{size}，屏幕占比高达{screen_ratio}%，显示效果非常细腻。", "emotion": "neutral", "duration_estimate_ms": 15000},
            {"order": 5, "type": "try_on", "text": "我们来实际测试一下它的{highlight_4}表现，大家可以看到效果非常明显。", "emotion": "professional", "duration_estimate_ms": 30000},
            {"order": 6, "type": "price_promo", "text": "现在下单只要{price}元，还赠送价值{gift_value}元的配件礼包，性价比超高。", "emotion": "happy", "duration_estimate_ms": 15000},
            {"order": 7, "type": "call_to_action", "text": "点击下方链接下单，享受官方质保和7天无理由退货。", "emotion": "professional", "duration_estimate_ms": 10000},
            {"order": 8, "type": "closing", "text": "以上就是本期评测的全部内容，有任何问题欢迎在评论区留言，我们下期再见！", "emotion": "neutral", "duration_estimate_ms": 10000},
        ],
        description="适用于3C数码产品的专业评测风格脚本，包含外观设计、核心配置、实际测试、价格对比等环节",
    ),
    ScriptTemplateData(
        template_id="tpl_beauty_001",
        name="美妆产品种草带货脚本",
        industry="美妆",
        style="story",
        template_sections=[
            {"order": 1, "type": "opening", "text": "姐妹们！我今天必须给你们安利这个{product_name}，真的是我用过最好用的！", "emotion": "excited", "duration_estimate_ms": 12000},
            {"order": 2, "type": "product_intro", "text": "先说说我为什么推荐它，{product_name}主打{highlight_1}功效，特别适合{skin_type}肌肤。", "emotion": "warm", "duration_estimate_ms": 20000},
            {"order": 3, "type": "fabric_detail", "text": "它的成分党看过来，里面含有{highlight_2}、{highlight_3}等核心成分，温和不刺激。", "emotion": "professional", "duration_estimate_ms": 20000},
            {"order": 4, "type": "try_on", "text": "来，我直接在脸上给大家试一下效果，你们看这个质地，水润不粘腻。", "emotion": "happy", "duration_estimate_ms": 35000},
            {"order": 5, "type": "size_guide", "text": "一瓶{size}ml，每天用的话大概可以用{usage_duration}个月，性价比很高。", "emotion": "neutral", "duration_estimate_ms": 10000},
            {"order": 6, "type": "price_promo", "text": "今天直播间领券只要{price}元，还送{highlight_4}小样，相当于买一送一！", "emotion": "excited", "duration_estimate_ms": 15000},
            {"order": 7, "type": "call_to_action", "text": "只有1000份，卖完就没有了，小姐姐们赶紧冲！", "emotion": "passionate", "duration_estimate_ms": 8000},
            {"order": 8, "type": "closing", "text": "下单的姐妹记得回来反馈使用感受，有任何问题都可以找我，爱你们！", "emotion": "warm", "duration_estimate_ms": 10000},
        ],
        description="适用于美妆产品的故事种草风格脚本，包含个人使用体验、成分分析、上脸实测、限时优惠等环节",
    ),
    ScriptTemplateData(
        template_id="tpl_fs_001",
        name="限时秒杀对比测评脚本",
        industry="综合",
        style="comparison",
        template_sections=[
            {"order": 1, "type": "opening", "text": "各位家人们，今晚的秒杀专场正式开始！第一波福利就是这款{product_name}！", "emotion": "excited", "duration_estimate_ms": 10000},
            {"order": 2, "type": "product_intro", "text": "我们先来看看市面上同类产品的价格，{competitor_brand}卖{competitor_price}，而我们今天只要{price}！", "emotion": "passionate", "duration_estimate_ms": 20000},
            {"order": 3, "type": "fabric_detail", "text": "来我们看看细节对比，{product_name}的{highlight_1}明显比竞品好，{highlight_2}也更出色。", "emotion": "professional", "duration_estimate_ms": 25000},
            {"order": 4, "type": "try_on", "text": "我给大家实际演示一下{highlight_3}的效果，大家看清楚了！", "emotion": "happy", "duration_estimate_ms": 30000},
            {"order": 5, "type": "price_promo", "text": "今天秒杀价只要{price}元，比平时便宜了整整{discount}元！只有500份！", "emotion": "excited", "duration_estimate_ms": 12000},
            {"order": 6, "type": "call_to_action", "text": "倒计时3、2、1，上链接！手速要快！", "emotion": "passionate", "duration_estimate_ms": 8000},
            {"order": 7, "type": "closing", "text": "抢到的家人们打'已拍'让我看到你们！没抢到的别急，后面还有更多福利！", "emotion": "excited", "duration_estimate_ms": 10000},
        ],
        description="适用于限时秒杀场景的对比测评风格脚本，强调价格优势和产品差异化卖点",
    ),
    ScriptTemplateData(
        template_id="tpl_qa_001",
        name="食品带货互动问答脚本",
        industry="食品",
        style="passionate",
        template_sections=[
            {"order": 1, "type": "opening", "text": "吃货宝宝们看过来！今天给大家带来一款好吃到舔手指的{product_name}！", "emotion": "excited", "duration_estimate_ms": 10000},
            {"order": 2, "type": "product_intro", "text": "这款{product_name}来自{origin_place}，采用{highlight_1}工艺制作，口感{highlight_2}。", "emotion": "happy", "duration_estimate_ms": 20000},
            {"order": 3, "type": "fabric_detail", "text": "配料表非常干净，只有{ingredients}，没有任何添加剂，老人小孩都能放心吃。", "emotion": "professional", "duration_estimate_ms": 15000},
            {"order": 4, "type": "try_on", "text": "我替大家尝尝味道，嗯——就是这个味！{highlight_3}，真的绝了！", "emotion": "excited", "duration_estimate_ms": 25000},
            {"order": 5, "type": "price_promo", "text": "今天拍下{price}元/{count}{unit}，相当于每{unit}只要{unit_price}元！", "emotion": "passionate", "duration_estimate_ms": 12000},
            {"order": 6, "type": "qa", "text": "大家有什么问题打在公屏上，比如保质期多久、能不能发偏远地区等等，我来一一解答！", "emotion": "warm", "duration_estimate_ms": 30000},
            {"order": 7, "type": "call_to_action", "text": "库存有限，喜欢的朋友抓紧下单！买两份更划算，第二份半价！", "emotion": "excited", "duration_estimate_ms": 10000},
            {"order": 8, "type": "closing", "text": "感谢大家的支持，下单后48小时内发货，包邮到家！", "emotion": "warm", "duration_estimate_ms": 8000},
        ],
        description="适用于食品类产品的激情带货风格脚本，突出原材料、口感、健康属性，包含互动问答环节",
    ),
]


# ── Helper: map string status/style to proto enum values ──

_STATUS_MAP = {
    "draft": 1,
    "pending_review": 2,
    "approved": 3,
    "rejected": 4,
    "archived": 5,
}

_STYLE_MAP = {
    "passionate": 1,
    "professional": 2,
    "story": 3,
    "comparison": 4,
    "flash_sale": 5,
}

_SECTION_TYPE_MAP = {
    "opening": 1,
    "product_intro": 2,
    "fabric_detail": 3,
    "size_guide": 4,
    "try_on": 5,
    "price_promo": 6,
    "call_to_action": 7,
    "closing": 8,
    "qa": 9,
}

_REVERSE_STATUS = {v: k for k, v in _STATUS_MAP.items()}
_REVERSE_STYLE = {v: k for k, v in _STYLE_MAP.items()}
_REVERSE_SECTION_TYPE = {v: k for k, v in _SECTION_TYPE_MAP.items()}


class ScriptService:
    """CRUD + versioning + template business logic for scripts."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── CRUD ──

    async def create_script(
        self,
        product_id: str,
        store_id: str,
        style: str,
        sections_data: list[dict[str, Any]] | None = None,
        industry: str = "",
        created_by: str | None = None,
    ) -> Script:
        """Create a new script with optional sections."""
        script = Script(
            product_id=product_id,
            store_id=store_id,
            style=style or "passionate",
            industry=industry,
            status="draft",
            version=1,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(script)
        await self.db.flush()

        if sections_data:
            for sec_data in sections_data:
                section = ScriptSection(
                    script_id=script.script_id,
                    order=sec_data.get("order", 1),
                    type=sec_data.get("type", "opening"),
                    text=sec_data.get("text", ""),
                    duration_estimate_ms=sec_data.get("duration_estimate_ms", 0),
                    emotion=sec_data.get("emotion", "neutral"),
                    action=sec_data.get("action", ""),
                    show_product_card=sec_data.get("show_product_card", False),
                    highlight_selling_point=sec_data.get("highlight_selling_point"),
                )
                self.db.add(section)

        await self.db.flush()
        # Re-fetch with eager-loaded sections
        return await self.get_script(str(script.script_id))

    async def get_script(self, script_id: str) -> Script:
        """Get a script by ID, or raise not_found."""
        try:
            uid = uuid.UUID(script_id)
        except ValueError:
            raise invalid_arg("script_id", "must be a valid UUID")

        stmt = (
            select(Script)
            .where(Script.script_id == uid)
            .options(selectinload(Script.sections))
        )
        result = await self.db.execute(stmt)
        script = result.scalar_one_or_none()
        if script is None:
            raise not_found("Script", script_id)
        return script

    async def update_script(
        self,
        script_id: str,
        style: str | None = None,
        sections_data: list[dict[str, Any]] | None = None,
        updated_by: str | None = None,
    ) -> Script:
        """Update script metadata and/or replace sections."""
        script = await self.get_script(script_id)

        if style is not None:
            script.style = style
        if updated_by is not None:
            script.updated_by = updated_by

        if sections_data is not None:
            # Delete existing sections (both DB and relationship)
            for sec in list(script.sections):
                await self.db.delete(sec)
            script.sections.clear()

            for sec_data in sections_data:
                section = ScriptSection(
                    script_id=script.script_id,
                    order=sec_data.get("order", 1),
                    type=sec_data.get("type", "opening"),
                    text=sec_data.get("text", ""),
                    duration_estimate_ms=sec_data.get("duration_estimate_ms", 0),
                    emotion=sec_data.get("emotion", "neutral"),
                    action=sec_data.get("action", ""),
                    show_product_card=sec_data.get("show_product_card", False),
                    highlight_selling_point=sec_data.get("highlight_selling_point"),
                )
                script.sections.append(section)

        # Recalculate total duration
        await self.db.flush()
        script.total_duration_estimate_ms = sum(
            s.duration_estimate_ms for s in script.sections
        )
        await self.db.flush()
        return await self.get_script(script_id)

    async def delete_script(self, script_id: str) -> None:
        """Delete a script (and cascade sections/versions)."""
        script = await self.get_script(script_id)
        await self.db.delete(script)
        await self.db.flush()

    async def list_scripts(
        self,
        store_id: str,
        status: str | None = None,
        product_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Script], int]:
        """List scripts with filtering and pagination. Returns (scripts, total_count)."""
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        query = select(Script).where(Script.store_id == store_id)

        if status:
            query = query.where(Script.status == status)
        if product_id:
            query = query.where(Script.product_id == product_id)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query)
        total = total or 0

        # Paginate
        stmt = query.order_by(Script.updated_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size)
        result = await self.db.execute(stmt)
        scripts = list(result.scalars().all())

        return scripts, total

    # ── Version Management ──

    async def publish_version(self, script_id: str, note: str | None = None) -> Script:
        """Increment script version, snapshot current sections into ScriptVersion."""
        script = await self.get_script(script_id)

        # Build sections snapshot with eager-loaded sections
        script = await self.get_script(script_id)
        snapshot = [
            {
                "section_id": str(s.section_id),
                "order": s.order,
                "type": s.type,
                "text": s.text,
                "duration_estimate_ms": s.duration_estimate_ms,
                "emotion": s.emotion,
                "action": s.action,
                "show_product_card": s.show_product_card,
                "highlight_selling_point": s.highlight_selling_point,
            }
            for s in script.sections
        ]

        version_entry = ScriptVersion(
            script_id=script.script_id,
            version_number=script.version,
            sections_snapshot=snapshot,
            note=note,
        )
        self.db.add(version_entry)

        script.version += 1
        await self.db.flush()
        return await self.get_script(script_id)

    async def rollback_version(self, script_id: str, target_version: int) -> Script:
        """Restore sections from a previous version snapshot."""
        script = await self.get_script(script_id)

        # Find the target version entry
        stmt = select(ScriptVersion).where(
            ScriptVersion.script_id == script.script_id,
            ScriptVersion.version_number == target_version,
        )
        result = await self.db.execute(stmt)
        version_entry = result.scalar_one_or_none()
        if version_entry is None:
            raise AppError(
                ErrorCode.NOT_FOUND,
                f"Version {target_version} not found for script {script_id}",
                domain=Domain.SCRIPT,
            )

        # Restore from snapshot: delete current sections, create new ones
        for sec in list(script.sections):
            await self.db.delete(sec)
        script.sections.clear()

        snapshot = version_entry.sections_snapshot
        for sec_data in snapshot:
            section = ScriptSection(
                script_id=script.script_id,
                order=sec_data.get("order", 1),
                type=sec_data.get("type", "opening"),
                text=sec_data.get("text", ""),
                duration_estimate_ms=sec_data.get("duration_estimate_ms", 0),
                emotion=sec_data.get("emotion", "neutral"),
                action=sec_data.get("action", ""),
                show_product_card=sec_data.get("show_product_card", False),
                highlight_selling_point=sec_data.get("highlight_selling_point"),
            )
            script.sections.append(section)

        script.version += 1
        await self.db.flush()
        return await self.get_script(script_id)

    # ── Templates ──

    async def list_templates(
        self,
        industry: str | None = None,
        style: str | None = None,
    ) -> list[ScriptTemplateData]:
        """Return built-in templates, optionally filtered."""
        templates = _BUILTIN_TEMPLATES
        if industry:
            templates = [t for t in templates if t.industry == industry]
        if style:
            templates = [t for t in templates if t.style == style]
        return templates
