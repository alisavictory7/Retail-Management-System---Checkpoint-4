from __future__ import annotations

import logging
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from src.models import ReturnRequest, ReturnItem, Product
from src.services.low_stock_alert_service import publish_inventory_update_event


class InventoryService:
    """
    Encapsulates stock adjustments triggered by returns/refunds and sales.
    
    Checkpoint 4: Implements Publish-Subscribe pattern for inventory updates.
    Publishes inventory_updated events that can be consumed by alert services.
    """

    def __init__(self, db_session: Session) -> None:
        self.db = db_session
        self.logger = logging.getLogger(__name__)

    def apply_return_stock(self, return_request: ReturnRequest) -> None:
        """
        Increase on-hand inventory for all items that were approved in the given return.
        Publishes inventory update events for low stock alert monitoring.
        """
        if not return_request:
            return

        adjustments = []
        for return_item in return_request.return_items:
            product = getattr(return_item.sale_item, "product", None)
            if not product:
                continue

            old_stock = product.stock or 0
            approved_quantity = min(return_item.quantity, return_item.sale_item.quantity)
            new_stock = old_stock + approved_quantity
            product.stock = new_stock
            adjustments.append((product.productID, approved_quantity))

            # Publish inventory update event (Pub-Sub pattern)
            publish_inventory_update_event(
                product_id=product.productID,
                old_stock=old_stock,
                new_stock=new_stock,
                reason="return",
            )

        if adjustments:
            self.logger.info(
                "Inventory adjusted for return request %s",
                return_request.returnRequestID,
                extra={"adjustments": adjustments},
            )

    def decrease_stock(
        self,
        product_id: int,
        quantity: int,
        reason: str = "sale",
    ) -> Optional[int]:
        """
        Decrease stock for a product and publish update event.
        
        Args:
            product_id: The product to update
            quantity: Amount to decrease
            reason: Reason for decrease (sale, adjustment, etc.)
            
        Returns:
            New stock level or None if product not found
        """
        product = self.db.query(Product).filter_by(productID=product_id).first()
        if not product:
            return None

        old_stock = product.stock or 0
        new_stock = max(0, old_stock - quantity)
        product.stock = new_stock

        # Publish inventory update event
        publish_inventory_update_event(
            product_id=product_id,
            old_stock=old_stock,
            new_stock=new_stock,
            reason=reason,
        )

        self.logger.info(
            "Stock decreased for product %d: %d -> %d (%s)",
            product_id,
            old_stock,
            new_stock,
            reason,
        )

        return new_stock

    def summarize_return_items(self, items: Iterable[ReturnItem]) -> int:
        """Helper for metrics/logging."""
        return sum(max(0, item.quantity) for item in items)

