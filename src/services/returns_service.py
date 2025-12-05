from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.config import Config
from src.models import (
    ReturnRequest,
    ReturnRequestStatus,
    ReturnReason,
    ReturnItem,
    ReturnShipment,
    Inspection,
    InspectionResult,
    RefundMethod,
    Sale,
    SaleItem,
    Payment,
    ReturnPhoto,
)
from src.services.inventory_service import InventoryService
from src.services.refund_service import RefundService
from src.services.notification_service import publish_rma_status_change
from src.observability import increment_counter, record_event


class ReturnsService:
    """Domain service that manages the full RMA lifecycle."""

    def __init__(
        self,
        db_session: Session,
        config: type[Config] = Config,
        refund_service: Optional[RefundService] = None,
        inventory_service: Optional[InventoryService] = None,
    ) -> None:
        self.db = db_session
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.inventory_service = inventory_service or InventoryService(db_session)
        self.refund_service = refund_service or RefundService(
            db_session,
            inventory_service=self.inventory_service,
            config=config,
        )

    # ------------------------------------------------------------------
    # Customer flows
    # ------------------------------------------------------------------
    def create_return_request(
        self,
        sale_id: int,
        customer_id: int,
        items: Iterable[Dict[str, int]],
        reason: ReturnReason | str,
        details: Optional[str] = None,
        photos: Optional[List[str]] = None,
    ) -> Tuple[bool, str, Optional[ReturnRequest]]:
        if not self.config.FEATURE_RETURNS_ENABLED:
            return False, "Returns feature is disabled", None

        sale = self._get_completed_sale(sale_id, customer_id)
        if not sale:
            return False, "Sale not found or not eligible for return", None

        if not self._is_within_policy_window(sale):
            return False, "Return window has expired for this sale", None

        sanitized_photos = self._sanitize_photos(photos)
        if not sanitized_photos and self.config.RETURNS_REQUIRE_PHOTOS:
            return False, "Photos are required for this type of return", None

        reason_enum = (
            reason if isinstance(reason, ReturnReason) else ReturnReason(reason)
        )

        return_items_result = self._build_return_items(sale, items)
        if not return_items_result[0]:
            return False, return_items_result[1], None
        return_items = return_items_result[2]
        if not return_items:
            return False, "No sale items remain eligible for return", None

        request = ReturnRequest(
            saleID=sale.saleID,
            customerID=customer_id,
            status=ReturnRequestStatus.PENDING_AUTHORIZATION,
            reason=reason_enum,
            details=details,
            photos_url=sanitized_photos[0] if sanitized_photos else None,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(request)
        self.db.flush()

        for return_item in return_items:
            return_item.returnRequestID = request.returnRequestID
            self.db.add(return_item)

        for photo_path in sanitized_photos:
            self.db.add(
                ReturnPhoto(
                    returnRequestID=request.returnRequestID,
                    file_path=photo_path,
                )
            )

        self.db.commit()
        increment_counter("returns_created_total")
        record_event(
            "return_request_created",
            {"return_request_id": request.returnRequestID, "sale_id": sale.saleID, "customer_id": customer_id},
        )
        
        # Publish RMA status change notification (CP4 Feature 2.3)
        publish_rma_status_change(
            return_request_id=request.returnRequestID,
            customer_id=customer_id,
            old_status="",
            new_status=ReturnRequestStatus.PENDING_AUTHORIZATION.value,
            rma_number=request.rma_number,
        )
        
        self.logger.info(
            "Return request %s created",
            request.returnRequestID,
            extra={"sale_id": sale.saleID, "customer_id": customer_id},
        )
        return True, "Return request submitted", request

    def _sanitize_photos(self, photos: Optional[List[str]]) -> List[str]:
        if not photos:
            return []
        max_photos = getattr(self.config, "RETURNS_MAX_PHOTOS", 20)
        cleaned: List[str] = []
        for candidate in photos:
            if not isinstance(candidate, str):
                continue
            trimmed = candidate.strip()
            if not trimmed:
                continue
            cleaned.append(trimmed)
            if len(cleaned) >= max_photos:
                break
        return cleaned

    # ------------------------------------------------------------------
    # Admin / internal flows
    # ------------------------------------------------------------------
    def authorize_return(
        self,
        return_request_id: int,
        approve: bool,
        decision_notes: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[ReturnRequest]]:
        request = self._get_return_request(return_request_id)
        if not request:
            return False, "Return request not found", None

        if request.status not in {
            ReturnRequestStatus.PENDING_AUTHORIZATION,
            ReturnRequestStatus.PENDING_CUSTOMER_INFO,
        }:
            return False, f"Cannot authorize return in status {request.status}", None

        old_status = request.status
        if approve:
            request.transition_to(ReturnRequestStatus.AUTHORIZED)
            if not request.rma_number:
                request.rma_number = f"RMA-{datetime.now().strftime('%Y%m%d')}-{request.returnRequestID:05d}"
            message = "Return authorized"
        else:
            request.transition_to(ReturnRequestStatus.REJECTED)
            message = "Return rejected"

        request.decision_notes = decision_notes
        self.db.commit()
        increment_counter("return_status_transition_total", labels={"status": request.status})
        
        # Publish RMA status change notification (CP4 Feature 2.3)
        publish_rma_status_change(
            return_request_id=request.returnRequestID,
            customer_id=request.customerID,
            old_status=old_status.value if hasattr(old_status, 'value') else str(old_status),
            new_status=request.status.value if hasattr(request.status, 'value') else str(request.status),
            rma_number=request.rma_number,
        )
        
        return True, message, request

    def record_shipment(
        self,
        return_request_id: int,
        carrier: str,
        tracking_number: str,
        shipped_at: Optional[datetime] = None,
    ) -> Tuple[bool, str, Optional[ReturnShipment]]:
        request = self._require_status(return_request_id, ReturnRequestStatus.AUTHORIZED)
        if not request:
            return False, "Return request not in AUTHORIZED state", None

        shipment = request.shipment
        if not shipment:
            shipment = ReturnShipment(returnRequestID=request.returnRequestID)
            self.db.add(shipment)

        old_status = request.status
        shipment.carrier = carrier
        shipment.tracking_number = tracking_number
        shipment.shipped_at = shipped_at or datetime.now(timezone.utc)
        request.transition_to(ReturnRequestStatus.IN_TRANSIT)

        self.db.commit()
        
        # Publish RMA status change notification (CP4 Feature 2.3)
        publish_rma_status_change(
            return_request_id=request.returnRequestID,
            customer_id=request.customerID,
            old_status=old_status.value if hasattr(old_status, 'value') else str(old_status),
            new_status=request.status.value if hasattr(request.status, 'value') else str(request.status),
            rma_number=request.rma_number,
        )
        
        return True, "Return shipment recorded", shipment

    def mark_received(
        self,
        return_request_id: int,
        received_at: Optional[datetime] = None,
    ) -> Tuple[bool, str, Optional[ReturnShipment]]:
        request = self._require_status(return_request_id, ReturnRequestStatus.IN_TRANSIT)
        if not request:
            return False, "Return request not in transit", None

        shipment = request.shipment
        if not shipment:
            return False, "No shipment record found for this return", None

        old_status = request.status
        shipment.received_at = received_at or datetime.now(timezone.utc)
        request.transition_to(ReturnRequestStatus.RECEIVED)
        self.db.commit()
        increment_counter("return_status_transition_total", labels={"status": request.status})
        
        # Publish RMA status change notification (CP4 Feature 2.3)
        publish_rma_status_change(
            return_request_id=request.returnRequestID,
            customer_id=request.customerID,
            old_status=old_status.value if hasattr(old_status, 'value') else str(old_status),
            new_status=request.status.value if hasattr(request.status, 'value') else str(request.status),
            rma_number=request.rma_number,
        )
        
        return True, "Return marked as received", shipment

    def record_inspection(
        self,
        return_request_id: int,
        inspected_by: str,
        result: InspectionResult | str,
        notes: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[Inspection]]:
        request = self._require_status(
            return_request_id,
            ReturnRequestStatus.RECEIVED,
            ReturnRequestStatus.UNDER_INSPECTION,
        )
        if not request:
            return False, "Return request not ready for inspection", None

        if request.status == ReturnRequestStatus.RECEIVED:
            request.transition_to(ReturnRequestStatus.UNDER_INSPECTION)

        result_enum = result if isinstance(result, InspectionResult) else InspectionResult(result)

        inspection = request.inspection
        if not inspection:
            inspection = Inspection(returnRequestID=request.returnRequestID)
            self.db.add(inspection)

        inspection.inspected_by = inspected_by
        inspection.inspected_at = datetime.now(timezone.utc)
        inspection.result = result_enum
        inspection.notes = notes

        old_status = request.status
        if result_enum in {InspectionResult.APPROVED, InspectionResult.PARTIALLY_APPROVED}:
            request.transition_to(ReturnRequestStatus.APPROVED)
        elif result_enum == InspectionResult.REJECTED:
            request.transition_to(ReturnRequestStatus.REJECTED)

        self.db.commit()
        increment_counter("return_status_transition_total", labels={"status": request.status})
        
        # Publish RMA status change notification (CP4 Feature 2.3)
        if request.status != old_status:
            publish_rma_status_change(
                return_request_id=request.returnRequestID,
                customer_id=request.customerID,
                old_status=old_status.value if hasattr(old_status, 'value') else str(old_status),
                new_status=request.status.value if hasattr(request.status, 'value') else str(request.status),
                rma_number=request.rma_number,
            )
        
        return True, "Inspection recorded", inspection

    def initiate_refund(
        self,
        return_request_id: int,
        method: Optional[RefundMethod | str] = None,
    ) -> Tuple[bool, str]:
        success, message, _ = self.refund_service.process_refund(return_request_id, method=method)
        return success, message

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
    def _get_completed_sale(self, sale_id: int, customer_id: int) -> Optional[Sale]:
        return (
            self.db.query(Sale)
            .filter(
                Sale.saleID == sale_id,
                Sale.userID == customer_id,
                Sale._status == 'completed',
                Sale.payments.any(Payment._status == 'completed'),
                Sale.items.any(SaleItem.quantity > 0),
            )
            .first()
        )

    def _is_within_policy_window(self, sale: Sale) -> bool:
        if not sale.sale_date:
            return False
        sale_dt = sale.sale_date
        if sale_dt.tzinfo is None:
            sale_dt = sale_dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - sale_dt
        return delta.days <= self.config.RETURN_WINDOW_DAYS

    def _build_return_items(
        self,
        sale: Sale,
        items: Iterable[Dict[str, int]],
    ) -> Tuple[bool, str, List[ReturnItem]]:
        if not items:
            return False, "At least one item must be selected for return", []

        prepared_items: List[ReturnItem] = []
        for payload in items:
            sale_item_id = payload.get("sale_item_id")
            quantity = payload.get("quantity", 0)

            if not sale_item_id or quantity <= 0:
                return False, "Each item must include sale_item_id and positive quantity", []

            sale_item = (
                self.db.query(SaleItem)
                .filter_by(saleItemID=sale_item_id, saleID=sale.saleID)
                .first()
            )
            if not sale_item:
                return False, f"Sale item {sale_item_id} not found for this sale", []

            if quantity > self.config.MAX_RETURN_ITEM_QUANTITY:
                return False, f"Quantity exceeds policy max ({self.config.MAX_RETURN_ITEM_QUANTITY})", []

            if quantity > sale_item.quantity:
                return False, "Cannot return more units than were purchased", []

            reserved_quantity = sum(
                ri.quantity
                for ri in sale_item.return_items
                if ri.return_request
                and ri.return_request.status not in {
                    ReturnRequestStatus.REJECTED,
                    ReturnRequestStatus.CANCELLED,
                }
            )
            remaining_quantity = max(0, sale_item.quantity - reserved_quantity)
            if remaining_quantity <= 0:
                return False, "All units for this item already have return requests.", []
            if quantity > remaining_quantity:
                return False, f"Only {remaining_quantity} unit(s) remain eligible for return.", []

            prepared_items.append(
                ReturnItem(
                    saleItemID=sale_item.saleItemID,
                    quantity=quantity,
                )
            )

        return True, "Items validated", prepared_items

    def _get_return_request(self, request_id: int) -> Optional[ReturnRequest]:
        return (
            self.db.query(ReturnRequest)
            .filter_by(returnRequestID=request_id)
            .first()
        )

    def _require_status(
        self,
        request_id: int,
        *allowed_statuses: ReturnRequestStatus,
    ) -> Optional[ReturnRequest]:
        request = self._get_return_request(request_id)
        if not request:
            return None
        if allowed_statuses and request.status not in set(allowed_statuses):
            return None
        return request

