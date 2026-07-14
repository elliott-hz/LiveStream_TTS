from common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ScriptStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SCRIPT_STATUS_UNSPECIFIED: _ClassVar[ScriptStatus]
    SCRIPT_STATUS_DRAFT: _ClassVar[ScriptStatus]
    SCRIPT_STATUS_PENDING_REVIEW: _ClassVar[ScriptStatus]
    SCRIPT_STATUS_APPROVED: _ClassVar[ScriptStatus]
    SCRIPT_STATUS_REJECTED: _ClassVar[ScriptStatus]
    SCRIPT_STATUS_ARCHIVED: _ClassVar[ScriptStatus]

class ScriptStyle(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SCRIPT_STYLE_UNSPECIFIED: _ClassVar[ScriptStyle]
    SCRIPT_STYLE_PASSIONATE: _ClassVar[ScriptStyle]
    SCRIPT_STYLE_PROFESSIONAL: _ClassVar[ScriptStyle]
    SCRIPT_STYLE_STORY: _ClassVar[ScriptStyle]
    SCRIPT_STYLE_COMPARISON: _ClassVar[ScriptStyle]
    SCRIPT_STYLE_FLASH_SALE: _ClassVar[ScriptStyle]

class SectionType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SECTION_TYPE_UNSPECIFIED: _ClassVar[SectionType]
    SECTION_TYPE_OPENING: _ClassVar[SectionType]
    SECTION_TYPE_PRODUCT_INTRO: _ClassVar[SectionType]
    SECTION_TYPE_FABRIC_DETAIL: _ClassVar[SectionType]
    SECTION_TYPE_SIZE_GUIDE: _ClassVar[SectionType]
    SECTION_TYPE_TRY_ON: _ClassVar[SectionType]
    SECTION_TYPE_PRICE_PROMO: _ClassVar[SectionType]
    SECTION_TYPE_CALL_TO_ACTION: _ClassVar[SectionType]
    SECTION_TYPE_CLOSING: _ClassVar[SectionType]
    SECTION_TYPE_QA: _ClassVar[SectionType]
SCRIPT_STATUS_UNSPECIFIED: ScriptStatus
SCRIPT_STATUS_DRAFT: ScriptStatus
SCRIPT_STATUS_PENDING_REVIEW: ScriptStatus
SCRIPT_STATUS_APPROVED: ScriptStatus
SCRIPT_STATUS_REJECTED: ScriptStatus
SCRIPT_STATUS_ARCHIVED: ScriptStatus
SCRIPT_STYLE_UNSPECIFIED: ScriptStyle
SCRIPT_STYLE_PASSIONATE: ScriptStyle
SCRIPT_STYLE_PROFESSIONAL: ScriptStyle
SCRIPT_STYLE_STORY: ScriptStyle
SCRIPT_STYLE_COMPARISON: ScriptStyle
SCRIPT_STYLE_FLASH_SALE: ScriptStyle
SECTION_TYPE_UNSPECIFIED: SectionType
SECTION_TYPE_OPENING: SectionType
SECTION_TYPE_PRODUCT_INTRO: SectionType
SECTION_TYPE_FABRIC_DETAIL: SectionType
SECTION_TYPE_SIZE_GUIDE: SectionType
SECTION_TYPE_TRY_ON: SectionType
SECTION_TYPE_PRICE_PROMO: SectionType
SECTION_TYPE_CALL_TO_ACTION: SectionType
SECTION_TYPE_CLOSING: SectionType
SECTION_TYPE_QA: SectionType

class Script(_message.Message):
    __slots__ = ("script_id", "product_id", "store_id", "version", "status", "style", "industry", "sections", "total_duration_estimate_ms", "ai_generated_prompt", "audit_info")
    SCRIPT_ID_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    STORE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    STYLE_FIELD_NUMBER: _ClassVar[int]
    INDUSTRY_FIELD_NUMBER: _ClassVar[int]
    SECTIONS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_DURATION_ESTIMATE_MS_FIELD_NUMBER: _ClassVar[int]
    AI_GENERATED_PROMPT_FIELD_NUMBER: _ClassVar[int]
    AUDIT_INFO_FIELD_NUMBER: _ClassVar[int]
    script_id: str
    product_id: str
    store_id: str
    version: int
    status: ScriptStatus
    style: ScriptStyle
    industry: str
    sections: _containers.RepeatedCompositeFieldContainer[ScriptSection]
    total_duration_estimate_ms: int
    ai_generated_prompt: str
    audit_info: _common_pb2.AuditInfo
    def __init__(self, script_id: _Optional[str] = ..., product_id: _Optional[str] = ..., store_id: _Optional[str] = ..., version: _Optional[int] = ..., status: _Optional[_Union[ScriptStatus, str]] = ..., style: _Optional[_Union[ScriptStyle, str]] = ..., industry: _Optional[str] = ..., sections: _Optional[_Iterable[_Union[ScriptSection, _Mapping]]] = ..., total_duration_estimate_ms: _Optional[int] = ..., ai_generated_prompt: _Optional[str] = ..., audit_info: _Optional[_Union[_common_pb2.AuditInfo, _Mapping]] = ...) -> None: ...

class ScriptSection(_message.Message):
    __slots__ = ("section_id", "order", "type", "text", "duration_estimate_ms", "emotion", "action", "show_product_card", "highlight_selling_point")
    SECTION_ID_FIELD_NUMBER: _ClassVar[int]
    ORDER_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    DURATION_ESTIMATE_MS_FIELD_NUMBER: _ClassVar[int]
    EMOTION_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    SHOW_PRODUCT_CARD_FIELD_NUMBER: _ClassVar[int]
    HIGHLIGHT_SELLING_POINT_FIELD_NUMBER: _ClassVar[int]
    section_id: str
    order: int
    type: SectionType
    text: str
    duration_estimate_ms: int
    emotion: str
    action: str
    show_product_card: bool
    highlight_selling_point: str
    def __init__(self, section_id: _Optional[str] = ..., order: _Optional[int] = ..., type: _Optional[_Union[SectionType, str]] = ..., text: _Optional[str] = ..., duration_estimate_ms: _Optional[int] = ..., emotion: _Optional[str] = ..., action: _Optional[str] = ..., show_product_card: _Optional[bool] = ..., highlight_selling_point: _Optional[str] = ...) -> None: ...

class CreateScriptRequest(_message.Message):
    __slots__ = ("product_id", "store_id", "style", "sections")
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    STORE_ID_FIELD_NUMBER: _ClassVar[int]
    STYLE_FIELD_NUMBER: _ClassVar[int]
    SECTIONS_FIELD_NUMBER: _ClassVar[int]
    product_id: str
    store_id: str
    style: ScriptStyle
    sections: _containers.RepeatedCompositeFieldContainer[ScriptSection]
    def __init__(self, product_id: _Optional[str] = ..., store_id: _Optional[str] = ..., style: _Optional[_Union[ScriptStyle, str]] = ..., sections: _Optional[_Iterable[_Union[ScriptSection, _Mapping]]] = ...) -> None: ...

class GetScriptRequest(_message.Message):
    __slots__ = ("script_id", "version")
    SCRIPT_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    script_id: str
    version: int
    def __init__(self, script_id: _Optional[str] = ..., version: _Optional[int] = ...) -> None: ...

class UpdateScriptRequest(_message.Message):
    __slots__ = ("script_id", "style", "sections")
    SCRIPT_ID_FIELD_NUMBER: _ClassVar[int]
    STYLE_FIELD_NUMBER: _ClassVar[int]
    SECTIONS_FIELD_NUMBER: _ClassVar[int]
    script_id: str
    style: ScriptStyle
    sections: _containers.RepeatedCompositeFieldContainer[ScriptSection]
    def __init__(self, script_id: _Optional[str] = ..., style: _Optional[_Union[ScriptStyle, str]] = ..., sections: _Optional[_Iterable[_Union[ScriptSection, _Mapping]]] = ...) -> None: ...

class DeleteScriptRequest(_message.Message):
    __slots__ = ("script_id",)
    SCRIPT_ID_FIELD_NUMBER: _ClassVar[int]
    script_id: str
    def __init__(self, script_id: _Optional[str] = ...) -> None: ...

class ListScriptsRequest(_message.Message):
    __slots__ = ("store_id", "status", "product_id", "pagination")
    STORE_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    PAGINATION_FIELD_NUMBER: _ClassVar[int]
    store_id: str
    status: ScriptStatus
    product_id: str
    pagination: _common_pb2.Pagination
    def __init__(self, store_id: _Optional[str] = ..., status: _Optional[_Union[ScriptStatus, str]] = ..., product_id: _Optional[str] = ..., pagination: _Optional[_Union[_common_pb2.Pagination, _Mapping]] = ...) -> None: ...

class ListScriptsResponse(_message.Message):
    __slots__ = ("scripts", "page_info")
    SCRIPTS_FIELD_NUMBER: _ClassVar[int]
    PAGE_INFO_FIELD_NUMBER: _ClassVar[int]
    scripts: _containers.RepeatedCompositeFieldContainer[Script]
    page_info: _common_pb2.PageInfo
    def __init__(self, scripts: _Optional[_Iterable[_Union[Script, _Mapping]]] = ..., page_info: _Optional[_Union[_common_pb2.PageInfo, _Mapping]] = ...) -> None: ...

class GenerateScriptRequest(_message.Message):
    __slots__ = ("product_id", "style", "target_duration_seconds", "highlight_selling_points", "extra_context")
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    STYLE_FIELD_NUMBER: _ClassVar[int]
    TARGET_DURATION_SECONDS_FIELD_NUMBER: _ClassVar[int]
    HIGHLIGHT_SELLING_POINTS_FIELD_NUMBER: _ClassVar[int]
    EXTRA_CONTEXT_FIELD_NUMBER: _ClassVar[int]
    product_id: str
    style: ScriptStyle
    target_duration_seconds: int
    highlight_selling_points: _containers.RepeatedScalarFieldContainer[str]
    extra_context: str
    def __init__(self, product_id: _Optional[str] = ..., style: _Optional[_Union[ScriptStyle, str]] = ..., target_duration_seconds: _Optional[int] = ..., highlight_selling_points: _Optional[_Iterable[str]] = ..., extra_context: _Optional[str] = ...) -> None: ...

class PublishVersionRequest(_message.Message):
    __slots__ = ("script_id", "note")
    SCRIPT_ID_FIELD_NUMBER: _ClassVar[int]
    NOTE_FIELD_NUMBER: _ClassVar[int]
    script_id: str
    note: str
    def __init__(self, script_id: _Optional[str] = ..., note: _Optional[str] = ...) -> None: ...

class RollbackVersionRequest(_message.Message):
    __slots__ = ("script_id", "target_version")
    SCRIPT_ID_FIELD_NUMBER: _ClassVar[int]
    TARGET_VERSION_FIELD_NUMBER: _ClassVar[int]
    script_id: str
    target_version: int
    def __init__(self, script_id: _Optional[str] = ..., target_version: _Optional[int] = ...) -> None: ...

class ListTemplatesRequest(_message.Message):
    __slots__ = ("industry", "style")
    INDUSTRY_FIELD_NUMBER: _ClassVar[int]
    STYLE_FIELD_NUMBER: _ClassVar[int]
    industry: str
    style: ScriptStyle
    def __init__(self, industry: _Optional[str] = ..., style: _Optional[_Union[ScriptStyle, str]] = ...) -> None: ...

class ListTemplatesResponse(_message.Message):
    __slots__ = ("templates",)
    TEMPLATES_FIELD_NUMBER: _ClassVar[int]
    templates: _containers.RepeatedCompositeFieldContainer[ScriptTemplate]
    def __init__(self, templates: _Optional[_Iterable[_Union[ScriptTemplate, _Mapping]]] = ...) -> None: ...

class ScriptTemplate(_message.Message):
    __slots__ = ("template_id", "name", "industry", "style", "template_sections", "description")
    TEMPLATE_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    INDUSTRY_FIELD_NUMBER: _ClassVar[int]
    STYLE_FIELD_NUMBER: _ClassVar[int]
    TEMPLATE_SECTIONS_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    template_id: str
    name: str
    industry: str
    style: ScriptStyle
    template_sections: _containers.RepeatedCompositeFieldContainer[ScriptSection]
    description: str
    def __init__(self, template_id: _Optional[str] = ..., name: _Optional[str] = ..., industry: _Optional[str] = ..., style: _Optional[_Union[ScriptStyle, str]] = ..., template_sections: _Optional[_Iterable[_Union[ScriptSection, _Mapping]]] = ..., description: _Optional[str] = ...) -> None: ...
