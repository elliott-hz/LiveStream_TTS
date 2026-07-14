"""
Billing service — plan management, subscriptions, usage metering, invoices, payments.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common.errors import AppError, ErrorCode, not_found, invalid_arg
from libs.common.logging import get_logger

from models.billing import Plan, Subscription, Invoice, Payment, Usage

logger = get_logger(__name__)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class BillingService:
    """Billing and payment business logic."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Plans ──

    async def list_plans(self) -> list[Plan]:
        """List all active plans."""
        stmt = select(Plan).where(Plan.is_active == True).order_by(Plan.monthly_price_fen)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def subscribe(self, store_id: str, plan_id: str, auto_renew: bool = True) -> Subscription:
        """Subscribe a store to a plan."""
        if not store_id:
            raise invalid_arg("store_id", "must not be empty")
        if not plan_id:
            raise invalid_arg("plan_id", "must not be empty")

        # Verify plan exists
        stmt = select(Plan).where(Plan.plan_id == plan_id, Plan.is_active == True)
        result = await self.db.execute(stmt)
        plan = result.scalars().one_or_none()
        if not plan:
            raise not_found("Plan", plan_id)

        now_ts = int(datetime.utcnow().timestamp())
        expires_at = now_ts + 30 * 86400  # 30 days

        sub = Subscription(
            store_id=store_id,
            plan_id=plan_id,
            status="active",
            started_at=now_ts,
            expires_at=expires_at,
            auto_renew=auto_renew,
        )
        self.db.add(sub)
        await self.db.flush()
        await self.db.refresh(sub)
        logger.info("subscription.created", sub_id=sub.subscription_id, store_id=store_id)
        return sub

    # ── Usage ──

    async def report_usage(
        self,
        store_id: str,
        metric: str,
        value: int,
    ) -> None:
        """Report usage for a store (accumulate into current period)."""
        if not store_id:
            raise invalid_arg("store_id", "must not be empty")

        period = datetime.utcnow().strftime("%Y-%m")

        stmt = select(Usage).where(
            Usage.store_id == store_id,
            Usage.billing_period == period,
        )
        result = await self.db.execute(stmt)
        usage = result.scalars().first()

        if not usage:
            usage = Usage(
                store_id=store_id,
                billing_period=period,
            )
            self.db.add(usage)

        if metric == "streaming_seconds":
            if usage.streaming_minutes_used is None:
                usage.streaming_minutes_used = 0
            usage.streaming_minutes_used += max(0, value // 60)
        elif metric == "api_calls":
            if usage.api_calls_used is None:
                usage.api_calls_used = 0
            usage.api_calls_used += max(0, value)
        elif metric == "llm_tokens":
            if usage.llm_tokens_used is None:
                usage.llm_tokens_used = 0
            usage.llm_tokens_used += max(0, value)

        await self.db.flush()
        logger.info("usage.reported", store_id=store_id, metric=metric, value=value)

    async def get_current_usage(self, store_id: str) -> dict[str, Any]:
        """Get current usage for a store."""
        if not store_id:
            raise invalid_arg("store_id", "must not be empty")

        period = datetime.utcnow().strftime("%Y-%m")

        stmt = select(Usage).where(
            Usage.store_id == store_id,
            Usage.billing_period == period,
        )
        result = await self.db.execute(stmt)
        usage = result.scalars().first()

        if not usage:
            return {
                "store_id": store_id,
                "billing_period": period,
                "streaming_minutes_used": 0,
                "streaming_minutes_limit": 0,
                "products_used": 0,
                "products_limit": 0,
                "api_calls_used": 0,
                "llm_tokens_used": 0,
                "estimated_cost_fen": 0,
            }

        return {
            "store_id": usage.store_id,
            "billing_period": usage.billing_period,
            "streaming_minutes_used": usage.streaming_minutes_used,
            "streaming_minutes_limit": usage.streaming_minutes_limit,
            "products_used": usage.products_used,
            "products_limit": usage.products_limit,
            "api_calls_used": usage.api_calls_used,
            "llm_tokens_used": usage.llm_tokens_used,
            "estimated_cost_fen": usage.estimated_cost_fen,
        }

    # ── Invoices ──

    async def get_invoice(self, invoice_id: str) -> Invoice:
        """Get an invoice by ID."""
        stmt = select(Invoice).where(Invoice.invoice_id == invoice_id)
        result = await self.db.execute(stmt)
        invoice = result.scalars().one_or_none()
        if not invoice:
            raise not_found("Invoice", invoice_id)
        return invoice

    async def list_invoices(
        self,
        store_id: str,
        status: str | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[Invoice], int]:
        """List invoices for a store."""
        if not store_id:
            raise invalid_arg("store_id", "must not be empty")
        page = max(page, 1)
        page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

        conditions = [Invoice.store_id == store_id]
        if status:
            conditions.append(Invoice.status == status)

        count_stmt = select(func.count()).select_from(Invoice).where(*conditions)
        total_result = await self.db.execute(count_stmt)
        total_count: int = total_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = (
            select(Invoice)
            .where(*conditions)
            .order_by(desc(Invoice.issued_at))
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        invoices = list(result.scalars().all())
        return invoices, total_count

    # ── Payments ──

    async def create_payment(self, invoice_id: str, method: str) -> Payment:
        """Create a payment for an invoice."""
        invoice = await self.get_invoice(invoice_id)

        if invoice.status == "paid":
            raise AppError(ErrorCode.DUPLICATE_RESOURCE, "Invoice already paid")

        payment = Payment(
            invoice_id=invoice_id,
            method=method,
            amount_fen=invoice.amount_fen,
            currency=invoice.currency,
            status="pending",
            qr_code_url=f"https://pay.example.com/qr/{invoice_id}",
            payment_url=f"https://pay.example.com/pay/{invoice_id}",
        )
        self.db.add(payment)
        await self.db.flush()
        await self.db.refresh(payment)
        logger.info("payment.created", payment_id=payment.payment_id)
        return payment

    async def payment_callback(self, payment_id: str, gateway_response: str) -> None:
        """Handle payment gateway callback."""
        stmt = select(Payment).where(Payment.payment_id == payment_id)
        result = await self.db.execute(stmt)
        payment = result.scalars().one_or_none()
        if not payment:
            raise not_found("Payment", payment_id)

        # Mock: mark as success
        payment.status = "success"

        # Update invoice
        stmt = select(Invoice).where(Invoice.invoice_id == payment.invoice_id)
        result = await self.db.execute(stmt)
        invoice = result.scalars().one_or_none()
        if invoice:
            invoice.status = "paid"
            invoice.paid_at = int(datetime.utcnow().timestamp())

        await self.db.flush()
        logger.info("payment.completed", payment_id=payment_id)
