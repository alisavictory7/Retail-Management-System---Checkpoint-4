from __future__ import annotations

import logging
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.models import (
    ReturnRequest,
    ReturnRequestStatus,
    Refund,
    RefundStatus,
    RefundMethod,
    Payment,
)
from src.services.payment_service import PaymentService
from src.services.inventory_service import InventoryService
from src.observability import increment_counter, record_event


class RefundService:
    """Coordinates refund execution via PaymentService and inventory adjustments."""

    def __init__(
        self,
        db_session: Session,
        payment_service: Optional[PaymentService] = None,
        inventory_service: Optional[InventoryService] = None,
    ) -> None:
        self.db = db_session
        self.logger = logging.getLogger(__name__)
        self.payment_service = payment_service or PaymentService(db_session)
        self.inventory_service = inventory_service or InventoryService(db_session)

    def process_refund(
        self,
        return_request_id: int,
        method: Optional[RefundMethod | str] = None,
        amount_override: Optional[float] = None,
    ) -> Tuple[bool, str, Optional[Refund]]:
        """
        Trigger the refund workflow for an approved return request.
        """
        return_request = (
            self.db.query(ReturnRequest)
            .filter_by(returnRequestID=return_request_id)
            .first()
        )
        if not return_request:
            return False, "Return request not found", None

        if return_request.status not in {
            ReturnRequestStatus.APPROVED,
            ReturnRequestStatus.REFUNDED,
        }:
            return False, f"Return request is not approved (current status: {return_request.status})", None

        if return_request.status == ReturnRequestStatus.REFUNDED:
            return True, "Return request already refunded", return_request.refund

        payment = (
            self.db.query(Payment)
            .filter_by(saleID=return_request.saleID)
            .order_by(desc(Payment.paymentID))
            .first()
        )

        if not payment:
            return False, "No payment record associated with this sale", None

        refund_amount = amount_override or return_request.calculate_requested_amount()
        if refund_amount <= 0:
            return False, "Calculated refund amount is zero; nothing to refund", None

        refund_method = self._determine_refund_method(method, payment)

        refund = return_request.refund
        if refund and refund.status == RefundStatus.COMPLETED:
            return True, "Refund already completed", refund
        if not refund:
            refund = Refund(
                returnRequestID=return_request.returnRequestID,
                paymentID=payment.paymentID,
                amount=refund_amount,
                method=refund_method,
            )
            self.db.add(refund)
        else:
            refund.amount = refund_amount
            refund.method = refund_method
            refund.status = RefundStatus.PENDING
            refund.failure_reason = None

        self.db.flush()

        success, message, reference = self.payment_service.refund(payment, refund_amount)
        if success:
            refund.mark_completed(reference)
            return_request.status = ReturnRequestStatus.REFUNDED
            self.inventory_service.apply_return_stock(return_request)
            self.db.commit()
            increment_counter("refunds_completed_total")
            record_event(
                "refund_completed",
                {
                    "return_request_id": return_request.returnRequestID,
                    "refund_id": refund.refundID,
                    "amount": float(refund.amount),
                },
            )
            self.logger.info(
                "Refund completed for return request %s",
                return_request.returnRequestID,
                extra={"refund_id": refund.refundID, "amount": refund_amount},
            )
            return True, message, refund

        refund.mark_failed(message)
        self.db.commit()
        increment_counter("refunds_failed_total")
        record_event(
            "refund_failed",
            {
                "return_request_id": return_request.returnRequestID,
                "reason": message,
            },
        )
        self.logger.warning(
            "Refund failed for return request %s",
            return_request.returnRequestID,
            extra={"reason": message},
        )
        return False, message, refund

    @staticmethod
    def _determine_refund_method(
        requested_method: Optional[RefundMethod | str],
        payment: Payment,
    ) -> RefundMethod:
        if requested_method:
            return (
                requested_method
                if isinstance(requested_method, RefundMethod)
                else RefundMethod(requested_method)
            )

        payment_type = (payment.payment_type or payment.type or "").lower()
        if payment_type == "card":
            return RefundMethod.CARD
        if payment_type == "cash":
            return RefundMethod.CASH
        return RefundMethod.ORIGINAL_METHOD

