from __future__ import annotations

import logging
from typing import Iterable

from sqlalchemy.orm import Session

from src.models import ReturnRequest, ReturnItem


class InventoryService:
    """Encapsulates stock adjustments triggered by returns/refunds."""

    def __init__(self, db_session: Session) -> None:
        self.db = db_session
        self.logger = logging.getLogger(__name__)

    def apply_return_stock(self, return_request: ReturnRequest) -> None:
        """
        Increase on-hand inventory for all items that were approved in the given return.
        """
        if not return_request:
            return

        adjustments = []
        for return_item in return_request.return_items:
            product = getattr(return_item.sale_item, "product", None)
            if not product:
                continue

            approved_quantity = min(return_item.quantity, return_item.sale_item.quantity)
            product.stock = (product.stock or 0) + approved_quantity
            adjustments.append((product.productID, approved_quantity))

        if adjustments:
            self.logger.info(
                "Inventory adjusted for return request %s",
                return_request.returnRequestID,
                extra={"adjustments": adjustments},
            )

    def summarize_return_items(self, items: Iterable[ReturnItem]) -> int:
        """Helper for metrics/logging."""
        return sum(max(0, item.quantity) for item in items)

