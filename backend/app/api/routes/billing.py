import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.auth import get_current_user
from app.core.config import get_settings
from app.models.user import User
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

stripe.api_key = settings.stripe_secret_key

router = APIRouter(prefix="/billing", tags=["billing"])

TIER_PRICES = {
    "solo": settings.stripe_solo_price_id,
    "pro": settings.stripe_pro_price_id,
}

TIER_LIMITS = {
    "free": 20,
    "solo": 100,
    "pro": 500,
    "school": 300,
}


@router.post("/checkout")
async def create_checkout_session(
    tier: str = "solo",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if tier not in TIER_PRICES:
        raise HTTPException(status_code=400, detail="Invalid tier")

    price_id = TIER_PRICES[tier]
    if not price_id:
        raise HTTPException(status_code=400, detail="Price not configured")

    # Create or retrieve Stripe customer
    if not user.stripe_customer_id:
        customer = stripe.Customer.create(
            email=user.email,
            name=user.full_name,
            metadata={"user_id": user.id},
        )
        user.stripe_customer_id = customer.id
        await db.commit()

    session = stripe.checkout.Session.create(
        customer=user.stripe_customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=f"{settings.cors_origins.split(',')[0]}/settings?billing=success",
        cancel_url=f"{settings.cors_origins.split(',')[0]}/settings?billing=cancel",
        metadata={"user_id": user.id, "tier": tier},
    )

    return {"checkout_url": session.url}


@router.post("/portal")
async def create_portal_session(
    user: User = Depends(get_current_user),
):
    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No billing account found")

    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=f"{settings.cors_origins.split(',')[0]}/settings",
    )

    return {"portal_url": session.url}


@router.get("/usage")
async def get_usage(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func
    from datetime import datetime, timezone, timedelta
    from app.models.school import Paper

    # Count papers this month
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    result = await db.execute(
        select(func.count(Paper.id)).where(
            Paper.teacher_id == user.id,
            Paper.created_at >= month_start,
        )
    )
    papers_this_month = result.scalar() or 0
    limit = TIER_LIMITS.get(user.subscription_tier, 20)

    return {
        "tier": user.subscription_tier,
        "papers_used": papers_this_month,
        "papers_limit": limit,
        "papers_remaining": max(0, limit - papers_this_month),
        "period_start": month_start.isoformat(),
    }


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        user_id = data.get("metadata", {}).get("user_id")
        tier = data.get("metadata", {}).get("tier", "solo")

        if user_id:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user:
                user.subscription_tier = tier
                user.subscription_status = "active"
                await db.commit()
                logger.info(f"User {user_id} upgraded to {tier}")

    elif event_type == "customer.subscription.deleted":
        customer_id = data.get("customer")
        if customer_id:
            result = await db.execute(
                select(User).where(User.stripe_customer_id == customer_id)
            )
            user = result.scalar_one_or_none()
            if user:
                user.subscription_tier = "free"
                user.subscription_status = "canceled"
                await db.commit()
                logger.info(f"User {user.id} subscription canceled")

    elif event_type == "invoice.payment_failed":
        customer_id = data.get("customer")
        if customer_id:
            result = await db.execute(
                select(User).where(User.stripe_customer_id == customer_id)
            )
            user = result.scalar_one_or_none()
            if user:
                user.subscription_status = "past_due"
                await db.commit()
                logger.warning(f"User {user.id} payment failed")

    return {"received": True}
