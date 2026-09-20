"""Background work."""
from celery import shared_task
from core.pricing import price_for


@shared_task
def recalculate(order_id, items, tier):
    return price_for(items, tier)
