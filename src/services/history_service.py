"""
History Service - Checkpoint 4 Feature 2.1

Implements the Layered Service Abstraction (Layers Pattern) for 
Order History Filtering & Search functionality.

This service encapsulates all business logic related to retrieving,
filtering, and preparing historical records, decoupling the API 
controllers from the underlying database schema.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_, and_, func
from sqlalchemy.orm import Session, joinedload

from src.config import Config
from src.models import (
    Sale,
    SaleItem,
    Product,
    ReturnRequest,
    ReturnRequestStatus,
    Refund,
    RefundStatus,
)


class HistoryService:
    """
    Service layer for order and return history operations.
    
    Architectural Pattern: Layers Pattern (Modifiability Tactic)
    - Encapsulates all history-related business logic
    - Decouples controllers from database schema
    - Provides filtering, searching, and pagination
    
    Performance Tactics:
    - Uses database indexing on status and date columns
    - Eager loading to prevent N+1 queries
    """

    # Valid order status values for filtering
    ORDER_STATUSES = ["completed", "pending", "failed", "cart"]
    
    # Derived statuses that require join logic
    DERIVED_STATUSES = ["returned", "refunded"]

    def __init__(
        self,
        db_session: Session,
        page_size: Optional[int] = None,
    ) -> None:
        self.db = db_session
        self.page_size = page_size or Config.ORDER_HISTORY_PAGE_SIZE
        self.logger = logging.getLogger(__name__)

    def get_order_history(
        self,
        user_id: int,
        status_filter: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        keyword: Optional[str] = None,
        page: int = 1,
    ) -> Dict[str, Any]:
        """
        Retrieve filtered and paginated order history for a user.
        
        Args:
            user_id: The user whose orders to retrieve
            status_filter: Filter by order status (completed, pending, returned, refunded)
            start_date: Filter orders on or after this date
            end_date: Filter orders on or before this date
            keyword: Search keyword for product name or order ID
            page: Page number for pagination (1-based)
            
        Returns:
            Dictionary containing:
            - orders: List of order dictionaries
            - total_count: Total number of matching orders
            - page: Current page number
            - page_size: Number of items per page
            - total_pages: Total number of pages
            - filters_applied: Dictionary of active filters
        """
        try:
            # Base query with eager loading
            query = (
                self.db.query(Sale)
                .options(
                    joinedload(Sale.items).joinedload(SaleItem.product),
                    joinedload(Sale.payments),
                    joinedload(Sale.return_requests),
                )
                .filter(Sale.userID == user_id)
                .filter(Sale._status != "cart")  # Exclude active cart
            )

            # Apply status filter
            query = self._apply_status_filter(query, status_filter, user_id)

            # Apply date range filter
            query = self._apply_date_filter(query, start_date, end_date)

            # Apply keyword search
            query = self._apply_keyword_filter(query, keyword)

            # Get total count before pagination
            total_count = query.count()

            # Apply ordering and pagination
            query = query.order_by(Sale._sale_date.desc())
            offset = (page - 1) * self.page_size
            orders = query.offset(offset).limit(self.page_size).all()

            # Calculate pagination info
            total_pages = max(1, (total_count + self.page_size - 1) // self.page_size)

            # Serialize orders
            serialized_orders = [
                self._serialize_order(order) for order in orders
            ]

            return {
                "orders": serialized_orders,
                "total_count": total_count,
                "page": page,
                "page_size": self.page_size,
                "total_pages": total_pages,
                "filters_applied": {
                    "status": status_filter,
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                    "keyword": keyword,
                },
            }

        except Exception as e:
            self.logger.error("Error retrieving order history: %s", e)
            return {
                "orders": [],
                "total_count": 0,
                "page": page,
                "page_size": self.page_size,
                "total_pages": 1,
                "filters_applied": {},
                "error": str(e),
            }

    def get_returns_history(
        self,
        user_id: int,
        status_filter: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        keyword: Optional[str] = None,
        page: int = 1,
    ) -> Dict[str, Any]:
        """
        Retrieve filtered and paginated returns history for a user.
        
        Args:
            user_id: The user whose returns to retrieve
            status_filter: Filter by return status (any ReturnRequestStatus value)
            start_date: Filter returns on or after this date
            end_date: Filter returns on or before this date
            keyword: Search keyword for product name or RMA number
            page: Page number for pagination
            
        Returns:
            Dictionary containing returns data and pagination info
        """
        try:
            query = (
                self.db.query(ReturnRequest)
                .options(
                    joinedload(ReturnRequest.return_items).joinedload("sale_item").joinedload("product"),
                    joinedload(ReturnRequest.sale),
                    joinedload(ReturnRequest.refund),
                )
                .filter(ReturnRequest.customerID == user_id)
            )

            # Apply status filter
            if status_filter:
                try:
                    status_enum = ReturnRequestStatus(status_filter.upper())
                    query = query.filter(ReturnRequest.status == status_enum)
                except ValueError:
                    pass  # Invalid status, skip filter

            # Apply date filter
            if start_date:
                query = query.filter(ReturnRequest.created_at >= start_date)
            if end_date:
                # Include the entire end day
                end_of_day = end_date.replace(hour=23, minute=59, second=59)
                query = query.filter(ReturnRequest.created_at <= end_of_day)

            # Apply keyword search
            if keyword:
                keyword_pattern = f"%{keyword}%"
                query = query.filter(
                    or_(
                        ReturnRequest.rma_number.ilike(keyword_pattern),
                        ReturnRequest.returnRequestID.cast(str).ilike(keyword_pattern),
                    )
                )

            # Get total count
            total_count = query.count()

            # Apply ordering and pagination
            query = query.order_by(ReturnRequest.created_at.desc())
            offset = (page - 1) * self.page_size
            returns = query.offset(offset).limit(self.page_size).all()

            total_pages = max(1, (total_count + self.page_size - 1) // self.page_size)

            serialized_returns = [
                self._serialize_return(ret) for ret in returns
            ]

            return {
                "returns": serialized_returns,
                "total_count": total_count,
                "page": page,
                "page_size": self.page_size,
                "total_pages": total_pages,
                "filters_applied": {
                    "status": status_filter,
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                    "keyword": keyword,
                },
            }

        except Exception as e:
            self.logger.error("Error retrieving returns history: %s", e)
            return {
                "returns": [],
                "total_count": 0,
                "page": page,
                "page_size": self.page_size,
                "total_pages": 1,
                "filters_applied": {},
                "error": str(e),
            }

    def _apply_status_filter(
        self,
        query,
        status_filter: Optional[str],
        user_id: int,
    ):
        """Apply status filter to order query."""
        if not status_filter:
            return query

        status_lower = status_filter.lower()

        if status_lower == "returned":
            # Orders that have at least one return request
            subquery = (
                self.db.query(ReturnRequest.saleID)
                .filter(ReturnRequest.customerID == user_id)
                .filter(
                    ReturnRequest.status.notin_([
                        ReturnRequestStatus.CANCELLED,
                        ReturnRequestStatus.REJECTED,
                    ])
                )
                .subquery()
            )
            query = query.filter(Sale.saleID.in_(subquery))

        elif status_lower == "refunded":
            # Orders that have a completed refund
            subquery = (
                self.db.query(ReturnRequest.saleID)
                .join(Refund, Refund.returnRequestID == ReturnRequest.returnRequestID)
                .filter(ReturnRequest.customerID == user_id)
                .filter(Refund.status == RefundStatus.COMPLETED)
                .subquery()
            )
            query = query.filter(Sale.saleID.in_(subquery))

        elif status_lower in self.ORDER_STATUSES:
            query = query.filter(Sale._status == status_lower)

        return query

    def _apply_date_filter(
        self,
        query,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ):
        """Apply date range filter to query."""
        if start_date:
            query = query.filter(Sale._sale_date >= start_date)
        if end_date:
            # Include the entire end day
            end_of_day = end_date.replace(hour=23, minute=59, second=59)
            query = query.filter(Sale._sale_date <= end_of_day)
        return query

    def _apply_keyword_filter(self, query, keyword: Optional[str]):
        """Apply keyword search filter to query."""
        if not keyword:
            return query

        keyword_pattern = f"%{keyword}%"
        
        # Search in order ID or product names
        # We need to join with SaleItem and Product for product name search
        product_match_subquery = (
            self.db.query(SaleItem.saleID)
            .join(Product, SaleItem.productID == Product.productID)
            .filter(Product.name.ilike(keyword_pattern))
            .subquery()
        )

        # Check if keyword is numeric (order ID search)
        try:
            order_id = int(keyword)
            query = query.filter(
                or_(
                    Sale.saleID == order_id,
                    Sale.saleID.in_(product_match_subquery),
                )
            )
        except ValueError:
            # Not a number, search only product names
            query = query.filter(Sale.saleID.in_(product_match_subquery))

        return query

    def _serialize_order(self, order: Sale) -> Dict[str, Any]:
        """Serialize an order to dictionary format."""
        # Determine derived status
        derived_status = order.status
        has_return = any(
            rr.status not in [ReturnRequestStatus.CANCELLED, ReturnRequestStatus.REJECTED]
            for rr in order.return_requests
        )
        has_refund = any(
            rr.refund and rr.refund.status == RefundStatus.COMPLETED
            for rr in order.return_requests
        )

        if has_refund:
            derived_status = "refunded"
        elif has_return:
            derived_status = "returned"

        return {
            "sale_id": order.saleID,
            "sale_date": order.sale_date.isoformat() if order.sale_date else None,
            "total_amount": float(order.totalAmount) if order.totalAmount else 0.0,
            "status": order.status,
            "derived_status": derived_status,
            "items": [
                {
                    "product_id": item.productID,
                    "product_name": item.product.name if item.product else "Unknown",
                    "quantity": item.quantity,
                    "unit_price": float(item.final_unit_price) if item.final_unit_price else 0.0,
                    "subtotal": float(item.subtotal) if item.subtotal else 0.0,
                }
                for item in order.items
            ],
            "payment_method": self._get_payment_method(order),
            "has_return": has_return,
            "has_refund": has_refund,
        }

    def _serialize_return(self, return_request: ReturnRequest) -> Dict[str, Any]:
        """Serialize a return request to dictionary format."""
        return {
            "return_id": return_request.returnRequestID,
            "sale_id": return_request.saleID,
            "rma_number": return_request.rma_number,
            "status": return_request.status.value if hasattr(return_request.status, 'value') else str(return_request.status),
            "reason": return_request.reason.value if hasattr(return_request.reason, 'value') else str(return_request.reason),
            "created_at": return_request.created_at.isoformat() if return_request.created_at else None,
            "updated_at": return_request.updated_at.isoformat() if return_request.updated_at else None,
            "refund_status": (
                return_request.refund.status.value
                if return_request.refund and hasattr(return_request.refund.status, 'value')
                else None
            ),
            "refund_amount": (
                float(return_request.refund.amount)
                if return_request.refund
                else None
            ),
            "items": [
                {
                    "product_name": (
                        item.sale_item.product.name
                        if item.sale_item and item.sale_item.product
                        else "Unknown"
                    ),
                    "quantity": item.quantity,
                }
                for item in return_request.return_items
            ],
        }

    def _get_payment_method(self, order: Sale) -> Optional[str]:
        """Get the payment method for an order."""
        if order.payments:
            payment = order.payments[0]
            return payment.payment_type or payment.type
        return None

    @staticmethod
    def parse_date(date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse a date string to datetime object.
        
        Args:
            date_str: Date string in YYYY-MM-DD format
            
        Returns:
            datetime object or None if invalid
        """
        if not date_str:
            return None
        try:
            # Parse YYYY-MM-DD format
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

