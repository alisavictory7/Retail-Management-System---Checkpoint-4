"""
Low Stock Alert Service - Checkpoint 4 Feature 2.2

Implements the Publish-Subscribe pattern for low stock alerts.
The service subscribes to inventory update events and tracks products
that fall below the configured threshold.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from sqlalchemy.orm import Session

from src.config import Config
from src.models import Product
from src.observability import increment_counter, record_event


class LowStockAlertService:
    """
    Service that monitors inventory levels and provides low stock alerts.
    
    Architectural Pattern: Publish-Subscribe (Subscriber)
    - Subscribes to inventory update events
    - Maintains list of products below threshold
    - Provides alerts to admin dashboard
    """

    def __init__(
        self,
        db_session: Session,
        threshold: Optional[int] = None,
    ) -> None:
        self.db = db_session
        self.threshold = threshold or Config.LOW_STOCK_THRESHOLD
        self.logger = logging.getLogger(__name__)

    def get_low_stock_products(self) -> List[Dict[str, Any]]:
        """
        Retrieve all products with stock at or below the threshold.
        
        Returns:
            List of dictionaries containing product info and alert severity
        """
        try:
            products = (
                self.db.query(Product)
                .filter(Product.stock <= self.threshold)
                .order_by(Product.stock.asc())
                .all()
            )

            alerts = []
            for product in products:
                severity = self._calculate_severity(product.stock)
                alerts.append({
                    "product_id": product.productID,
                    "product_name": product.name,
                    "current_stock": product.stock,
                    "threshold": self.threshold,
                    "severity": severity,
                    "severity_class": self._get_severity_class(severity),
                })

            self.logger.info(
                "Retrieved %d low stock alerts (threshold: %d)",
                len(alerts),
                self.threshold,
            )
            return alerts

        except Exception as e:
            self.logger.error("Error retrieving low stock products: %s", e)
            return []

    def check_and_alert(self, product_id: int) -> Optional[Dict[str, Any]]:
        """
        Check if a specific product is below threshold and generate alert.
        Called after inventory updates.
        
        Args:
            product_id: The product ID to check
            
        Returns:
            Alert dict if below threshold, None otherwise
        """
        try:
            product = self.db.query(Product).filter_by(productID=product_id).first()
            if not product:
                return None

            if product.stock <= self.threshold:
                severity = self._calculate_severity(product.stock)
                alert = {
                    "product_id": product.productID,
                    "product_name": product.name,
                    "current_stock": product.stock,
                    "threshold": self.threshold,
                    "severity": severity,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                # Record metrics and events
                increment_counter("low_stock_alerts_total", labels={"severity": severity})
                record_event(
                    "low_stock_alert",
                    {
                        "product_id": product_id,
                        "product_name": product.name,
                        "stock": product.stock,
                        "threshold": self.threshold,
                        "severity": severity,
                    },
                )

                self.logger.warning(
                    "Low stock alert: %s (ID: %d) has %d units (threshold: %d)",
                    product.name,
                    product_id,
                    product.stock,
                    self.threshold,
                )
                return alert

            return None

        except Exception as e:
            self.logger.error("Error checking stock for product %d: %s", product_id, e)
            return None

    def get_alert_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all low stock alerts for dashboard display.
        
        Returns:
            Summary dict with counts by severity and total
        """
        alerts = self.get_low_stock_products()
        
        summary = {
            "total_alerts": len(alerts),
            "critical_count": sum(1 for a in alerts if a["severity"] == "critical"),
            "warning_count": sum(1 for a in alerts if a["severity"] == "warning"),
            "out_of_stock_count": sum(1 for a in alerts if a["current_stock"] == 0),
            "threshold": self.threshold,
            "alerts": alerts,
        }

        return summary

    def _calculate_severity(self, stock: int) -> str:
        """
        Calculate alert severity based on stock level.
        
        Args:
            stock: Current stock quantity
            
        Returns:
            Severity level: 'critical', 'warning', or 'low'
        """
        if stock == 0:
            return "critical"
        elif stock <= self.threshold // 2:
            return "warning"
        else:
            return "low"

    def _get_severity_class(self, severity: str) -> str:
        """
        Get CSS class for severity level.
        
        Args:
            severity: Severity level string
            
        Returns:
            TailwindCSS class string
        """
        severity_classes = {
            "critical": "bg-red-100 text-red-800 border-red-300",
            "warning": "bg-yellow-100 text-yellow-800 border-yellow-300",
            "low": "bg-orange-100 text-orange-800 border-orange-300",
        }
        return severity_classes.get(severity, "bg-gray-100 text-gray-800")


def publish_inventory_update_event(
    product_id: int,
    old_stock: int,
    new_stock: int,
    reason: str = "sale",
) -> None:
    """
    Publish an inventory update event for the Pub-Sub pattern.
    Called by inventory-modifying operations.
    
    Args:
        product_id: The product that was updated
        old_stock: Previous stock level
        new_stock: New stock level
        reason: Reason for update (sale, return, adjustment)
    """
    record_event(
        "inventory_updated",
        {
            "product_id": product_id,
            "old_stock": old_stock,
            "new_stock": new_stock,
            "change": new_stock - old_stock,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    increment_counter(
        "inventory_updates_total",
        labels={"reason": reason, "direction": "decrease" if new_stock < old_stock else "increase"},
    )

