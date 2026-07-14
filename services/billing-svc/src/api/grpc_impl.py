"""
gRPC service implementation for BillingService.
"""

from typing import Any, Callable, Coroutine

import grpc
from grpc import aio

from libs.common.errors import AppError, ErrorCode
from libs.common.logging import get_logger

from billing.v1 import billing_pb2 as pb
from billing.v1 import billing_pb2_grpc as pb_grpc
from common.v1 import common_pb2 as common_pb

from models.billing import Plan, Subscription, Invoice, Payment
from services.billing_service import BillingService

logger = get_logger(__name__)

ServiceFactory = Callable[[], Coroutine[Any, Any, BillingService]]


_ERROR_CODE_TO_GRPC: dict[ErrorCode, grpc.StatusCode] = {
    ErrorCode.UNAUTHENTICATED: grpc.StatusCode.UNAUTHENTICATED,
    ErrorCode.INVALID_ARGUMENT: grpc.StatusCode.INVALID_ARGUMENT,
    ErrorCode.NOT_FOUND: grpc.StatusCode.NOT_FOUND,
    ErrorCode.DUPLICATE_RESOURCE: grpc.StatusCode.ALREADY_EXISTS,
    ErrorCode.INSUFFICIENT_BALANCE: grpc.StatusCode.FAILED_PRECONDITION,
    ErrorCode.QUOTA_EXCEEDED: grpc.StatusCode.RESOURCE_EXHAUSTED,
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


def _plan_to_proto(p: Plan) -> pb.Plan:
    quota = p.quota_json or {}
    return pb.Plan(
        plan_id=p.plan_id,
        name=p.name,
        description=p.description,
        monthly_price=common_pb.Money(amount=p.monthly_price_fen, currency=p.currency),
        quota=pb.PlanQuota(
            max_live_rooms=quota.get("max_live_rooms", 0),
            max_concurrent_streams=quota.get("max_concurrent_streams", 0),
            max_products=quota.get("max_products", 0),
            max_avatars=quota.get("max_avatars", 0),
            max_voices=quota.get("max_voices", 0),
            streaming_hours_per_month=quota.get("streaming_hours_per_month", 0),
            includes_api_access=quota.get("includes_api_access", False),
        ),
        is_active=p.is_active,
    )


_MAP_SUB_STATUS = {
    "active": pb.SubscriptionStatus.SUBSCRIPTION_STATUS_ACTIVE,
    "expired": pb.SubscriptionStatus.SUBSCRIPTION_STATUS_EXPIRED,
    "cancelled": pb.SubscriptionStatus.SUBSCRIPTION_STATUS_CANCELLED,
}
_REV_SUB_STATUS = {v: k for k, v in _MAP_SUB_STATUS.items()}


def _sub_status_to_proto(s: str) -> int:
    return _MAP_SUB_STATUS.get(s, pb.SubscriptionStatus.SUBSCRIPTION_STATUS_UNSPECIFIED)


def _sub_to_proto(s: Subscription) -> pb.Subscription:
    return pb.Subscription(
        subscription_id=s.subscription_id,
        store_id=s.store_id,
        plan_id=s.plan_id,
        status=_sub_status_to_proto(s.status),
        started_at=s.started_at,
        expires_at=s.expires_at,
        auto_renew=s.auto_renew,
    )


_MAP_INV_STATUS = {
    "pending": pb.InvoiceStatus.INVOICE_STATUS_PENDING,
    "paid": pb.InvoiceStatus.INVOICE_STATUS_PAID,
    "overdue": pb.InvoiceStatus.INVOICE_STATUS_OVERDUE,
}
_REV_INV_STATUS = {v: k for k, v in _MAP_INV_STATUS.items()}


def _inv_status_to_proto(s: str) -> int:
    return _MAP_INV_STATUS.get(s, pb.InvoiceStatus.INVOICE_STATUS_UNSPECIFIED)


def _inv_to_proto(inv: Invoice) -> pb.Invoice:
    return pb.Invoice(
        invoice_id=inv.invoice_id,
        store_id=inv.store_id,
        billing_period=inv.billing_period,
        amount=common_pb.Money(amount=inv.amount_fen, currency=inv.currency),
        status=_inv_status_to_proto(inv.status),
        pdf_url=inv.pdf_url,
        issued_at=inv.issued_at,
        paid_at=inv.paid_at,
    )


_MAP_PAY_STATUS = {
    "pending": pb.PaymentStatus.PAYMENT_STATUS_PENDING,
    "success": pb.PaymentStatus.PAYMENT_STATUS_SUCCESS,
    "failed": pb.PaymentStatus.PAYMENT_STATUS_FAILED,
}
_REV_PAY_STATUS = {v: k for k, v in _MAP_PAY_STATUS.items()}


def _pay_status_to_proto(s: str) -> int:
    return _MAP_PAY_STATUS.get(s, pb.PaymentStatus.PAYMENT_STATUS_UNSPECIFIED)


_MAP_PAY_METHOD = {
    "wechat": pb.PaymentMethod.PAYMENT_METHOD_WECHAT,
    "alipay": pb.PaymentMethod.PAYMENT_METHOD_ALIPAY,
}
_REV_PAY_METHOD = {v: k for k, v in _MAP_PAY_METHOD.items()}


def _pay_method_from_proto(m: int) -> str:
    return _REV_PAY_METHOD.get(m, "wechat")


def _pay_to_proto(p: Payment) -> pb.Payment:
    return pb.Payment(
        payment_id=p.payment_id,
        invoice_id=p.invoice_id,
        method=_MAP_PAY_METHOD.get(p.method, pb.PaymentMethod.PAYMENT_METHOD_UNSPECIFIED),
        amount=common_pb.Money(amount=p.amount_fen, currency=p.currency),
        status=_pay_status_to_proto(p.status),
        qr_code_url=p.qr_code_url,
        payment_url=p.payment_url,
    )


def _usage_to_proto(data: dict) -> pb.Usage:
    return pb.Usage(
        store_id=data["store_id"],
        billing_period=data["billing_period"],
        streaming_minutes_used=data.get("streaming_minutes_used", 0),
        streaming_minutes_limit=data.get("streaming_minutes_limit", 0),
        products_used=data.get("products_used", 0),
        products_limit=data.get("products_limit", 0),
        api_calls_used=data.get("api_calls_used", 0),
        llm_tokens_used=data.get("llm_tokens_used", 0),
        estimated_cost=common_pb.Money(amount=data.get("estimated_cost_fen", 0), currency="CNY"),
    )


class BillingServiceServicer(pb_grpc.BillingServiceServicer):
    """gRPC servicer for BillingService."""

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

    async def ListPlans(
        self, request: pb.ListPlansRequest, context: aio.ServicerContext
    ) -> pb.ListPlansResponse:
        async def handler(svc, req):
            plans = await svc.list_plans()
            return pb.ListPlansResponse(plans=[_plan_to_proto(p) for p in plans])
        return await self._run(handler, request, context)

    async def Subscribe(
        self, request: pb.SubscribeRequest, context: aio.ServicerContext
    ) -> pb.Subscription:
        async def handler(svc, req):
            sub = await svc.subscribe(
                store_id=req.store_id,
                plan_id=req.plan_id,
                auto_renew=req.auto_renew,
            )
            return _sub_to_proto(sub)
        return await self._run(handler, request, context)

    async def ReportUsage(
        self, request: pb.ReportUsageRequest, context: aio.ServicerContext
    ) -> common_pb.Error:
        async def handler(svc, req):
            metric_map = {1: "streaming_seconds", 2: "api_calls", 3: "llm_tokens"}
            metric = metric_map.get(req.metric, "streaming_seconds")
            await svc.report_usage(
                store_id=req.store_id,
                metric=metric,
                value=req.value,
            )
            return common_pb.Error(code=0, message="ok")
        return await self._run(handler, request, context)

    async def GetCurrentUsage(
        self, request: pb.GetCurrentUsageRequest, context: aio.ServicerContext
    ) -> pb.Usage:
        async def handler(svc, req):
            data = await svc.get_current_usage(store_id=req.store_id)
            return _usage_to_proto(data)
        return await self._run(handler, request, context)

    async def GetInvoice(
        self, request: pb.GetInvoiceRequest, context: aio.ServicerContext
    ) -> pb.Invoice:
        async def handler(svc, req):
            inv = await svc.get_invoice(invoice_id=req.invoice_id)
            return _inv_to_proto(inv)
        return await self._run(handler, request, context)

    async def ListInvoices(
        self, request: pb.ListInvoicesRequest, context: aio.ServicerContext
    ) -> pb.ListInvoicesResponse:
        async def handler(svc, req):
            status = _REV_INV_STATUS.get(req.status) if req.HasField("status") else None
            page = req.pagination.page if req.pagination and req.pagination.page else 1
            page_size = req.pagination.page_size if req.pagination and req.pagination.page_size else 20
            invoices, total = await svc.list_invoices(
                store_id=req.store_id,
                status=status,
                page=page,
                page_size=page_size,
            )
            total_pages = max(1, (total + page_size - 1) // page_size)
            return pb.ListInvoicesResponse(
                invoices=[_inv_to_proto(i) for i in invoices],
                page_info=common_pb.PageInfo(
                    page=page, page_size=page_size, total_count=total, total_pages=total_pages
                ),
            )
        return await self._run(handler, request, context)

    async def CreatePayment(
        self, request: pb.CreatePaymentRequest, context: aio.ServicerContext
    ) -> pb.Payment:
        async def handler(svc, req):
            method = _REV_PAY_METHOD.get(req.method, "wechat")
            payment = await svc.create_payment(
                invoice_id=req.invoice_id,
                method=method,
            )
            return _pay_to_proto(payment)
        return await self._run(handler, request, context)

    async def PaymentCallback(
        self, request: pb.PaymentCallbackRequest, context: aio.ServicerContext
    ) -> common_pb.Error:
        async def handler(svc, req):
            await svc.payment_callback(
                payment_id=req.payment_id,
                gateway_response=req.gateway_response,
            )
            return common_pb.Error(code=0, message="ok")
        return await self._run(handler, request, context)
