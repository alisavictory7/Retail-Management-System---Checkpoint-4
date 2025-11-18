from __future__ import annotations

import logging
import random
import uuid
from typing import Optional, Tuple, Dict, Any

from sqlalchemy.orm import Session

from src.models import Payment
from src.tactics.availability import PaymentServiceCircuitBreaker
from src.config import Config


class PaymentService:
    """
    Wrapper around outbound payment/refund operations.
    In CP3 we simulate the gateway but still exercise reliability tactics (circuit breaker).
    """

    def __init__(
        self,
        db_session: Session,
        circuit_breaker_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.db = db_session
        self.logger = logging.getLogger(__name__)
        self.circuit_breaker = PaymentServiceCircuitBreaker(
            db_session,
            circuit_breaker_config or {},
        )

    def refund(self, payment: Payment, amount: float) -> Tuple[bool, str, Optional[str]]:
        """
        Attempt to refund the specified payment amount.
        Returns (success flag, message, external reference or None).
        """
        if payment is None:
            return False, "Payment record is required for refunds", None
        if amount <= 0:
            return False, "Refund amount must be positive", None
        if payment.amount is None or amount > float(payment.amount):
            return False, "Refund amount exceeds original payment", None

        def _perform_refund() -> str:
            # Simulate upstream instability to exercise the circuit breaker.
            failure_probability = Config.PAYMENT_REFUND_FAILURE_PROBABILITY
            if random.random() < failure_probability:
                raise RuntimeError("Payment processor timeout")

            reference = f"RF-{payment.paymentID}-{uuid.uuid4().hex[:8].upper()}"
            self.logger.info(
                "Refund processed",
                extra={
                    "payment_id": payment.paymentID,
                    "sale_id": payment.saleID,
                    "amount": amount,
                    "reference": reference,
                },
            )
            return reference

        success, result = self.circuit_breaker.execute(_perform_refund)
        if success:
            return True, "Refund processed successfully", result

        self.logger.warning(
            "Refund attempt failed via circuit breaker",
            extra={
                "payment_id": payment.paymentID if payment else None,
                "sale_id": payment.saleID if payment else None,
                "reason": result,
            },
        )
        return False, result, None

