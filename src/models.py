# src/models.py
from enum import Enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    DateTime,
    ForeignKey,
    Boolean,
    Text,
    Enum as SAEnum,
)
from sqlalchemy.orm import relationship

# Use a single, shared Base for all models
# This ensures all models use the same SQLAlchemy metadata, preventing conflicts.
from src.database import Base


class ReturnRequestStatus(str, Enum):
    PENDING_CUSTOMER_INFO = "PENDING_CUSTOMER_INFO"
    PENDING_AUTHORIZATION = "PENDING_AUTHORIZATION"
    AUTHORIZED = "AUTHORIZED"
    IN_TRANSIT = "IN_TRANSIT"
    RECEIVED = "RECEIVED"
    UNDER_INSPECTION = "UNDER_INSPECTION"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REFUNDED = "REFUNDED"
    CANCELLED = "CANCELLED"


class ReturnReason(str, Enum):
    DAMAGED = "DAMAGED"
    WRONG_ITEM = "WRONG_ITEM"
    NOT_AS_DESCRIBED = "NOT_AS_DESCRIBED"
    OTHER = "OTHER"


class InspectionResult(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    PARTIALLY_APPROVED = "PARTIALLY_APPROVED"
    REJECTED = "REJECTED"


class RefundStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RefundMethod(str, Enum):
    CARD = "CARD"
    CASH = "CASH"
    STORE_CREDIT = "STORE_CREDIT"
    ORIGINAL_METHOD = "ORIGINAL_METHOD"

class User(Base):
    __tablename__ = 'User'
    userID = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), unique=True, nullable=False)
    _passwordHash = Column('passwordHash', String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    _created_at = Column('created_at', DateTime, default=lambda: datetime.now(timezone.utc))
    role = Column(String(50), default='customer', nullable=False)
    sales = relationship("Sale", back_populates="user")
    return_requests = relationship("ReturnRequest", back_populates="customer")
    
    @property
    def passwordHash(self):
        return self._passwordHash
    
    @passwordHash.setter
    def passwordHash(self, value):
        self._passwordHash = value
    
    @property
    def created_at(self):
        return self._created_at

    @property
    def is_admin(self) -> bool:
        return (self.role or '').lower() == 'admin'

class Product(Base):
    __tablename__ = 'Product'
    productID = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(String)
    price = Column(Numeric(10, 2), nullable=False)
    stock = Column(Integer, nullable=False)
    _shipping_weight = Column('shipping_weight', Numeric(10, 2), nullable=False, default=0.0)
    _discount_percent = Column('discount_percent', Numeric(5, 2), nullable=False, default=0.0)
    _country_of_origin = Column('country_of_origin', String(255))
    _requires_shipping = Column('requires_shipping', Boolean, default=True)

    @property
    def shipping_weight(self):
        return self._shipping_weight
    
    @property
    def discount_percent(self):
        return self._discount_percent
    
    @property
    def country_of_origin(self):
        return self._country_of_origin
    
    @property
    def requires_shipping(self):
        return self._requires_shipping

    def get_discounted_unit_price(self) -> float:
        return float(self.price) * (1 - float(self._discount_percent) / 100)

    def get_shipping_fees(self, quantity: int) -> float:
        if not self._requires_shipping:
            return 0.0
        return (float(self._shipping_weight) * quantity) * 1.5

    def get_import_duty(self, quantity: int) -> float:
        if self._country_of_origin == 'USA':
            return 0.0
        return float(self.price) * quantity * 0.05
        
    def get_subtotal_for_quantity(self, quantity: int) -> float:
        return self.get_discounted_unit_price() * quantity


class Sale(Base):
    __tablename__ = 'Sale'
    saleID = Column(Integer, primary_key=True, autoincrement=True)
    userID = Column(Integer, ForeignKey('User.userID'))
    _sale_date = Column('sale_date', DateTime, nullable=False)
    _totalAmount = Column('totalAmount', Numeric(10, 2), nullable=False)
    _status = Column('status', String(50))
    user = relationship("User", back_populates="sales")
    items = relationship("SaleItem", back_populates="sale")
    payments = relationship("Payment", back_populates="sale")
    return_requests = relationship("ReturnRequest", back_populates="sale")
    
    @property
    def sale_date(self):
        return self._sale_date
    
    @sale_date.setter
    def sale_date(self, value):
        self._sale_date = value
    
    @property
    def totalAmount(self):
        return self._totalAmount
    
    @totalAmount.setter
    def totalAmount(self, value):
        self._totalAmount = value
    
    @property
    def status(self):
        return self._status
    
    @status.setter
    def status(self, value):
        self._status = value

class SaleItem(Base):
    __tablename__ = 'SaleItem'
    saleItemID = Column(Integer, primary_key=True, autoincrement=True)
    saleID = Column(Integer, ForeignKey('Sale.saleID'))
    productID = Column(Integer, ForeignKey('Product.productID'))
    quantity = Column(Integer, nullable=False)
    _original_unit_price = Column('original_unit_price', Numeric(10, 2), nullable=False)
    _final_unit_price = Column('final_unit_price', Numeric(10, 2), nullable=False)
    _discount_applied = Column('discount_applied', Numeric(10, 2), nullable=False)
    _shipping_fee_applied = Column('shipping_fee_applied', Numeric(10, 2), nullable=False)
    _import_duty_applied = Column('import_duty_applied', Numeric(10, 2), nullable=False)
    _subtotal = Column('subtotal', Numeric(10, 2), nullable=False)
    sale = relationship("Sale", back_populates="items")
    product = relationship("Product")
    return_items = relationship("ReturnItem", back_populates="sale_item")
    
    @property
    def original_unit_price(self):
        return self._original_unit_price
    
    @original_unit_price.setter
    def original_unit_price(self, value):
        self._original_unit_price = value
    
    @property
    def final_unit_price(self):
        return self._final_unit_price
    
    @final_unit_price.setter
    def final_unit_price(self, value):
        self._final_unit_price = value
    
    @property
    def discount_applied(self):
        return self._discount_applied
    
    @discount_applied.setter
    def discount_applied(self, value):
        self._discount_applied = value
    
    @property
    def shipping_fee_applied(self):
        return self._shipping_fee_applied
    
    @shipping_fee_applied.setter
    def shipping_fee_applied(self, value):
        self._shipping_fee_applied = value
    
    @property
    def import_duty_applied(self):
        return self._import_duty_applied
    
    @import_duty_applied.setter
    def import_duty_applied(self, value):
        self._import_duty_applied = value
    
    @property
    def subtotal(self):
        return self._subtotal
    
    @subtotal.setter
    def subtotal(self, value):
        self._subtotal = value

class Payment(Base):
    __tablename__ = 'Payment'
    paymentID = Column(Integer, primary_key=True)
    saleID = Column(Integer, ForeignKey('Sale.saleID'))
    _payment_date = Column('payment_date', DateTime, default=lambda: datetime.now(timezone.utc))
    amount = Column(Numeric(10, 2))
    _status = Column('status', String(20))
    _payment_type = Column('payment_type', String(50))
    type = Column(String(50))  # This line is required for polymorphic identity
    sale = relationship("Sale", back_populates="payments")
    refunds = relationship("Refund", back_populates="payment")
    __mapper_args__ = {
        'polymorphic_identity': 'payment',
        'polymorphic_on': type
    }
    
    @property
    def payment_date(self):
        return self._payment_date
    
    @payment_date.setter
    def payment_date(self, value):
        self._payment_date = value
    
    @property
    def status(self):
        return self._status
    
    @status.setter
    def status(self, value):
        self._status = value
    
    @property
    def payment_type(self):
        return self._payment_type
    
    @payment_type.setter
    def payment_type(self, value):
        self._payment_type = value

    def authorized(self) -> (bool, str):
        # Default behavior: always authorized
        return True, "Approved"

class Cash(Payment):
    _cash_tendered = Column('cash_tendered', Numeric(10, 2))
    __mapper_args__ = {'polymorphic_identity': 'cash'}
    
    @property
    def cash_tendered(self):
        return self._cash_tendered
    
    @cash_tendered.setter
    def cash_tendered(self, value):
        self._cash_tendered = value

class Card(Payment):
    _card_number = Column('card_number', String(255))
    _card_type = Column('card_type', String(50))
    _card_exp_date = Column('card_exp_date', String(7)) # MM/YYYY
    __mapper_args__ = {'polymorphic_identity': 'card'}
    
    @property
    def card_number(self):
        return self._card_number
    
    @card_number.setter
    def card_number(self, value):
        self._card_number = value
    
    @property
    def card_type(self):
        return self._card_type
    
    @card_type.setter
    def card_type(self, value):
        self._card_type = value
    
    @property
    def card_exp_date(self):
        return self._card_exp_date
    
    @card_exp_date.setter
    def card_exp_date(self, value):
        self._card_exp_date = value

    def authorized(self) -> (bool, str):
        card_num_str = self._card_number.strip() if self._card_number else ""
        if not card_num_str.isdigit() or not (15 <= len(card_num_str) <= 19):
            return False, "Invalid Card Number (must be 15-19 digits)"
        try:
            exp_month, exp_year = map(int, self._card_exp_date.split('/'))
            current_date = datetime.now(timezone.utc)
            if (exp_year < current_date.year) or (exp_year == current_date.year and exp_month < current_date.month):
                return False, "Card Expired"
        except (ValueError, TypeError):
            return False, "Invalid Expiry Date Format"
        if "1111" in self._card_number:
            return False, "Card Declined by issuer"
        return True, "Approved"


class ReturnRequest(Base):
    __tablename__ = 'ReturnRequest'

    returnRequestID = Column(Integer, primary_key=True, autoincrement=True)
    saleID = Column(Integer, ForeignKey('Sale.saleID'), nullable=False)
    customerID = Column(Integer, ForeignKey('User.userID'), nullable=False)
    status = Column(
        SAEnum(ReturnRequestStatus, name="return_request_status", native_enum=False, validate_strings=True),
        default=ReturnRequestStatus.PENDING_AUTHORIZATION,
        nullable=False,
    )
    reason = Column(
        SAEnum(ReturnReason, name="return_reason", native_enum=False, validate_strings=True),
        nullable=False,
    )
    details = Column(Text)
    photos_url = Column(String(512))
    rma_number = Column(String(50), unique=True)
    decision_notes = Column(Text)
    policy_window_days = Column(Integer, default=30)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    sale = relationship("Sale", back_populates="return_requests")
    customer = relationship("User", back_populates="return_requests")
    return_items = relationship("ReturnItem", back_populates="return_request", cascade="all, delete-orphan")
    shipment = relationship("ReturnShipment", uselist=False, back_populates="return_request", cascade="all, delete-orphan")
    inspection = relationship("Inspection", uselist=False, back_populates="return_request", cascade="all, delete-orphan")
    refund = relationship("Refund", uselist=False, back_populates="return_request", cascade="all, delete-orphan")
    photos = relationship("ReturnPhoto", back_populates="return_request", cascade="all, delete-orphan")

    _VALID_TRANSITIONS = {
        ReturnRequestStatus.PENDING_CUSTOMER_INFO: {ReturnRequestStatus.PENDING_AUTHORIZATION, ReturnRequestStatus.CANCELLED},
        ReturnRequestStatus.PENDING_AUTHORIZATION: {ReturnRequestStatus.AUTHORIZED, ReturnRequestStatus.REJECTED, ReturnRequestStatus.CANCELLED},
        ReturnRequestStatus.AUTHORIZED: {ReturnRequestStatus.IN_TRANSIT, ReturnRequestStatus.REJECTED},
        ReturnRequestStatus.IN_TRANSIT: {ReturnRequestStatus.RECEIVED},
        ReturnRequestStatus.RECEIVED: {ReturnRequestStatus.UNDER_INSPECTION},
        ReturnRequestStatus.UNDER_INSPECTION: {ReturnRequestStatus.APPROVED, ReturnRequestStatus.REJECTED},
        ReturnRequestStatus.APPROVED: {ReturnRequestStatus.REFUNDED},
        ReturnRequestStatus.REJECTED: {ReturnRequestStatus.CANCELLED},
    }

    def can_transition(self, new_status: ReturnRequestStatus) -> bool:
        allowed = self._VALID_TRANSITIONS.get(ReturnRequestStatus(self.status), set())
        return new_status in allowed

    def transition_to(self, new_status: ReturnRequestStatus) -> None:
        if not self.can_transition(new_status):
            raise ValueError(f"Invalid return status transition from {self.status} to {new_status}")
        self.status = new_status

    def calculate_requested_amount(self) -> float:
        total = 0.0
        for item in self.return_items:
            total += item.requested_refund_amount
        return round(total, 2)

    def is_within_policy(self, return_window_days: int) -> bool:
        if not self.sale or not self.sale.sale_date:
            return False
        delta = datetime.now(timezone.utc) - self.sale.sale_date
        return delta.days <= return_window_days


class ReturnItem(Base):
    __tablename__ = 'ReturnItem'

    returnItemID = Column(Integer, primary_key=True, autoincrement=True)
    returnRequestID = Column(Integer, ForeignKey('ReturnRequest.returnRequestID'), nullable=False)
    saleItemID = Column(Integer, ForeignKey('SaleItem.saleItemID'), nullable=False)
    quantity = Column(Integer, nullable=False)
    condition_report = Column(Text)
    restocking_fee = Column(Numeric(10, 2), default=0.0)

    return_request = relationship("ReturnRequest", back_populates="return_items")
    sale_item = relationship("SaleItem", back_populates="return_items")

    @property
    def requested_refund_amount(self) -> float:
        if not self.sale_item:
            return 0.0
        unit_price = float(self.sale_item.final_unit_price)
        requested_qty = min(self.quantity, self.sale_item.quantity)
        return round(max(unit_price * requested_qty - float(self.restocking_fee or 0), 0), 2)


class ReturnShipment(Base):
    __tablename__ = 'ReturnShipment'

    shipmentID = Column(Integer, primary_key=True, autoincrement=True)
    returnRequestID = Column(Integer, ForeignKey('ReturnRequest.returnRequestID'), nullable=False)
    carrier = Column(String(120))
    tracking_number = Column(String(120))
    shipped_at = Column(DateTime)
    received_at = Column(DateTime)
    notes = Column(Text)

    return_request = relationship("ReturnRequest", back_populates="shipment")


class ReturnPhoto(Base):
    __tablename__ = 'ReturnPhoto'

    photoID = Column(Integer, primary_key=True, autoincrement=True)
    returnRequestID = Column(Integer, ForeignKey('ReturnRequest.returnRequestID', ondelete="CASCADE"), nullable=False)
    file_path = Column(String(512), nullable=False)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    return_request = relationship("ReturnRequest", back_populates="photos")


class Inspection(Base):
    __tablename__ = 'Inspection'

    inspectionID = Column(Integer, primary_key=True, autoincrement=True)
    returnRequestID = Column(Integer, ForeignKey('ReturnRequest.returnRequestID'), nullable=False)
    inspected_by = Column(String(120))
    inspected_at = Column(DateTime)
    result = Column(
        SAEnum(InspectionResult, name="inspection_result", native_enum=False, validate_strings=True),
        default=InspectionResult.PENDING,
        nullable=False,
    )
    notes = Column(Text)

    return_request = relationship("ReturnRequest", back_populates="inspection")


class Refund(Base):
    __tablename__ = 'Refund'

    refundID = Column(Integer, primary_key=True, autoincrement=True)
    returnRequestID = Column(Integer, ForeignKey('ReturnRequest.returnRequestID'), nullable=False)
    paymentID = Column(Integer, ForeignKey('Payment.paymentID'), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    method = Column(
        SAEnum(RefundMethod, name="refund_method", native_enum=False, validate_strings=True),
        nullable=False,
    )
    status = Column(
        SAEnum(RefundStatus, name="refund_status", native_enum=False, validate_strings=True),
        default=RefundStatus.PENDING,
        nullable=False,
    )
    failure_reason = Column(String(255))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime)
    external_reference = Column(String(120))

    return_request = relationship("ReturnRequest", back_populates="refund")
    payment = relationship("Payment", back_populates="refunds")

    def mark_completed(self, reference: str | None = None) -> None:
        self.status = RefundStatus.COMPLETED
        self.processed_at = datetime.now(timezone.utc)
        if reference:
            self.external_reference = reference

    def mark_failed(self, reason: str) -> None:
        self.status = RefundStatus.FAILED
        self.failure_reason = reason
        self.processed_at = datetime.now(timezone.utc)

class FailedPaymentLog(Base):
    __tablename__ = 'FailedPaymentLog'
    logID = Column(Integer, primary_key=True, autoincrement=True)
    userID = Column(Integer, ForeignKey('User.userID'))
    _attempt_date = Column('attempt_date', DateTime, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    _payment_method = Column('payment_method', String(50), nullable=False)
    _reason = Column('reason', String(255))
    
    @property
    def attempt_date(self):
        return self._attempt_date
    
    @attempt_date.setter
    def attempt_date(self, value):
        self._attempt_date = value
    
    @property
    def payment_method(self):
        return self._payment_method
    
    @payment_method.setter
    def payment_method(self, value):
        self._payment_method = value
    
    @property
    def reason(self):
        return self._reason
    
    @reason.setter
    def reason(self, value):
        self._reason = value

# ==============================================
# CHECKPOINT 2: NEW MODELS FOR QUALITY TACTICS
# ==============================================

# Circuit Breaker Model (Availability tactic)
class CircuitBreakerState(Base):
    __tablename__ = 'CircuitBreakerState'
    breakerID = Column(Integer, primary_key=True, autoincrement=True)
    service_name = Column(String(100), unique=True, nullable=False)
    state = Column(String(20), nullable=False, default='closed')  # closed, open, half_open
    failure_count = Column(Integer, default=0)
    last_failure_time = Column(DateTime)
    next_attempt_time = Column(DateTime)
    failure_threshold = Column(Integer, default=5)
    timeout_duration = Column(Integer, default=60)  # seconds
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

# Order Queue Model (Availability & Performance tactics)
class OrderQueue(Base):
    __tablename__ = 'OrderQueue'
    queueID = Column(Integer, primary_key=True, autoincrement=True)
    saleID = Column(Integer, ForeignKey('Sale.saleID'), nullable=False)
    userID = Column(Integer, ForeignKey('User.userID'), nullable=False)
    queue_type = Column(String(50), nullable=False)  # payment_retry, flash_sale, processing
    priority = Column(Integer, default=0)  # higher number = higher priority
    status = Column(String(20), default='pending')  # pending, processing, completed, failed
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    scheduled_for = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    error_message = Column(String)
    retry_after = Column(DateTime)
    sale = relationship("Sale")
    user = relationship("User")

# Feature Toggle Model (Modifiability tactic)
class FeatureToggle(Base):
    __tablename__ = 'FeatureToggle'
    toggleID = Column(Integer, primary_key=True, autoincrement=True)
    feature_name = Column(String(100), unique=True, nullable=False)
    is_enabled = Column(Boolean, default=False)
    description = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    updated_by = Column(String(100))
    rollout_percentage = Column(Integer, default=0)  # 0-100 for gradual rollouts
    target_users = Column(String)  # JSON array of user IDs or conditions

# Message Queue Model (Integrability tactic - Publish-Subscribe)
class MessageQueue(Base):
    __tablename__ = 'MessageQueue'
    messageID = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(String(100), nullable=False)
    message_type = Column(String(50), nullable=False)
    payload = Column(String, nullable=False)  # JSON message content
    status = Column(String(20), default='pending')  # pending, processing, completed, failed
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    scheduled_for = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    error_message = Column(String)
    subscriber_id = Column(String(100))  # which subscriber processed this

# Test Record Model (Testability tactic - Record/Playback)
class TestRecord(Base):
    __tablename__ = 'TestRecord'
    recordID = Column(Integer, primary_key=True, autoincrement=True)
    test_name = Column(String(100), nullable=False)
    record_type = Column(String(50), nullable=False)  # request, response, state
    sequence_number = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    data = Column(String, nullable=False)  # JSON data
    record_metadata = Column(String)  # JSON metadata (renamed from 'metadata')
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

# Audit Log Model (Security & Monitoring)
class AuditLog(Base):
    __tablename__ = 'AuditLog'
    auditID = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(50), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer)
    user_id = Column(Integer, ForeignKey('User.userID'))
    action = Column(String(100), nullable=False)
    old_values = Column(String)  # JSON
    new_values = Column(String)  # JSON
    ip_address = Column(String(45))
    user_agent = Column(String)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    success = Column(Boolean, default=True)
    error_message = Column(String)
    user = relationship("User")

# System Metrics Model (Monitoring)
class SystemMetrics(Base):
    __tablename__ = 'SystemMetrics'
    metricID = Column(Integer, primary_key=True, autoincrement=True)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Numeric(15, 4), nullable=False)
    metric_unit = Column(String(20))  # ms, count, percent, etc.
    tags = Column(String)  # JSON key-value pairs
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    service_name = Column(String(100))
    instance_id = Column(String(100))

# ==============================================
# EXISTING MODELS (Updated for Checkpoint 2)
# ==============================================

# Flash Sale Models
class FlashSale(Base):
    __tablename__ = 'FlashSale'
    flashSaleID = Column(Integer, primary_key=True, autoincrement=True)
    productID = Column(Integer, ForeignKey('Product.productID'), nullable=False)
    _title = Column('title', String(255), nullable=False, default='Flash Sale')
    _start_time = Column('start_time', DateTime, nullable=False)
    _end_time = Column('end_time', DateTime, nullable=False)
    _discount_percent = Column('discount_percent', Numeric(5, 2), nullable=False)
    _max_quantity = Column('max_quantity', Integer, nullable=False)
    _reserved_quantity = Column('reserved_quantity', Integer, default=0)
    _status = Column('status', String(20), default='active')  # active, expired, cancelled
    product = relationship("Product")
    
    @property
    def start_time(self):
        return self._start_time
    
    @start_time.setter
    def start_time(self, value):
        self._start_time = value

    @property
    def title(self):
        return self._title
    
    @title.setter
    def title(self, value):
        self._title = value
    
    @property
    def end_time(self):
        return self._end_time
    
    @end_time.setter
    def end_time(self, value):
        self._end_time = value
    
    @property
    def discount_percent(self):
        return self._discount_percent
    
    @discount_percent.setter
    def discount_percent(self, value):
        self._discount_percent = value
    
    @property
    def max_quantity(self):
        return self._max_quantity
    
    @max_quantity.setter
    def max_quantity(self, value):
        self._max_quantity = value
    
    @property
    def reserved_quantity(self):
        return self._reserved_quantity
    
    @reserved_quantity.setter
    def reserved_quantity(self, value):
        self._reserved_quantity = value
    
    @property
    def status(self):
        return self._status
    
    @status.setter
    def status(self, value):
        self._status = value
    
    def is_active(self) -> bool:
        now = datetime.now(timezone.utc)
        return (self._status == 'active' and 
                self._start_time <= now <= self._end_time and
                self._reserved_quantity < self._max_quantity)
    
    def get_available_quantity(self) -> int:
        return max(0, self._max_quantity - self._reserved_quantity)

class FlashSaleReservation(Base):
    __tablename__ = 'FlashSaleReservation'
    reservationID = Column(Integer, primary_key=True, autoincrement=True)
    flashSaleID = Column(Integer, ForeignKey('FlashSale.flashSaleID'), nullable=False)
    userID = Column(Integer, ForeignKey('User.userID'), nullable=False)
    quantity = Column(Integer, nullable=False)
    _reserved_at = Column('reserved_at', DateTime, default=lambda: datetime.now(timezone.utc))
    _expires_at = Column('expires_at', DateTime, nullable=False)
    _status = Column('status', String(20), default='reserved')  # reserved, confirmed, expired, cancelled
    flash_sale = relationship("FlashSale")
    user = relationship("User")
    
    @property
    def reserved_at(self):
        return self._reserved_at
    
    @reserved_at.setter
    def reserved_at(self, value):
        self._reserved_at = value
    
    @property
    def expires_at(self):
        return self._expires_at
    
    @expires_at.setter
    def expires_at(self, value):
        self._expires_at = value
    
    @property
    def status(self):
        return self._status
    
    @status.setter
    def status(self, value):
        self._status = value
    
    def is_valid(self) -> bool:
        now = datetime.now(timezone.utc)
        return (self._status == 'reserved' and 
                now <= self._expires_at)

# Partner/VAR Catalog Models
class Partner(Base):
    __tablename__ = 'Partner'
    partnerID = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    _api_endpoint = Column('api_endpoint', String(500))
    _api_key = Column('api_key', String(255))
    _sync_frequency = Column('sync_frequency', Integer, default=3600)  # seconds
    _last_sync = Column('last_sync', DateTime)
    _status = Column('status', String(20), default='active')
    
    @property
    def api_endpoint(self):
        return self._api_endpoint
    
    @api_endpoint.setter
    def api_endpoint(self, value):
        self._api_endpoint = value
    
    @property
    def api_key(self):
        return self._api_key
    
    @api_key.setter
    def api_key(self, value):
        self._api_key = value
    
    @property
    def sync_frequency(self):
        return self._sync_frequency
    
    @sync_frequency.setter
    def sync_frequency(self, value):
        self._sync_frequency = value
    
    @property
    def last_sync(self):
        return self._last_sync
    
    @last_sync.setter
    def last_sync(self, value):
        self._last_sync = value
    
    @property
    def status(self):
        return self._status
    
    @status.setter
    def status(self, value):
        self._status = value

class PartnerAPIKey(Base):
    __tablename__ = 'PartnerAPIKey'
    keyID = Column(Integer, primary_key=True, autoincrement=True)
    partnerID = Column(Integer, ForeignKey('Partner.partnerID'), nullable=False)
    api_key = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    last_used = Column(DateTime)
    usage_count = Column(Integer, default=0)
    partner = relationship("Partner")

class PartnerProduct(Base):
    __tablename__ = 'PartnerProduct'
    partnerProductID = Column(Integer, primary_key=True, autoincrement=True)
    partnerID = Column(Integer, ForeignKey('Partner.partnerID'), nullable=False)
    _external_product_id = Column('external_product_id', String(255), nullable=False)
    productID = Column(Integer, ForeignKey('Product.productID'))
    _sync_status = Column('sync_status', String(20), default='pending')
    _last_synced = Column('last_synced', DateTime)
    _sync_data = Column('sync_data', String)  # JSON data from partner
    partner = relationship("Partner")
    product = relationship("Product")
    
    @property
    def external_product_id(self):
        return self._external_product_id
    
    @external_product_id.setter
    def external_product_id(self, value):
        self._external_product_id = value
    
    @property
    def sync_status(self):
        return self._sync_status
    
    @sync_status.setter
    def sync_status(self, value):
        self._sync_status = value
    
    @property
    def last_synced(self):
        return self._last_synced
    
    @last_synced.setter
    def last_synced(self, value):
        self._last_synced = value
    
    @property
    def sync_data(self):
        return self._sync_data
    
    @sync_data.setter
    def sync_data(self, value):
        self._sync_data = value

