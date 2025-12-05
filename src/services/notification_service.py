"""
Notification Service - Checkpoint 4 Feature 2.3

Implements the Publish-Subscribe pattern for RMA status change notifications.
Provides a lightweight in-memory notification system for the UI.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from threading import Lock

from src.observability import increment_counter, record_event


@dataclass
class Notification:
    """Represents a single notification."""
    id: str
    user_id: int
    notification_type: str
    title: str
    message: str
    reference_id: Optional[int] = None
    reference_type: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    read: bool = False
    read_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert notification to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.notification_type,
            "title": self.title,
            "message": self.message,
            "reference_id": self.reference_id,
            "reference_type": self.reference_type,
            "created_at": self.created_at.isoformat(),
            "read": self.read,
            "read_at": self.read_at.isoformat() if self.read_at else None,
        }


class NotificationService:
    """
    In-memory notification service for RMA status changes.
    
    Architectural Pattern: Publish-Subscribe (Subscriber for RMA events)
    - Subscribes to RMA status change events
    - Stores notifications per user
    - Provides unread count and notification list for UI
    
    Note: In a production system, this would use a database or Redis.
    For CP4 lightweight requirements, in-memory storage is sufficient.
    """

    _instance: Optional["NotificationService"] = None
    _lock: Lock = Lock()

    def __new__(cls) -> "NotificationService":
        """Singleton pattern to ensure consistent notification state."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._notifications: Dict[int, List[Notification]] = defaultdict(list)
        self._notification_counter: int = 0
        self._max_notifications_per_user: int = 50
        self.logger = logging.getLogger(__name__)
        self._initialized = True

    def add_notification(
        self,
        user_id: int,
        notification_type: str,
        title: str,
        message: str,
        reference_id: Optional[int] = None,
        reference_type: Optional[str] = None,
    ) -> Notification:
        """
        Add a new notification for a user.
        
        Args:
            user_id: The user to notify
            notification_type: Type of notification (rma_status, low_stock, etc.)
            title: Short title for the notification
            message: Full notification message
            reference_id: Optional ID of related entity (e.g., return request ID)
            reference_type: Type of reference (e.g., 'return_request')
            
        Returns:
            The created Notification object
        """
        with self._lock:
            self._notification_counter += 1
            notification_id = f"notif_{self._notification_counter}_{int(datetime.now().timestamp())}"

            notification = Notification(
                id=notification_id,
                user_id=user_id,
                notification_type=notification_type,
                title=title,
                message=message,
                reference_id=reference_id,
                reference_type=reference_type,
            )

            # Add to user's notifications (most recent first)
            self._notifications[user_id].insert(0, notification)

            # Trim old notifications if exceeding limit
            if len(self._notifications[user_id]) > self._max_notifications_per_user:
                self._notifications[user_id] = self._notifications[user_id][:self._max_notifications_per_user]

            # Record metrics
            increment_counter(
                "notifications_created_total",
                labels={"type": notification_type},
            )

            self.logger.info(
                "Notification created for user %d: %s",
                user_id,
                title,
            )

            return notification

    def get_notifications(
        self,
        user_id: int,
        unread_only: bool = False,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Get notifications for a user.
        
        Args:
            user_id: The user ID
            unread_only: If True, only return unread notifications
            limit: Maximum number of notifications to return
            
        Returns:
            List of notification dictionaries
        """
        notifications = self._notifications.get(user_id, [])

        if unread_only:
            notifications = [n for n in notifications if not n.read]

        return [n.to_dict() for n in notifications[:limit]]

    def get_unread_count(self, user_id: int) -> int:
        """
        Get count of unread notifications for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            Number of unread notifications
        """
        notifications = self._notifications.get(user_id, [])
        return sum(1 for n in notifications if not n.read)

    def mark_as_read(self, user_id: int, notification_id: str) -> bool:
        """
        Mark a specific notification as read.
        
        Args:
            user_id: The user ID
            notification_id: The notification ID to mark
            
        Returns:
            True if notification was found and marked, False otherwise
        """
        notifications = self._notifications.get(user_id, [])
        for notification in notifications:
            if notification.id == notification_id:
                notification.read = True
                notification.read_at = datetime.now(timezone.utc)
                return True
        return False

    def mark_all_as_read(self, user_id: int) -> int:
        """
        Mark all notifications for a user as read.
        
        Args:
            user_id: The user ID
            
        Returns:
            Number of notifications marked as read
        """
        notifications = self._notifications.get(user_id, [])
        count = 0
        now = datetime.now(timezone.utc)
        for notification in notifications:
            if not notification.read:
                notification.read = True
                notification.read_at = now
                count += 1
        return count

    def clear_notifications(self, user_id: int) -> None:
        """Clear all notifications for a user."""
        self._notifications[user_id] = []


# -----------------------------------------------------------------------------
# RMA Status Change Event Handlers
# -----------------------------------------------------------------------------

# Human-readable status labels
RMA_STATUS_LABELS = {
    "PENDING_CUSTOMER_INFO": "Pending Customer Info",
    "PENDING_AUTHORIZATION": "Submitted",
    "AUTHORIZED": "Authorized",
    "IN_TRANSIT": "In Transit",
    "RECEIVED": "Received",
    "UNDER_INSPECTION": "Under Inspection",
    "APPROVED": "Approved",
    "REJECTED": "Rejected",
    "REFUNDED": "Refunded",
    "CANCELLED": "Cancelled",
}


def publish_rma_status_change(
    return_request_id: int,
    customer_id: int,
    old_status: str,
    new_status: str,
    rma_number: Optional[str] = None,
) -> None:
    """
    Publish an RMA status change event and create user notification.
    
    This function implements the Publisher side of the Pub-Sub pattern.
    Called by ReturnsService when status transitions occur.
    
    Args:
        return_request_id: The return request ID
        customer_id: The customer who owns the return
        old_status: Previous status
        new_status: New status
        rma_number: Optional RMA number for display
    """
    # Get human-readable status labels
    old_label = RMA_STATUS_LABELS.get(old_status, old_status)
    new_label = RMA_STATUS_LABELS.get(new_status, new_status)
    
    rma_display = rma_number or f"#{return_request_id}"

    # Record the event for observability
    record_event(
        "rma_status_changed",
        {
            "return_request_id": return_request_id,
            "customer_id": customer_id,
            "old_status": old_status,
            "new_status": new_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

    increment_counter(
        "rma_status_transitions_total",
        labels={"from_status": old_status, "to_status": new_status},
    )

    # Create user notification
    notification_service = NotificationService()
    notification_service.add_notification(
        user_id=customer_id,
        notification_type="rma_status",
        title=f"Return {rma_display} Updated",
        message=f"Your return request status changed from {old_label} to {new_label}.",
        reference_id=return_request_id,
        reference_type="return_request",
    )

