# src/services/flash_sale_service.py
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from src.models import FlashSale, FlashSaleReservation, Product, User
import logging

logger = logging.getLogger(__name__)

class FlashSaleService:
    """Service class for managing Flash Sale operations using Repository pattern"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def create_flash_sale(
        self,
        product_id: int,
        start_time: datetime,
        end_time: datetime,
        discount_percent: float,
        max_quantity: int,
        title: str = "Flash Sale",
    ) -> Tuple[bool, str, Optional[FlashSale]]:
        """Create a new flash sale"""
        try:
            # Validate product exists
            product = self.db.query(Product).filter_by(productID=product_id).first()
            if not product:
                return False, "Product not found", None
            
            # Validate time range
            if start_time >= end_time:
                return False, "Start time must be before end time", None
            if end_time <= datetime.now(timezone.utc):
                return False, "End time must be in the future", None
            
            # Validate discount
            if not (0 <= discount_percent <= 100):
                return False, "Discount must be between 0 and 100 percent", None
            if max_quantity <= 0:
                return False, "Max quantity must be positive", None
            if not title or not title.strip():
                return False, "Title is required", None
            
            # Check for overlapping flash sales
            overlapping = self.db.query(FlashSale).filter(
                FlashSale.productID == product_id,
                FlashSale._status == 'active',
                FlashSale._start_time < end_time,
                FlashSale._end_time > start_time
            ).first()
            
            if overlapping:
                return False, "Overlapping flash sale already exists for this product", None
            
            flash_sale = FlashSale(
                productID=product_id,
                title=title.strip(),
                start_time=start_time,
                end_time=end_time,
                discount_percent=discount_percent,
                max_quantity=max_quantity,
                reserved_quantity=0,
                status='active'
            )
            
            self.db.add(flash_sale)
            self.db.commit()
            self.db.refresh(flash_sale)
            
            logger.info(f"Created flash sale {flash_sale.flashSaleID} for product {product_id}")
            return True, "Flash sale created successfully", flash_sale
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating flash sale: {e}")
            return False, f"Error creating flash sale: {str(e)}", None
    
    def get_active_flash_sales(self) -> List[FlashSale]:
        """Get all currently active flash sales"""
        now = datetime.now(timezone.utc)
        return self.db.query(FlashSale).filter(
            FlashSale._status == 'active',
            FlashSale._start_time <= now,
            FlashSale._end_time > now,
            FlashSale._reserved_quantity < FlashSale._max_quantity
        ).all()
    
    def get_flash_sale_by_id(self, flash_sale_id: int) -> Optional[FlashSale]:
        """Get flash sale by ID"""
        return self.db.query(FlashSale).filter_by(flashSaleID=flash_sale_id).first()
    
    def reserve_flash_sale_item(self, flash_sale_id: int, user_id: int, quantity: int) -> Tuple[bool, str, Optional[FlashSaleReservation]]:
        """Reserve items in a flash sale"""
        try:
            flash_sale = self.get_flash_sale_by_id(flash_sale_id)
            if not flash_sale:
                return False, "Flash sale not found", None
            
            if not flash_sale.is_active():
                return False, "Flash sale is not active", None
            
            if quantity <= 0:
                return False, "Quantity must be positive", None
            
            if quantity > flash_sale.get_available_quantity():
                return False, f"Not enough items available. Only {flash_sale.get_available_quantity()} left", None
            
            # Check for existing reservation by this user
            existing_reservation = self.db.query(FlashSaleReservation).filter(
                FlashSaleReservation.flashSaleID == flash_sale_id,
                FlashSaleReservation.userID == user_id,
                FlashSaleReservation._status == 'reserved'
            ).first()
            
            if existing_reservation:
                return False, "You already have a reservation for this flash sale", None
            
            # Create reservation
            reservation = FlashSaleReservation(
                flashSaleID=flash_sale_id,
                userID=user_id,
                quantity=quantity,
                reserved_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),  # 15-minute reservation
                status='reserved'
            )
            
            # Update flash sale reserved quantity
            flash_sale.reserved_quantity += quantity
            
            self.db.add(reservation)
            self.db.commit()
            self.db.refresh(reservation)
            
            logger.info(f"Created reservation {reservation.reservationID} for flash sale {flash_sale_id}")
            return True, "Items reserved successfully", reservation
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error reserving flash sale items: {e}")
            return False, f"Error reserving items: {str(e)}", None
    
    def confirm_flash_sale_reservation(self, reservation_id: int) -> Tuple[bool, str]:
        """Confirm a flash sale reservation (convert to regular sale)"""
        try:
            reservation = self.db.query(FlashSaleReservation).filter_by(reservationID=reservation_id).first()
            if not reservation:
                return False, "Reservation not found"
            
            if not reservation.is_valid():
                return False, "Reservation has expired or is invalid"
            
            # Mark reservation as confirmed
            reservation.status = 'confirmed'
            
            # Update flash sale
            flash_sale = reservation.flash_sale
            flash_sale.reserved_quantity -= reservation.quantity
            
            # If all items are sold, mark flash sale as expired
            if flash_sale.reserved_quantity >= flash_sale.max_quantity:
                flash_sale.status = 'expired'
            
            self.db.commit()
            
            logger.info(f"Confirmed reservation {reservation_id}")
            return True, "Reservation confirmed successfully"
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error confirming reservation: {e}")
            return False, f"Error confirming reservation: {str(e)}"
    
    def cancel_flash_sale_reservation(self, reservation_id: int) -> Tuple[bool, str]:
        """Cancel a flash sale reservation"""
        try:
            reservation = self.db.query(FlashSaleReservation).filter_by(reservationID=reservation_id).first()
            if not reservation:
                return False, "Reservation not found"
            
            if reservation.status != 'reserved':
                return False, "Reservation cannot be cancelled"
            
            # Update flash sale reserved quantity
            flash_sale = reservation.flash_sale
            flash_sale.reserved_quantity -= reservation.quantity
            
            # Mark reservation as cancelled
            reservation.status = 'cancelled'
            
            self.db.commit()
            
            logger.info(f"Cancelled reservation {reservation_id}")
            return True, "Reservation cancelled successfully"
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error cancelling reservation: {e}")
            return False, f"Error cancelling reservation: {str(e)}"
    
    def cleanup_expired_reservations(self) -> int:
        """Clean up expired reservations and return count of cleaned items"""
        try:
            now = datetime.now(timezone.utc)
            expired_reservations = self.db.query(FlashSaleReservation).filter(
                FlashSaleReservation._status == 'reserved',
                FlashSaleReservation._expires_at < now
            ).all()
            
            count = 0
            for reservation in expired_reservations:
                # Update flash sale reserved quantity
                flash_sale = reservation.flash_sale
                flash_sale.reserved_quantity -= reservation.quantity
                
                # Mark reservation as expired
                reservation.status = 'expired'
                count += 1
            
            self.db.commit()
            logger.info(f"Cleaned up {count} expired reservations")
            return count
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error cleaning up expired reservations: {e}")
            return 0
    
    def get_user_reservations(self, user_id: int) -> List[FlashSaleReservation]:
        """Get all reservations for a user"""
        return self.db.query(FlashSaleReservation).filter(
            FlashSaleReservation.userID == user_id,
            FlashSaleReservation._status.in_(['reserved', 'confirmed'])
        ).all()
    
    def get_flash_sale_discount_price(self, product_id: int) -> Optional[float]:
        """Get the flash sale discount price for a product if available"""
        flash_sale = self.db.query(FlashSale).filter(
            FlashSale.productID == product_id,
            FlashSale._status == 'active'
        ).first()
        
        if flash_sale and flash_sale.is_active():
            product = flash_sale.product
            original_price = float(product.price)
            discount_amount = original_price * (float(flash_sale.discount_percent) / 100)
            return original_price - discount_amount
        
        return None
