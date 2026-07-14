"""
Tests for billing-svc: plans, subscriptions, usage, invoices, payments.
"""

import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
_SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
_LIBS_PROTO = str(Path(_REPO_ROOT) / "libs" / "proto")

for _p in (_REPO_ROOT, _SRC_DIR, _LIBS_PROTO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from libs.db import Base
from models.billing import Plan, Subscription, Invoice, Payment, Usage

import pytest_asyncio  # noqa: E402


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_list_plans(db_session):
    """Test listing plans."""
    from models.billing import Plan
    from services.platform_svc.src.modules.billing.services.billing_service import BillingService

    # Seed plans
    plans_data = [
        ("plan_free", "Free", 0, {"max_live_rooms": 1}),
        ("plan_pro", "Pro", 9900, {"max_live_rooms": 5}),
    ]
    for pid, name, price, quota in plans_data:
        db_session.add(Plan(plan_id=pid, name=name, monthly_price_fen=price, quota_json=quota, is_active=True))
    await db_session.flush()

    svc = BillingService(db=db_session)
    plans = await svc.list_plans()
    assert len(plans) == 2
    assert plans[0].name == "Free"


@pytest.mark.asyncio
async def test_subscribe(db_session):
    """Test subscribing to a plan."""
    from models.billing import Plan
    from services.platform_svc.src.modules.billing.services.billing_service import BillingService

    db_session.add(Plan(plan_id="plan_pro", name="Pro", monthly_price_fen=9900, is_active=True))
    await db_session.flush()

    svc = BillingService(db=db_session)
    sub = await svc.subscribe(store_id="store_001", plan_id="plan_pro", auto_renew=True)
    assert sub.subscription_id is not None
    assert sub.store_id == "store_001"
    assert sub.plan_id == "plan_pro"
    assert sub.status == "active"


@pytest.mark.asyncio
async def test_report_and_get_usage(db_session):
    """Test reporting usage and getting current usage."""
    from services.platform_svc.src.modules.billing.services.billing_service import BillingService

    svc = BillingService(db=db_session)

    # Report streaming usage
    await svc.report_usage(store_id="store_001", metric="streaming_seconds", value=600)

    usage = await svc.get_current_usage(store_id="store_001")
    assert usage["store_id"] == "store_001"
    assert usage["streaming_minutes_used"] == 10  # 600 / 60
    assert usage["billing_period"] is not None


@pytest.mark.asyncio
async def test_create_and_get_invoice(db_session):
    """Test creating and fetching an invoice."""
    from models.billing import Invoice
    from services.platform_svc.src.modules.billing.services.billing_service import BillingService

    inv = Invoice(invoice_id="inv_001", store_id="store_001", billing_period="2026-07", amount_fen=9900, issued_at=1000)
    db_session.add(inv)
    await db_session.flush()

    svc = BillingService(db=db_session)
    fetched = await svc.get_invoice(invoice_id="inv_001")
    assert fetched.store_id == "store_001"
    assert fetched.amount_fen == 9900


@pytest.mark.asyncio
async def test_create_payment(db_session):
    """Test creating a payment for an invoice."""
    from models.billing import Invoice
    from services.platform_svc.src.modules.billing.services.billing_service import BillingService

    inv = Invoice(invoice_id="inv_001", store_id="store_001", billing_period="2026-07", amount_fen=9900, issued_at=1000)
    db_session.add(inv)
    await db_session.flush()

    svc = BillingService(db=db_session)
    payment = await svc.create_payment(invoice_id="inv_001", method="wechat")
    assert payment.payment_id is not None
    assert payment.method == "wechat"
    assert payment.status == "pending"


@pytest.mark.asyncio
async def test_payment_callback(db_session):
    """Test payment callback marks invoice as paid."""
    from models.billing import Invoice, Payment
    from services.platform_svc.src.modules.billing.services.billing_service import BillingService

    inv = Invoice(invoice_id="inv_001", store_id="store_001", billing_period="2026-07", amount_fen=9900, issued_at=1000)
    db_session.add(inv)
    await db_session.flush()

    pay = Payment(payment_id="pay_001", invoice_id="inv_001", method="wechat", amount_fen=9900)
    db_session.add(pay)
    await db_session.flush()

    svc = BillingService(db=db_session)
    await svc.payment_callback(payment_id="pay_001", gateway_response="success")

    updated_inv = await svc.get_invoice(invoice_id="inv_001")
    assert updated_inv.status == "paid"
