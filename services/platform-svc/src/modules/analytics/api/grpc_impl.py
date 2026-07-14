"""
gRPC service implementation for AnalyticsService.
"""

from typing import Any, Callable, Coroutine

import grpc
from grpc import aio

from libs.common.errors import AppError, ErrorCode
from libs.common.logging import get_logger

from libs.proto.analytics.v1 import analytics_pb2 as pb
from libs.proto.analytics.v1 import analytics_pb2_grpc as pb_grpc
from libs.proto.common.v1 import common_pb2 as common_pb

from .services.analytics_service import AnalyticsService

logger = get_logger(__name__)

ServiceFactory = Callable[[], Coroutine[Any, Any, AnalyticsService]]


_ERROR_CODE_TO_GRPC: dict[ErrorCode, grpc.StatusCode] = {
    ErrorCode.UNAUTHENTICATED: grpc.StatusCode.UNAUTHENTICATED,
    ErrorCode.PERMISSION_DENIED: grpc.StatusCode.PERMISSION_DENIED,
    ErrorCode.INVALID_ARGUMENT: grpc.StatusCode.INVALID_ARGUMENT,
    ErrorCode.NOT_FOUND: grpc.StatusCode.NOT_FOUND,
    ErrorCode.INTERNAL_ERROR: grpc.StatusCode.INTERNAL,
    ErrorCode.DATABASE_ERROR: grpc.StatusCode.INTERNAL,
}


def _app_error_to_grpc_context(exc: AppError, context: aio.ServicerContext) -> None:
    grpc_code = _ERROR_CODE_TO_GRPC.get(exc.code, grpc.StatusCode.UNKNOWN)
    context.set_code(grpc_code)
    context.set_details(exc.message)
    error_proto = common_pb.Error(code=exc.full_code, message=exc.message, details=exc.details)
    context.set_trailing_metadata(
        ("x-error-code", str(exc.full_code)),
        ("x-error-bin", error_proto.SerializeToString()),
    )


def _metrics_dict_to_proto(data: dict) -> pb.LiveMetrics:
    return pb.LiveMetrics(
        live_room_id=data["live_room_id"],
        viewer_count=data["viewer_count"],
        peak_viewer_count=data.get("peak_viewer_count", 0),
        danmaku_count=data.get("danmaku_count", 0),
        interaction_count=data.get("interaction_count", 0),
        interaction_rate=float(data.get("interaction_rate", 0)),
        product_clicks=data.get("product_clicks", 0),
        orders=data.get("orders", 0),
        gmv_fen=data.get("gmv_fen", 0),
        duration_seconds=data.get("duration_seconds", 0),
    )


def _rt_metrics_dict_to_proto(data: dict) -> pb.RealTimeMetrics:
    top_products = [
        pb.TopProduct(
            product_id=tp["product_id"],
            title=tp["title"],
            clicks=tp.get("clicks", 0),
            orders=tp.get("orders", 0),
        )
        for tp in data.get("top_products", [])
    ]
    return pb.RealTimeMetrics(
        live_room_id=data["live_room_id"],
        current_viewers=data.get("current_viewers", 0),
        danmaku_per_minute=data.get("danmaku_per_minute", 0),
        orders_last_5min=data.get("orders_last_5min", 0),
        gmv_last_5min_fen=data.get("gmv_last_5min_fen", 0),
        avg_watch_seconds=float(data.get("avg_watch_seconds", 0)),
        top_products=top_products,
    )


def _report_to_proto(report) -> pb.SessionReport:
    summary = report.summary_json or {}
    viewer_timeline = report.viewer_timeline or []
    danmaku_timeline = report.danmaku_timeline or []
    gmv_timeline = report.gmv_timeline or []
    funnel = report.funnel_json or {}

    return pb.SessionReport(
        session_id=report.session_id,
        live_room_id=report.live_room_id,
        summary=_metrics_dict_to_proto(summary) if summary else None,
        viewer_timeline=[
            pb.TimeSeriesPoint(timestamp=pt["timestamp"], value=float(pt["value"]))
            for pt in viewer_timeline
        ],
        danmaku_timeline=[
            pb.TimeSeriesPoint(timestamp=pt["timestamp"], value=float(pt["value"]))
            for pt in danmaku_timeline
        ],
        gmv_timeline=[
            pb.TimeSeriesPoint(timestamp=pt["timestamp"], value=float(pt["value"]))
            for pt in gmv_timeline
        ],
        funnel=pb.FunnelMetrics(
            impressions=funnel.get("impressions", 0),
            product_clicks=funnel.get("product_clicks", 0),
            add_to_cart=funnel.get("add_to_cart", 0),
            orders=funnel.get("orders", 0),
            payments=funnel.get("payments", 0),
        ),
    )


def _perf_dict_to_proto(data: dict) -> pb.ProductPerformance:
    return pb.ProductPerformance(
        product_id=data["product_id"],
        total_appearances=data.get("total_appearances", 0),
        total_clicks=data.get("total_clicks", 0),
        click_rate=float(data.get("click_rate", 0)),
        total_orders=data.get("total_orders", 0),
        total_gmv_fen=data.get("total_gmv_fen", 0),
        avg_attention_seconds=data.get("avg_attention_seconds", 0),
    )


class AnalyticsServiceServicer(pb_grpc.AnalyticsServiceServicer):
    """gRPC servicer for AnalyticsService."""

    def __init__(self, service_factory: ServiceFactory) -> None:
        self._factory = service_factory

    async def _run(self, handler, request, context: aio.ServicerContext) -> Any:
        try:
            svc = await self._factory()
            return await handler(svc, request)
        except AppError as exc:
            _app_error_to_grpc_context(exc, context)
            return None
        except Exception as exc:
            logger.exception("grpc.handler_error", method=context.method)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(exc))
            return None

    async def GetLiveMetrics(
        self, request: pb.GetLiveMetricsRequest, context: aio.ServicerContext
    ) -> pb.LiveMetrics:
        async def handler(svc, req):
            data = await svc.get_live_metrics(live_room_id=req.live_room_id)
            return _metrics_dict_to_proto(data)
        return await self._run(handler, request, context)

    async def GetRealTimeMetrics(
        self, request: pb.GetRealTimeMetricsRequest, context: aio.ServicerContext
    ) -> pb.RealTimeMetrics:
        async def handler(svc, req):
            data = await svc.get_real_time_metrics(live_room_id=req.live_room_id)
            return _rt_metrics_dict_to_proto(data)
        return await self._run(handler, request, context)

    async def GetSessionReport(
        self, request: pb.GetSessionReportRequest, context: aio.ServicerContext
    ) -> pb.SessionReport:
        async def handler(svc, req):
            data = await svc.get_session_report(session_id=req.session_id)
            return _report_to_proto(data)
        return await self._run(handler, request, context)

    async def ListSessionReports(
        self, request: pb.ListSessionReportsRequest, context: aio.ServicerContext
    ) -> pb.ListSessionReportsResponse:
        async def handler(svc, req):
            page = req.pagination.page if req.pagination and req.pagination.page else 1
            page_size = req.pagination.page_size if req.pagination and req.pagination.page_size else 20
            reports, total = await svc.list_session_reports(
                store_id=req.store_id,
                start_date=req.start_date if req.start_date else None,
                end_date=req.end_date if req.end_date else None,
                page=page,
                page_size=page_size,
            )
            total_pages = max(1, (total + page_size - 1) // page_size)
            return pb.ListSessionReportsResponse(
                reports=[_report_to_proto(r) for r in reports],
                page_info=common_pb.PageInfo(
                    page=page, page_size=page_size, total_count=total, total_pages=total_pages
                ),
            )
        return await self._run(handler, request, context)

    async def GetProductPerformance(
        self, request: pb.GetProductPerformanceRequest, context: aio.ServicerContext
    ) -> pb.ProductPerformance:
        async def handler(svc, req):
            data = await svc.get_product_performance(product_id=req.product_id)
            return _perf_dict_to_proto(data)
        return await self._run(handler, request, context)
