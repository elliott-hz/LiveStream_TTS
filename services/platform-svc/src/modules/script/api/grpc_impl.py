"""
gRPC implementation for ScriptService.

Implements all 10 RPCs from script/v1/script.proto by delegating to the
business-logic ScriptService and AIGenerator layers.
"""

import json
import time
import traceback
from typing import Any

import grpc
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common.errors import AppError, ErrorCode, Domain
from libs.common.logging import get_logger
from libs.db import Base

from libs.proto.common.v1 import common_pb2
from libs.proto.script.v1 import script_pb2, script_pb2_grpc

from ..config import ScriptConfig
from src.services.script_service import ScriptService
from src.services.ai_generator import AIGenerator

logger = get_logger(__name__)


def _proto_audit_info(created_by: str | None, updated_by: str | None, created_at, updated_at) -> common_pb2.AuditInfo:
    """Convert timestamps to proto AuditInfo."""
    ts = common_pb2.Timestamps(
        created_at=int(created_at.timestamp() * 1000) if created_at else 0,
        updated_at=int(updated_at.timestamp() * 1000) if updated_at else 0,
    )
    return common_pb2.AuditInfo(
        created_by=created_by or "",
        updated_by=updated_by or "",
        timestamps=ts,
    )


def _section_to_proto(section) -> script_pb2.ScriptSection:
    """Convert ORM ScriptSection to proto ScriptSection."""
    section_type = _section_type_name_to_value(section.type)
    return script_pb2.ScriptSection(
        section_id=str(section.section_id),
        order=section.order,
        type=section_type,
        text=section.text or "",
        duration_estimate_ms=section.duration_estimate_ms or 0,
        emotion=section.emotion or "",
        action=section.action or "",
        show_product_card=section.show_product_card or False,
        highlight_selling_point=section.highlight_selling_point or "",
    )


def _section_dict_to_proto(sec: dict[str, Any]) -> script_pb2.ScriptSection:
    """Convert section dict to proto ScriptSection."""
    return script_pb2.ScriptSection(
        section_id=sec.get("section_id", ""),
        order=sec.get("order", 1),
        type=_section_type_name_to_value(sec.get("type", "opening")),
        text=sec.get("text", ""),
        duration_estimate_ms=sec.get("duration_estimate_ms", 0),
        emotion=sec.get("emotion", ""),
        action=sec.get("action", ""),
        show_product_card=sec.get("show_product_card", False),
        highlight_selling_point=sec.get("highlight_selling_point", ""),
    )


def _proto_error_to_grpc_context(error: AppError, context: grpc.aio.ServicerContext) -> script_pb2.Script:
    """Set gRPC context error from an AppError, returning an empty Script."""
    grpc_code = _app_error_to_grpc_code(error)
    context.set_code(grpc_code)
    context.set_details(error.message)
    return script_pb2.Script()


def _app_error_to_grpc_code(error: AppError) -> grpc.StatusCode:
    """Map AppError error codes to gRPC status codes."""
    code_map = {
        ErrorCode.UNAUTHENTICATED: grpc.StatusCode.UNAUTHENTICATED,
        ErrorCode.PERMISSION_DENIED: grpc.StatusCode.PERMISSION_DENIED,
        ErrorCode.INVALID_ARGUMENT: grpc.StatusCode.INVALID_ARGUMENT,
        ErrorCode.MISSING_REQUIRED_FIELD: grpc.StatusCode.INVALID_ARGUMENT,
        ErrorCode.VALUE_OUT_OF_RANGE: grpc.StatusCode.OUT_OF_RANGE,
        ErrorCode.NOT_FOUND: grpc.StatusCode.NOT_FOUND,
        ErrorCode.SCRIPT_NOT_FOUND: grpc.StatusCode.NOT_FOUND,
        ErrorCode.DUPLICATE_RESOURCE: grpc.StatusCode.ALREADY_EXISTS,
        ErrorCode.INTERNAL_ERROR: grpc.StatusCode.INTERNAL,
        ErrorCode.DATABASE_ERROR: grpc.StatusCode.INTERNAL,
        ErrorCode.LLM_API_ERROR: grpc.StatusCode.UNAVAILABLE,
    }
    return code_map.get(error.code, grpc.StatusCode.UNKNOWN)


def _section_type_name_to_value(name: str) -> int:
    mapping = {
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
    return mapping.get(name, 0)


def _section_type_value_to_name(value: int) -> str:
    mapping = {
        1: "opening",
        2: "product_intro",
        3: "fabric_detail",
        4: "size_guide",
        5: "try_on",
        6: "price_promo",
        7: "call_to_action",
        8: "closing",
        9: "qa",
    }
    return mapping.get(value, "opening")


def _style_name_to_value(name: str) -> int:
    mapping = {
        "passionate": 1,
        "professional": 2,
        "story": 3,
        "comparison": 4,
        "flash_sale": 5,
    }
    return mapping.get(name, 0)


def _style_value_to_name(value: int) -> str:
    mapping = {
        1: "passionate",
        2: "professional",
        3: "story",
        4: "comparison",
        5: "flash_sale",
    }
    return mapping.get(value, "passionate")


def _status_name_to_value(name: str) -> int:
    mapping = {
        "draft": 1,
        "pending_review": 2,
        "approved": 3,
        "rejected": 4,
        "archived": 5,
    }
    return mapping.get(name, 0)


def _status_value_to_name(value: int) -> str:
    mapping = {
        1: "draft",
        2: "pending_review",
        3: "approved",
        4: "rejected",
        5: "archived",
    }
    return mapping.get(value, "draft")


def _script_to_proto(script) -> script_pb2.Script:
    """Convert ORM Script + sections to proto Script."""
    sections = [_section_to_proto(s) for s in script.sections] if script.sections else []

    return script_pb2.Script(
        script_id=str(script.script_id),
        product_id=script.product_id or "",
        store_id=script.store_id or "",
        version=script.version or 1,
        status=_status_name_to_value(script.status or "draft"),
        style=_style_name_to_value(script.style or "passionate"),
        industry=script.industry or "",
        sections=sections,
        total_duration_estimate_ms=script.total_duration_estimate_ms or 0,
        ai_generated_prompt=script.ai_generated_prompt or "",
        audit_info=_proto_audit_info(
            script.created_by, script.updated_by,
            script.created_at, script.updated_at,
        ),
    )


def _section_proto_to_dict(section_proto) -> dict[str, Any]:
    """Convert proto ScriptSection to dict for the service layer."""
    return {
        "section_id": section_proto.section_id,
        "order": section_proto.order,
        "type": _section_type_value_to_name(section_proto.type),
        "text": section_proto.text,
        "duration_estimate_ms": section_proto.duration_estimate_ms,
        "emotion": section_proto.emotion,
        "action": section_proto.action,
        "show_product_card": section_proto.show_product_card,
        "highlight_selling_point": section_proto.highlight_selling_point,
    }


class ScriptServiceServicer(script_pb2_grpc.ScriptServiceServicer):
    """gRPC servicer implementing all 10 script RPCs."""

    def __init__(self, db: AsyncSession, config: ScriptConfig):
        self.db = db
        self.config = config
        self.script_svc = ScriptService(db)
        self.ai_generator = AIGenerator(config)

    # ── CRUD ──

    async def CreateScript(self, request: script_pb2.CreateScriptRequest, context) -> script_pb2.Script:
        try:
            sections = [_section_proto_to_dict(s) for s in request.sections] if request.sections else None
            script = await self.script_svc.create_script(
                product_id=request.product_id,
                store_id=request.store_id,
                style=_style_value_to_name(request.style),
                sections_data=sections,
            )
            return _script_to_proto(script)
        except AppError as e:
            return _proto_error_to_grpc_context(e, context)
        except Exception as e:
            logger.exception("create_script.error")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return script_pb2.Script()

    async def GetScript(self, request: script_pb2.GetScriptRequest, context) -> script_pb2.Script:
        try:
            script = await self.script_svc.get_script(request.script_id)
            return _script_to_proto(script)
        except AppError as e:
            return _proto_error_to_grpc_context(e, context)
        except Exception as e:
            logger.exception("get_script.error")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return script_pb2.Script()

    async def UpdateScript(self, request: script_pb2.UpdateScriptRequest, context) -> script_pb2.Script:
        try:
            style = _style_value_to_name(request.style) if request.style else None
            sections = [_section_proto_to_dict(s) for s in request.sections] if request.sections else None
            script = await self.script_svc.update_script(
                script_id=request.script_id,
                style=style,
                sections_data=sections,
            )
            return _script_to_proto(script)
        except AppError as e:
            return _proto_error_to_grpc_context(e, context)
        except Exception as e:
            logger.exception("update_script.error")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return script_pb2.Script()

    async def DeleteScript(self, request: script_pb2.DeleteScriptRequest, context) -> common_pb2.Error:
        try:
            await self.script_svc.delete_script(request.script_id)
            return common_pb2.Error(code=0, message="ok")
        except AppError as e:
            context.set_code(_app_error_to_grpc_code(e))
            context.set_details(e.message)
            return common_pb2.Error(code=e.full_code, message=e.message, details=e.details)
        except Exception as e:
            logger.exception("delete_script.error")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return common_pb2.Error(code=5001, message=str(e))

    async def ListScripts(self, request: script_pb2.ListScriptsRequest, context) -> script_pb2.ListScriptsResponse:
        try:
            status = _status_value_to_name(request.status) if request.status else None
            page = request.pagination.page if request.pagination and request.pagination.page else 1
            page_size = request.pagination.page_size if request.pagination and request.pagination.page_size else 20

            scripts, total = await self.script_svc.list_scripts(
                store_id=request.store_id,
                status=status,
                product_id=request.product_id or None,
                page=page,
                page_size=page_size,
            )

            total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
            page_info = common_pb2.PageInfo(
                page=page,
                page_size=page_size,
                total_count=total,
                total_pages=total_pages,
            )

            return script_pb2.ListScriptsResponse(
                scripts=[_script_to_proto(s) for s in scripts],
                page_info=page_info,
            )
        except AppError as e:
            context.set_code(_app_error_to_grpc_code(e))
            context.set_details(e.message)
            return script_pb2.ListScriptsResponse()
        except Exception as e:
            logger.exception("list_scripts.error")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return script_pb2.ListScriptsResponse()

    # ── AI Generation ──

    async def GenerateScript(self, request: script_pb2.GenerateScriptRequest, context) -> script_pb2.Script:
        try:
            style_name = _style_value_to_name(request.style)

            # Use AI generator to create sections
            sections = await self.ai_generator.generate_script(
                product_name=f"Product({request.product_id})",
                industry="",
                style=style_name,
                selling_points=list(request.highlight_selling_points),
                target_duration_seconds=request.target_duration_seconds or 120,
                extra_context=request.extra_context or "",
            )

            # Store the prompt used
            prompt_used = json.dumps({
                "product_id": request.product_id,
                "style": style_name,
                "target_duration_seconds": request.target_duration_seconds,
                "selling_points": list(request.highlight_selling_points),
            }, ensure_ascii=False)

            # Create script with generated sections
            script = await self.script_svc.create_script(
                product_id=request.product_id,
                store_id="ai_generated",
                style=style_name,
                sections_data=sections,
            )

            # Save the prompt
            script.ai_generated_prompt = prompt_used
            await self.db.flush()
            await self.db.refresh(script)

            return _script_to_proto(script)
        except AppError as e:
            return _proto_error_to_grpc_context(e, context)
        except Exception as e:
            logger.exception("generate_script.error")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return script_pb2.Script()

    # ── Version Management ──

    async def PublishVersion(self, request: script_pb2.PublishVersionRequest, context) -> script_pb2.Script:
        try:
            script = await self.script_svc.publish_version(
                script_id=request.script_id,
                note=request.note or None,
            )
            return _script_to_proto(script)
        except AppError as e:
            return _proto_error_to_grpc_context(e, context)
        except Exception as e:
            logger.exception("publish_version.error")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return script_pb2.Script()

    async def RollbackVersion(self, request: script_pb2.RollbackVersionRequest, context) -> script_pb2.Script:
        try:
            script = await self.script_svc.rollback_version(
                script_id=request.script_id,
                target_version=request.target_version,
            )
            return _script_to_proto(script)
        except AppError as e:
            return _proto_error_to_grpc_context(e, context)
        except Exception as e:
            logger.exception("rollback_version.error")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return script_pb2.Script()

    # ── Templates ──

    async def ListTemplates(self, request: script_pb2.ListTemplatesRequest, context) -> script_pb2.ListTemplatesResponse:
        try:
            industry = request.industry or None
            style = _style_value_to_name(request.style) if request.style else None

            templates = await self.script_svc.list_templates(
                industry=industry,
                style=style,
            )

            proto_templates = []
            for tpl in templates:
                style_value = _style_name_to_value(tpl.style)
                proto_sections = [
                    _section_dict_to_proto(s) for s in tpl.template_sections
                ]
                proto_tpl = script_pb2.ScriptTemplate(
                    template_id=tpl.template_id,
                    name=tpl.name,
                    industry=tpl.industry,
                    style=style_value,
                    template_sections=proto_sections,
                    description=tpl.description,
                )
                proto_templates.append(proto_tpl)

            return script_pb2.ListTemplatesResponse(templates=proto_templates)
        except Exception as e:
            logger.exception("list_templates.error")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return script_pb2.ListTemplatesResponse()
