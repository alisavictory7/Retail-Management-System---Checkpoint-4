# src/main.py
import logging
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    g,
    abort,
)
from sqlalchemy import not_, desc
from werkzeug.security import generate_password_hash, check_password_hash

from src.config import Config
from src.database import get_db, close_db, engine
from src.models import Product, User, Sale, SaleItem, Payment, Cash, Card, FailedPaymentLog, Base, FlashSale, FlashSaleReservation, ReturnRequest
from src.tactics.manager import QualityTacticsManager
from src.blueprints.returns import returns_bp
from src.observability import (
    configure_logging,
    increment_counter,
    observe_latency,
    record_event,
    get_metrics_snapshot,
    check_database_health,
)
from src.observability.business_metrics import (
    compute_orders_metrics,
    compute_refund_metrics,
    compute_rma_summary,
    generate_quarter_windows,
    select_quarter_window,
)
from src.observability.logging_config import ensure_request_id

# Checkpoint 4: Import new services
from src.services.history_service import HistoryService
from src.services.low_stock_alert_service import LowStockAlertService
from src.services.notification_service import NotificationService
from src.services.flash_sale_service import FlashSaleService
from src.services.partner_catalog_service import PartnerCatalogService

app = Flask(__name__, template_folder='../templates', static_folder='../static')
Config.configure_app(app)
configure_logging(app)
app.register_blueprint(returns_bp)

logger = logging.getLogger(__name__)

_QUALITY_TACTICS_CONFIG = {
    'throttling': {
        'max_rps': Config.THROTTLING_MAX_RPS,
        'window_size': Config.THROTTLING_WINDOW_SECONDS,
    },
    'queue': {'max_size': 1000},
    'concurrency': {'max_concurrent': 10, 'lock_timeout': 50},
    'monitoring': {'metrics_interval': 60},
    'usability': {},
}

# Initialize database tables
def init_database():
    """Initialize database tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.exception("Error initializing database: %s", e)

# Initialize database on startup
init_database()

# Initialize quality tactics manager
def get_quality_manager():
    """Get quality tactics manager instance"""
    db = get_db()
    return QualityTacticsManager(db, _QUALITY_TACTICS_CONFIG)

def is_admin_user() -> bool:
    user = getattr(g, "current_user", None)
    if user:
        return user.is_admin
    return False

@app.context_processor
def inject_nav_context():
    user = getattr(g, "current_user", None)
    
    # Checkpoint 4: Get notification count for the navbar badge
    notification_count = 0
    active_flash_sales = []
    if user:
        try:
            notification_service = NotificationService()
            notification_count = notification_service.get_unread_count(user.userID)
        except Exception:
            pass  # Fail silently if notification service unavailable
    # Active flash sale banner (visible to all)
    try:
        db = get_db()
        flash_service = FlashSaleService(db)
        active_flash_sales = flash_service.get_active_flash_sales()
    except Exception:
        active_flash_sales = []
    
    return {
        "current_user": user,
        "is_admin": is_admin_user(),
        "show_storefront_link": True,
        "notification_count": notification_count,
        "active_flash_sales": active_flash_sales,
    }

@app.before_request
def before_request_logging():
    g.current_user = None
    if 'user_id' in session:
        db = get_db()
        g.current_user = db.query(User).filter_by(userID=session['user_id']).first()
    g.request_started_at = time.perf_counter()
    g.request_id = ensure_request_id()
    increment_counter(
        "http_requests_total",
        labels={
            "method": request.method,
            "endpoint": request.endpoint or request.path,
        },
    )

@app.after_request
def after_request_logging(response):
    started = getattr(g, 'request_started_at', None)
    if started is not None:
        duration_ms = (time.perf_counter() - started) * 1000
        observe_latency(
            "http_request_latency_ms",
            duration_ms,
            labels={
                "method": request.method,
                "endpoint": request.endpoint or request.path,
                "status": str(response.status_code),
            },
        )
    if response.status_code >= 500:
        increment_counter(
            "http_errors_total",
            labels={
                "method": request.method,
                "endpoint": request.endpoint or request.path,
                "status": str(response.status_code),
            },
        )
        logger.error("Request finished with error status %s", response.status_code)
    else:
        logger.info("Request finished", extra={"status_code": response.status_code})
    return response

@app.teardown_appcontext
def teardown_db(exception):
    try:
        close_db(exception)
    except RuntimeError:
        # Handle case where we're outside of application context during tests
        pass

# --- Database-Backed Cart Functions ---

def get_or_create_cart_sale(user_id, db):
    """Get existing cart sale or create a new one for the user."""
    cart_sale = db.query(Sale).filter_by(userID=user_id).filter(Sale._status == 'cart').first()
    if not cart_sale:
        cart_sale = Sale()
        cart_sale.userID = user_id
        cart_sale._sale_date = datetime.now(timezone.utc)
        cart_sale._totalAmount = 0.0
        cart_sale._status = 'cart'
        db.add(cart_sale)
        db.commit()
        db.refresh(cart_sale)
    return cart_sale

def get_products_with_flash_sales(db):
    """Get all products enriched with flash sale information."""
    products = db.query(Product).all()
    
    # Get active flash sales
    flash_service = FlashSaleService(db)
    active_flash_sales = flash_service.get_active_flash_sales()
    
    # Create a map of product_id to flash sale for easy lookup
    flash_sale_map = {fs.productID: fs for fs in active_flash_sales}
    
    # Enrich products with flash sale info
    products_with_flash = []
    for product in products:
        product_dict = {
            'productID': product.productID,
            'name': product.name,
            'description': product.description,
            'price': float(product.price),
            'stock': product.stock,
            'has_flash_sale': product.productID in flash_sale_map
        }
        
        if product_dict['has_flash_sale']:
            flash_sale = flash_sale_map[product.productID]
            discount_percent = float(flash_sale.discount_percent)
            discounted_price = float(product.price) * (1 - discount_percent / 100)
            product_dict['flash_sale'] = {
                'title': flash_sale.title,
                'discount_percent': discount_percent,
                'discounted_price': discounted_price,
                'available_quantity': flash_sale.get_available_quantity()
            }
        
        products_with_flash.append(product_dict)
    
    return products_with_flash

def get_cart_items(user_id, db):
    """Get all items in the user's cart from database."""
    cart_sale = get_or_create_cart_sale(user_id, db)
    cart_items = []
    grand_total = 0.0
    
    # Initialize flash sale service to check for active flash sales
    flash_service = FlashSaleService(db)
    
    for sale_item in cart_sale.items:
        product = db.query(Product).filter_by(productID=sale_item.productID).first()
        if product:
            # Check if product has an active flash sale
            flash_sale_price = flash_service.get_flash_sale_discount_price(product.productID)
            
            if flash_sale_price is not None:
                # Apply flash sale discount
                discounted_unit_price = flash_sale_price
                is_flash_sale = True
            else:
                # Use regular product discount
                discounted_unit_price = product.get_discounted_unit_price()
                is_flash_sale = False
            
            # Calculate totals
            subtotal = discounted_unit_price * sale_item.quantity
            shipping_fee = product.get_shipping_fees(sale_item.quantity)
            import_duty = product.get_import_duty(sale_item.quantity)
            
            item_total = subtotal + shipping_fee + import_duty
            grand_total += item_total
            
            cart_items.append({
                'product_id': product.productID,
                'name': product.name,
                'quantity': sale_item.quantity,
                'original_price': float(product.price),
                'discounted_unit_price': discounted_unit_price,
                'subtotal': subtotal,
                'discount_applied': (float(product.price) - discounted_unit_price) * sale_item.quantity,
                'shipping_fee': shipping_fee,
                'import_duty': import_duty,
                'available_stock': product.stock,
                'is_flash_sale': is_flash_sale
            })
    
    return {
        'items': cart_items,
        'grand_total': grand_total,
        'sale_id': cart_sale.saleID
    }

def add_item_to_cart(user_id, product_id, quantity, db):
    """Add item to database-backed cart."""
    try:
        cart_sale = get_or_create_cart_sale(user_id, db)
        
        # Check if item already exists in cart
        existing_item = db.query(SaleItem).filter_by(
            saleID=cart_sale.saleID, 
            productID=product_id
        ).first()
        
        if existing_item:
            existing_item.quantity += quantity
        else:
            product = db.query(Product).filter_by(productID=product_id).first()
            if not product:
                return False, "Product not found"
            
            new_item = SaleItem()
            new_item.saleID = cart_sale.saleID
            new_item.productID = product_id
            new_item.quantity = quantity
            new_item._original_unit_price = float(product.price)
            new_item._discount_applied = 0.0
            new_item._final_unit_price = product.get_discounted_unit_price()
            new_item._shipping_fee_applied = 0.0
            new_item._import_duty_applied = 0.0
            new_item._subtotal = product.get_subtotal_for_quantity(quantity)
            db.add(new_item)
        
        db.commit()
        return True, "Item added to cart"
    except Exception as e:
        db.rollback()
        return False, f"Error adding item to cart: {str(e)}"

def update_cart_item_quantity(user_id, product_id, quantity, db):
    """Update quantity of item in database-backed cart."""
    cart_sale = get_or_create_cart_sale(user_id, db)
    
    if quantity <= 0:
        # Remove item from cart
        item = db.query(SaleItem).filter_by(
            saleID=cart_sale.saleID, 
            productID=product_id
        ).first()
        if item:
            db.delete(item)
    else:
        # Update quantity
        item = db.query(SaleItem).filter_by(
            saleID=cart_sale.saleID, 
            productID=product_id
        ).first()
        if item:
            product = db.query(Product).filter_by(productID=product_id).first()
            if product:
                item.quantity = quantity
                item.subtotal = product.get_subtotal_for_quantity(quantity)
    
    db.commit()
    return True, "Cart updated"

def clear_cart(user_id, db):
    """Clear all items from user's cart."""
    cart_sale = db.query(Sale).filter_by(userID=user_id).filter(Sale._status == 'cart').first()
    if cart_sale:
        # Delete all cart items
        db.query(SaleItem).filter_by(saleID=cart_sale.saleID).delete()
        # Delete the cart sale
        db.delete(cart_sale)
        db.commit()
    return True, "Cart cleared"

def _recalculate_cart_totals(cart, db):
    """
    Recalculates derived values for all items in the cart like subtotals and fees.
    This should be the single source of truth for cart calculations.
    """
    grand_total = 0
    for item in cart.get('items', []):
        product = db.query(Product).filter_by(productID=item['product_id']).first()
        if product:
            quantity = item.get('quantity', 0)
            # Ensure all calculated fields are re-evaluated and stored as floats
            item['discounted_unit_price'] = product.get_discounted_unit_price()
            item['subtotal'] = product.get_subtotal_for_quantity(quantity)
            item['discount_applied'] = (float(product.price) - item['discounted_unit_price']) * quantity
            item['shipping_fee'] = product.get_shipping_fees(quantity)
            item['import_duty'] = product.get_import_duty(quantity)
            item['available_stock'] = product.stock
            grand_total += item['subtotal'] + item['shipping_fee'] + item['import_duty']
    
    cart['grand_total'] = grand_total
    return cart

def recalculate_cart_totals(cart, db):
    # Public wrapper retained for compatibility
    return _recalculate_cart_totals(cart, db)

def _refresh_cart_after_payment_failure(cart, db):
    """
    After payment failure: completely refresh the cart by clearing it and re-adding
    all items with the same quantities the user had before.
    This simulates a page refresh and ensures the cart is exactly as the user intended.
    """
    # Step 1: Store the original cart items with their quantities
    original_items = cart.get('items', []).copy()
    
    # Step 2: Completely clear the cart (simulate page refresh)
    cart['items'] = []
    cart['grand_total'] = 0.0
    
    # Step 3: Re-add each item exactly as the user had it before
    for item in original_items:
        # Re-add the item with the exact same quantity and details
        cart['items'].append({
            'product_id': item['product_id'],
            'name': item['name'],
            'quantity': item['quantity'],  # Same quantity as before
            'original_price': item['original_price']
        })
    
    # Step 4: Recalculate totals for proper display
    cart = _recalculate_cart_totals(cart, db)
    
    return cart


@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    
    user = db.query(User).filter_by(userID=session['user_id']).first()
    
    if not user:
        session.clear()
        return redirect(url_for('login'))
    
    # Get products with flash sale information
    products_with_flash = get_products_with_flash_sales(db)
    
    # Get cart from database instead of session
    cart = get_cart_items(session['user_id'], db)
    
    # Note: Do not auto-adjust quantities; user decides how to resolve stock issues
    cart_update_message = None

    # Get recent completed sales (exclude cart sales)
    recent_sales = db.query(Sale).filter_by(userID=session['user_id']).filter(Sale._status != 'cart').order_by(desc(Sale._sale_date)).limit(5).all()
    username = user.username
    
    return render_template('index.html', products=products_with_flash, cart=cart, username=username, recent_sales=recent_sales, cart_update_message=cart_update_message)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        requested_role = request.form.get('role', 'customer')
        
        db = get_db()
        if db.query(User).filter_by(username=username).first():
            return render_template('register.html', error='Username already exists.', show_storefront_link=False)
        if db.query(User).filter_by(email=email).first():
            return render_template('register.html', error='Email already registered.', show_storefront_link=False)

        role = 'customer'
        if requested_role == 'admin':
            if request.form.get('super_admin_token') != Config.SUPER_ADMIN_TOKEN:
                    return render_template('register.html', error='Invalid super admin token.', show_storefront_link=False)
            role = 'admin'

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, passwordHash=hashed_password, role=role)
        db.add(new_user)
        db.commit()
        return redirect(url_for('login'))
        
    return render_template('register.html', super_admin_token_required=Config.SUPER_ADMIN_TOKEN, show_storefront_link=False)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        user = db.query(User).filter_by(username=username).first()
        if user and check_password_hash(user.passwordHash, password):
            session['user_id'] = user.userID
            # Preserve existing cart or initialize empty cart if none exists
            if 'cart' not in session:
                session['cart'] = {'items': [], 'grand_total': 0.0}
            return redirect(url_for('index'))
        return render_template('login.html', error='Invalid username or password.', show_storefront_link=False)
    return render_template('login.html', show_storefront_link=False)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'user_id' not in session: return jsonify({'error': 'User not logged in.'}), 401
    
    db = get_db()
    
    try:
        if 'product_id' not in request.form or not request.form['product_id']:
            return jsonify({'error': 'Product ID is required.'}), 400
        product_id = int(request.form['product_id'])
        quantity = int(request.form.get('quantity', 1))
    except (ValueError, TypeError, KeyError):
        return jsonify({'error': 'Invalid or missing product data.'}), 400

    product = db.query(Product).filter_by(productID=product_id).first()
    if not product: return jsonify({'error': 'Product not found.'}), 404
    if product.stock < 1: return jsonify({'error': 'Product is out of stock.'}), 400
    
    # Check if adding this quantity would exceed stock
    cart_sale = get_or_create_cart_sale(session['user_id'], db)
    existing_item = db.query(SaleItem).filter_by(
        saleID=cart_sale.saleID, 
        productID=product_id
    ).first()
    
    current_quantity = existing_item.quantity if existing_item else 0
    new_quantity = current_quantity + quantity
    
    if new_quantity > product.stock:
        return jsonify({'error': f'Not enough stock. Only {product.stock} available.'}), 400
    
    # Add item to database cart
    success, message = add_item_to_cart(session['user_id'], product_id, quantity, db)
    if not success:
        return jsonify({'error': message}), 400
    
    # Get updated cart from database
    cart = get_cart_items(session['user_id'], db)
    
    return jsonify({'message': 'Item added to cart.', 'cart': cart, 'product_name': product.name})

@app.route('/set_cart_quantity', methods=['POST'])
def set_cart_quantity():
    if 'user_id' not in session: return jsonify({'error': 'User not logged in.'}), 401
    
    db = get_db()
    try:
        product_id = int(request.form['product_id'])
        quantity = int(request.form.get('quantity', 0))
    except (ValueError, TypeError, KeyError):
        return jsonify({'error': 'Invalid or missing product data.'}), 400

    product = db.query(Product).filter_by(productID=product_id).first()
    if not product: return jsonify({'error': 'Product not found.'}), 404
    
    if quantity > product.stock:
        return jsonify({
            'error': f'Only {product.stock} in stock.',
            'available': product.stock,
            'product_id': product_id,
            'product_name': product.name
        }), 409

    # Update quantity in database cart
    success, message = update_cart_item_quantity(session['user_id'], product_id, quantity, db)
    if not success:
        return jsonify({'error': message}), 400
    
    # Get updated cart from database
    cart = get_cart_items(session['user_id'], db)
    
    return jsonify({
        'message': 'Cart updated.', 
        'cart': cart, 
        'quantity_adjusted': False, 
        'new_quantity': quantity
    })

@app.route('/checkout', methods=['POST'])
def checkout():
    if 'user_id' not in session:
        return "User not logged in.", 401

    db = get_db()
    quality_manager = get_quality_manager()
    order_start = time.perf_counter()
    
    # Get cart from database instead of session
    cart = get_cart_items(session['user_id'], db)
    if not cart.get('items'):
        # Return to index with error message instead of silent redirect
        user = db.query(User).filter_by(userID=session['user_id']).first()
        products = get_products_with_flash_sales(db)
        recent_sales = db.query(Sale).filter_by(userID=session['user_id']).filter(Sale._status != 'cart').order_by(desc(Sale._sale_date)).limit(5).all()
        msg = "Cannot complete purchase: Your cart is empty. Please add items to your cart first."
        return render_template('index.html', products=products, cart=cart, username=user.username, recent_sales=recent_sales, cart_update_message=msg), 400
    
    # Check throttling (Performance tactic)
    request_data = {
        'user_id': session['user_id'],
        'cart_size': len(cart.get('items', [])),
        'total_amount': cart.get('grand_total', 0)
    }
    throttled, throttle_msg = quality_manager.check_throttling(request_data)
    if not throttled:
        user = db.query(User).filter_by(userID=session['user_id']).first()
        products = get_products_with_flash_sales(db)
        recent_sales = db.query(Sale).filter_by(userID=session['user_id']).filter(Sale._status != 'cart').order_by(desc(Sale._sale_date)).limit(5).all()
        msg = f"System is busy. Please try again in a moment. ({throttle_msg})"
        return render_template('index.html', products=products, cart=cart, username=user.username, recent_sales=recent_sales, cart_update_message=msg), 429

    try:
        increment_counter("orders_submitted_total", labels={"source": "checkout"})
        product_ids = [item['product_id'] for item in cart['items']]
        products_in_cart = db.query(Product).filter(Product.productID.in_(product_ids)).with_for_update().all()
        
        product_map = {p.productID: p for p in products_in_cart}

        for item in cart['items']:
            product = product_map.get(item['product_id'])
            if not product or product.stock < item['quantity']:
                # Rollback and return user to cart with clear message
                db.rollback()
                # Get fresh cart from database
                cart = get_cart_items(session['user_id'], db)
                user = db.query(User).filter_by(userID=session['user_id']).first()
                products = get_products_with_flash_sales(db)
                recent_sales = db.query(Sale).filter_by(userID=session['user_id']).filter(Sale._status != 'cart').order_by(desc(Sale._sale_date)).limit(5).all()
                msg = f"Checkout failed: stock for '{item['name']}' changed: Only {product.stock if product else 0} left. All stock levels updated and payment rolled back."
                return render_template('index.html', products=products, cart=cart, username=user.username, recent_sales=recent_sales, cart_update_message=msg), 409

        payment_method = request.form['payment_method']
        total_amount = cart['grand_total']

        # Convert the existing cart sale to a pending sale
        cart_sale = db.query(Sale).filter_by(userID=session['user_id']).filter(Sale._status == 'cart').first()
        if cart_sale:
            # Update the existing cart sale to pending status
            cart_sale._status = 'pending'
            cart_sale._totalAmount = total_amount
            cart_sale._sale_date = datetime.now(timezone.utc)
            new_sale = cart_sale
        else:
            # Create new sale if no cart exists (shouldn't happen)
            new_sale = Sale()
            new_sale.userID = session['user_id']
            new_sale._sale_date = datetime.now(timezone.utc)
            new_sale._totalAmount = total_amount
            new_sale._status = 'pending'
            db.add(new_sale)
        db.flush()

        payment = None
        if payment_method == 'Cash':
            payment = Cash(saleID=new_sale.saleID, amount=total_amount, status='pending', cash_tendered=total_amount)
            payment.payment_type = 'cash'
        elif payment_method == 'Card':
            card_number = request.form.get('card_number', '').replace(' ', '').replace('-', '')
            card_exp_date = request.form.get('card_exp_date')
            # Basic server-side validation to avoid blank error pages
            def _render_validation_error(msg: str):
                # Convert the pending sale back to cart status to preserve items
                if new_sale:
                    new_sale._status = 'cart'
                    db.commit()
                
                # Get fresh cart from database
                cart_local = get_cart_items(session['user_id'], db)
                user_local = db.query(User).filter_by(userID=session['user_id']).first()
                products_local = get_products_with_flash_sales(db)
                recent_local = db.query(Sale).filter_by(userID=session['user_id']).filter(Sale._status != 'cart').order_by(desc(Sale._sale_date)).limit(5).all()
                return render_template('index.html', products=products_local, cart=cart_local, username=user_local.username, recent_sales=recent_local, cart_update_message=msg), 400

            if not card_number or not card_exp_date:
                db.rollback()
                return _render_validation_error('Card number and expiry date are required.')
            if not card_number.isdigit() or not (15 <= len(card_number) <= 19):
                db.rollback()
                return _render_validation_error('Invalid Card Number (must be 15-19 digits)')
            try:
                exp_month, exp_year = map(int, card_exp_date.split('/'))
                now = datetime.now(timezone.utc)
                if exp_month < 1 or exp_month > 12:
                    raise ValueError
                if (exp_year < now.year) or (exp_year == now.year and exp_month < now.month):
                    db.rollback()
                    return _render_validation_error('Card Expired')
            except Exception:
                db.rollback()
                return _render_validation_error('Invalid Expiry Date Format')
            payment = Card(
                saleID=new_sale.saleID, amount=total_amount, status='pending',
                card_number=card_number,
                card_type=request.form.get('card_type', 'Unknown'), 
                card_exp_date=card_exp_date
            )
            payment.payment_type = 'card'
        
        if payment: db.add(payment)
        
        is_authorized, reason = payment.authorized() if payment else (False, "Invalid payment method")
        # Simulate external payment processor behavior: 50% chance of decline for valid payments
        if is_authorized:
            if payment_method == 'Card' and random.random() < 0.5:
                is_authorized = False
                reason = 'Payment declined by processor'
            elif payment_method == 'Cash' and random.random() < 0.5:
                is_authorized = False
                reason = 'Cash handling error at terminal'
        
        if is_authorized:
            # Final check immediately before applying stock updates (guard against concurrent changes)
            conflict_item = None
            for item in cart['items']:
                product = product_map[item['product_id']]
                if product.stock < item['quantity']:
                    conflict_item = (product, item)
                    break

            if conflict_item is not None:
                # Roll back payment and sale, inform the user, and show cart for resolution
                db.rollback()
                # Convert the sale back to cart status
                cart_sale = db.query(Sale).filter_by(saleID=new_sale.saleID).first()
                if cart_sale:
                    cart_sale._status = 'cart'
                    db.commit()
                
                # Get fresh cart from database
                cart = get_cart_items(session['user_id'], db)
                user = db.query(User).filter_by(userID=session['user_id']).first()
                products = get_products_with_flash_sales(db)
                recent_sales = db.query(Sale).filter_by(userID=session['user_id']).filter(Sale._status != 'cart').order_by(desc(Sale._sale_date)).limit(5).all()
                product, item = conflict_item
                msg = f"Checkout failed: stock for '{product.name}' changed: Only {product.stock} left. All stock levels updated and payment rolled back."
                return render_template('index.html', products=products, cart=cart, username=user.username, recent_sales=recent_sales, cart_update_message=msg), 409
            new_sale._status = 'completed'
            payment._status = 'completed'
            
            # Clear the original cart items before creating new sale items
            # This prevents duplicate items from appearing in future carts
            original_cart_items = db.query(SaleItem).filter_by(saleID=new_sale.saleID).all()
            for old_item in original_cart_items:
                db.delete(old_item)
            
            # Initialize flash sale service to apply flash sale discounts
            flash_service = FlashSaleService(db)
            
            for item in cart['items']:
                product = product_map[item['product_id']]
                quantity = item['quantity']

                # Check if product has an active flash sale
                flash_sale_price = flash_service.get_flash_sale_discount_price(product.productID)
                
                if flash_sale_price is not None:
                    # Apply flash sale discount
                    final_unit_price = flash_sale_price
                else:
                    # Use regular product discount
                    final_unit_price = product.get_discounted_unit_price()
                
                subtotal = final_unit_price * quantity
                discount_applied = (float(product.price) - final_unit_price) * quantity
                shipping_fee_applied = product.get_shipping_fees(quantity)
                import_duty_applied = product.get_import_duty(quantity)
                
                product.stock -= quantity

                sale_item = SaleItem()
                sale_item.saleID = new_sale.saleID
                sale_item.productID = product.productID
                sale_item.quantity = quantity
                sale_item._original_unit_price = float(product.price)
                sale_item._final_unit_price = final_unit_price
                sale_item._discount_applied = discount_applied
                sale_item._shipping_fee_applied = shipping_fee_applied
                sale_item._import_duty_applied = import_duty_applied
                sale_item._subtotal = subtotal
                db.add(sale_item)

            db.commit()
            session['cart'] = {'items': [], 'grand_total': 0.0}
            # Reload sale with items for receipt
            sale_with_items = db.query(Sale).filter_by(saleID=new_sale.saleID).first()
            for item in sale_with_items.items:
                _ = item.product

            # Compute invoice breakdown
            items_total = sum(float(i.subtotal) for i in sale_with_items.items)
            shipping_total = sum(float(i.shipping_fee_applied) for i in sale_with_items.items)
            tax_total = sum(float(i.import_duty_applied) for i in sale_with_items.items)
            discount_total = sum(float(i.discount_applied) for i in sale_with_items.items)
            grand_total = float(sale_with_items.totalAmount)

            # Payment details
            payment_row = db.query(Payment).filter_by(saleID=sale_with_items.saleID).order_by(desc(Payment.paymentID)).first()
            payment_method = None
            payment_ref = None
            masked_details = None
            if payment_row:
                payment_method = payment_row.payment_type or payment_row.type
                payment_ref = f"PAY-{payment_row.paymentID}"
                if getattr(payment_row, 'card_number', None):
                    last4 = str(payment_row.card_number)[-4:]
                    masked_details = f"{payment_row.card_type or 'Card'} •••• {last4}"

            duration_ms = (time.perf_counter() - order_start) * 1000
            increment_counter("orders_accepted_total", labels={"mode": "completed"})
            observe_latency("order_processing_latency_ms", duration_ms, labels={"mode": "completed"})
            record_event(
                "order_completed",
                {
                    "sale_id": sale_with_items.saleID,
                    "user_id": session['user_id'],
                    "latency_ms": duration_ms,
                    "amount": grand_total,
                },
            )
            user = db.query(User).filter_by(userID=session['user_id']).first()
            return render_template(
                'receipt.html',
                sale=sale_with_items,
                username=user.username,
                items_total=items_total,
                shipping_total=shipping_total,
                tax_total=tax_total,
                discount_total=discount_total,
                grand_total=grand_total,
                payment_method=payment_method,
                payment_ref=payment_ref,
                masked_details=masked_details
            )
        else:
            # Payment not authorized: treat this as an upstream gateway issue and
            # apply graceful degradation by queuing the order instead of hard‑failing.
            quality_manager = get_quality_manager()
            order_data = {
                "sale_id": new_sale.saleID,
                "user_id": session['user_id'],
                "total_amount": float(total_amount),
                "priority": 0,
            }
            queued = False
            queue_message = ""
            try:
                queued, queue_message = quality_manager.queue_order_for_retry(order_data, session['user_id'])
            except Exception as qe:  # Fallback to legacy behavior if queuing fails
                queued = False
                queue_message = str(qe)

            if queued:
                # Order has been accepted into the retry queue: count as accepted and
                # keep the sale in a pending state instead of failing it outright.
                new_sale._status = 'pending'
                db.commit()

                # Clear the in‑session cart so the user sees a fresh state.
                session['cart'] = {'items': [], 'grand_total': 0.0}

                user = db.query(User).filter_by(userID=session['user_id']).first()
                products = get_products_with_flash_sales(db)
                recent_sales = (
                    db.query(Sale)
                    .filter_by(userID=session['user_id'])
                    .filter(Sale._status != 'cart')
                    .order_by(desc(Sale._sale_date))
                    .limit(5)
                    .all()
                )
                msg = (
                    "Payment gateway is currently unavailable. "
                    "Your order has been queued for retry and will be processed asynchronously. "
                    f"Details: {queue_message or reason}"
                )
                return (
                    render_template(
                        'index.html',
                        products=products,
                        cart=get_cart_items(session['user_id'], db),
                        username=user.username,
                        recent_sales=recent_sales,
                        cart_update_message=msg,
                    ),
                    200,
                )

            # If we reach here, graceful degradation failed; fall back to the original
            # behavior of marking the sale as failed and returning a 400 to the user.
            new_sale._status = 'failed'
            payment._status = 'failed'

            log = FailedPaymentLog(
                userID=session['user_id'],
                attempt_date=datetime.now(timezone.utc),
                amount=total_amount,
                payment_method=payment_method,
                reason=reason,
            )
            db.add(log)
            db.commit()

            new_sale._status = 'cart'
            db.commit()

            cart = get_cart_items(session['user_id'], db)
            user = db.query(User).filter_by(userID=session['user_id']).first()
            products = get_products_with_flash_sales(db)
            recent_sales = (
                db.query(Sale)
                .filter_by(userID=session['user_id'])
                .filter(Sale._status != 'cart')
                .order_by(desc(Sale._sale_date))
                .limit(5)
                .all()
            )
            msg = (
                f"Payment failed: {reason}. Failed payment attempt #{log.logID}. "
                "Please use a different payment method or cancel your sale."
            )
            return (
                render_template(
                    'index.html',
                    products=products,
                    cart=cart,
                    username=user.username,
                    recent_sales=recent_sales,
                    cart_update_message=msg,
                ),
                400,
            )

    except Exception as e:
        db.rollback()
        import logging
        logging.error(f"Checkout error: {e}", exc_info=True)
        # For debugging: show the actual error in the browser
        return f"Checkout error: {e}", 500


@app.route('/cancel_sale', methods=['POST'])
def cancel_sale():
    if 'user_id' not in session:
        return "User not logged in.", 401
    
    db = get_db()
    success, message = clear_cart(session['user_id'], db)
    if success:
        return redirect(url_for('index'))
    else:
        return f"Error clearing cart: {message}", 500

# ==============================================
# CHECKPOINT 2: NEW API ENDPOINTS FOR QUALITY TACTICS
# ==============================================

@app.route('/api/flash-sales', methods=['GET'])
def get_flash_sales():
    """Get active flash sales"""
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401
    
    db = get_db()
    quality_manager = get_quality_manager()
    
    # Check if flash sale feature is enabled
    feature_enabled, feature_msg = quality_manager.is_feature_enabled("flash_sale_enabled", session['user_id'])
    if not feature_enabled:
        return jsonify({'error': 'Flash sale feature disabled', 'message': feature_msg}), 403
    
    try:
        from src.services.flash_sale_service import FlashSaleService
        flash_sale_service = FlashSaleService(db)
        active_sales = flash_sale_service.get_active_flash_sales()
        
        sales_data = []
        for sale in active_sales:
            sales_data.append({
                'id': sale.flashSaleID,
                'product_id': sale.productID,
                'product_name': sale.product.name,
                'original_price': float(sale.product.price),
                'discount_percent': float(sale.discount_percent),
                'discounted_price': sale.product.get_discounted_unit_price(),
                'max_quantity': sale.max_quantity,
                'available_quantity': sale.get_available_quantity(),
                'end_time': sale.end_time.isoformat()
            })
        
        return jsonify({'flash_sales': sales_data})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/flash-sales/<int:sale_id>/reserve', methods=['POST'])
def reserve_flash_sale(sale_id):
    """Reserve items in a flash sale"""
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401
    
    db = get_db()
    quality_manager = get_quality_manager()
    
    try:
        quantity = int(request.json.get('quantity', 1))
        
        from src.services.flash_sale_service import FlashSaleService
        flash_sale_service = FlashSaleService(db)
        
        success, message, reservation = flash_sale_service.reserve_flash_sale_item(
            sale_id, session['user_id'], quantity
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'reservation_id': reservation.reservationID,
                'expires_at': reservation.expires_at.isoformat()
            })
        else:
            return jsonify({'error': message}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/partner/ingest', methods=['POST'])
def partner_catalog_ingest():
    """
    Ingest partner catalog data via API.
    
    This endpoint implements the Partner (VAR) Catalog Ingest feature:
    - ADR 6 (S.1): Authenticate Actors - API key validation
    - ADR 7 (S.2): Validate Input - SQL injection prevention
    - ADR 9 (M.1): Adapter Pattern - CSV/JSON format support
    - ADR 16 (I.2): Publish-Subscribe - Event broadcasting
    
    Headers:
        X-API-Key: Partner API key for authentication
        Content-Type: application/json or text/csv
    
    Body:
        CSV or JSON product feed data
    """
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return jsonify({'error': 'API key required', 'code': 'AUTH_REQUIRED'}), 401
    
    db = get_db()
    partner_service = PartnerCatalogService(db)
    
    try:
        # Authenticate partner (ADR 6: Authenticate Actors)
        auth_success, auth_message, partner_id = partner_service.authenticate_api_key(api_key)
        if not auth_success:
            return jsonify({'error': auth_message, 'code': 'AUTH_FAILED'}), 401
        
        # Get request data
        data = request.get_data(as_text=True)
        if not data:
            return jsonify({'error': 'No data provided', 'code': 'EMPTY_PAYLOAD'}), 400
        
        # Determine format from Content-Type header
        content_type = request.headers.get('Content-Type', '').lower()
        
        # Process based on format (ADR 9: Adapter Pattern)
        if 'json' in content_type:
            success, message, count = partner_service.ingest_json_file(partner_id, data)
        elif 'csv' in content_type or 'text/plain' in content_type:
            success, message, count = partner_service.ingest_csv_file(partner_id, data)
        else:
            # Try to auto-detect format
            if data.strip().startswith('{') or data.strip().startswith('['):
                success, message, count = partner_service.ingest_json_file(partner_id, data)
            else:
                success, message, count = partner_service.ingest_csv_file(partner_id, data)
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'products_processed': count,
                'partner_id': partner_id
            })
        else:
            return jsonify({
                'success': False,
                'error': message,
                'code': 'PROCESSING_FAILED'
            }), 400
            
    except Exception as e:
        logger.error(f"Partner catalog ingest error: {e}")
        return jsonify({'error': str(e), 'code': 'INTERNAL_ERROR'}), 500

@app.route('/api/system/health', methods=['GET'])
def system_health():
    """Get system health status"""
    try:
        quality_manager = get_quality_manager()
        health = quality_manager.get_system_health()
        return jsonify(health)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    db_status = check_database_health()
    overall = "UP" if db_status.get("status") == "UP" else "DEGRADED"
    status_code = 200 if overall == "UP" else 503
    return jsonify({
        "status": overall,
        "components": {
            "database": db_status
        }
    }), status_code

@app.route('/admin/metrics', methods=['GET'])
def admin_metrics():
    if not is_admin_user():
        abort(403)
    return jsonify(get_metrics_snapshot())


# ---------------------------------------------
# Quality Scenario Monitoring Routes
# ---------------------------------------------
@app.route('/admin/quality-monitoring', methods=['GET'])
def quality_scenario_monitoring():
    """Interactive Quality Scenario Monitoring page for A.1 and P.1 testing"""
    if not is_admin_user():
        abort(403)
    
    metrics = get_metrics_snapshot()
    scenario_metrics = _calculate_quality_scenario_metrics(metrics)
    
    return render_template(
        'quality_scenario_monitoring.html',
        scenario_metrics=scenario_metrics
    )


@app.route('/admin/quality-monitoring/test/availability', methods=['POST'])
def test_availability_scenario():
    """Test A.1 Availability scenario with configurable parameters"""
    if not is_admin_user():
        abort(403)
    
    try:
        data = request.get_json() or {}
        failure_rate = data.get('failure_rate', 0)  # 0-100%
        threshold = data.get('threshold', 5)  # Circuit breaker threshold
        timeout = data.get('timeout', 60)  # Recovery timeout seconds
        
        db = get_db()
        quality_manager = get_quality_manager()
        
        # Simulate requests with configured failure rate
        total_requests = 100
        successful_requests = 0
        circuit_breaker_trips = 0
        failures_recorded = 0
        
        import random
        
        def simulated_payment():
            nonlocal failures_recorded
            if random.randint(1, 100) <= failure_rate:
                failures_recorded += 1
                raise Exception("Simulated payment failure")
            return {"status": "success", "transaction_id": str(uuid4())}
        
        for i in range(total_requests):
            try:
                # Update circuit breaker config dynamically
                quality_manager.circuit_breaker.failure_threshold = threshold
                quality_manager.circuit_breaker.timeout_duration = timeout
                
                success, result = quality_manager.execute_with_circuit_breaker(simulated_payment)
                if success:
                    successful_requests += 1
                else:
                    # Check if circuit breaker is open
                    if "temporarily unavailable" in str(result).lower():
                        circuit_breaker_trips += 1
            except Exception as e:
                logger.warning(f"Availability test iteration {i} failed: {e}")
        
        success_rate = (successful_requests / total_requests) * 100 if total_requests > 0 else 0
        
        # Calculate simulated MTTR based on failure rate and timeout
        mttr_seconds = (failure_rate / 100) * timeout if failure_rate > 0 else 0
        mttr_display = _format_duration(mttr_seconds) if mttr_seconds > 0 else "No outages"
        
        # Determine if scenario is fulfilled (>=99% success, MTTR < 5 min)
        fulfilled = success_rate >= 99.0 and mttr_seconds < 300
        
        # Determine status: Fulfilled, Failed, or In Progress
        if fulfilled:
            status = "Fulfilled"
        elif success_rate < 99.0 or mttr_seconds >= 300:
            status = "Failed"
        else:
            status = "In Progress"
        
        # Record metrics
        increment_counter("quality_scenario_tests_total", labels={"scenario": "A.1"})
        record_event("availability_test_completed", {
            "failure_rate": failure_rate,
            "threshold": threshold,
            "timeout": timeout,
            "success_rate": success_rate,
            "circuit_breaker_trips": circuit_breaker_trips
        })
        
        return jsonify({
            "success": True,
            "success_rate": success_rate,
            "mttr": mttr_display,
            "mttr_seconds": mttr_seconds,
            "circuit_breaker_trips": circuit_breaker_trips,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failures_recorded": failures_recorded,
            "fulfilled": fulfilled,
            "status": status
        })
        
    except Exception as e:
        logger.exception("Availability test failed")
        return jsonify({
            "success": False, 
            "error": str(e),
            "status": "Blocked"
        }), 500


@app.route('/admin/quality-monitoring/test/performance', methods=['POST'])
def test_performance_scenario():
    """Test P.1 Performance scenario with configurable parameters"""
    if not is_admin_user():
        abort(403)
    
    try:
        data = request.get_json() or {}
        simulated_load = data.get('simulated_load', 100)  # Requests per second
        throttle_limit = data.get('throttle_limit', 100)  # Max RPS allowed
        processing_time = data.get('processing_time', 50)  # ms per request
        
        quality_manager = get_quality_manager()
        
        # Update throttling config
        quality_manager.throttling.max_requests_per_second = throttle_limit
        
        # Simulate requests and measure latency
        num_requests = min(simulated_load, 500)  # Cap at 500 for safety
        latencies = []
        requests_processed = 0
        requests_throttled = 0
        
        for i in range(num_requests):
            start_time = time.perf_counter()
            
            # Check throttling
            allowed, msg = quality_manager.check_throttling({'request_id': i})
            
            if allowed:
                # Simulate processing time with some variance
                import random
                actual_processing = processing_time * (0.5 + random.random())
                time.sleep(actual_processing / 1000)  # Convert ms to seconds
                requests_processed += 1
                
                latency_ms = (time.perf_counter() - start_time) * 1000
                latencies.append(latency_ms)
                
                # Record latency metric
                observe_latency("order_processing_latency_ms", latency_ms, labels={"mode": "test"})
            else:
                requests_throttled += 1
        
        # Calculate P95 latency
        if latencies:
            latencies.sort()
            p95_index = int(len(latencies) * 0.95)
            p95_latency = latencies[p95_index] if p95_index < len(latencies) else latencies[-1]
        else:
            p95_latency = 0
        
        # Determine if scenario is fulfilled (P95 <= 500ms)
        fulfilled = p95_latency <= 500
        
        # Determine status: Fulfilled, Failed, or In Progress
        if fulfilled:
            status = "Fulfilled"
        elif p95_latency > 500:
            status = "Failed"
        else:
            status = "In Progress"
        
        # Record metrics
        increment_counter("quality_scenario_tests_total", labels={"scenario": "P.1"})
        record_event("performance_test_completed", {
            "simulated_load": simulated_load,
            "throttle_limit": throttle_limit,
            "processing_time": processing_time,
            "p95_latency": p95_latency,
            "requests_processed": requests_processed,
            "requests_throttled": requests_throttled
        })
        
        return jsonify({
            "success": True,
            "p95_latency": p95_latency,
            "avg_latency": sum(latencies) / len(latencies) if latencies else 0,
            "min_latency": min(latencies) if latencies else 0,
            "max_latency": max(latencies) if latencies else 0,
            "requests_processed": requests_processed,
            "requests_throttled": requests_throttled,
            "total_requests": num_requests,
            "fulfilled": fulfilled,
            "status": status
        })
        
    except Exception as e:
        logger.exception("Performance test failed")
        return jsonify({
            "success": False, 
            "error": str(e),
            "status": "Blocked"
        }), 500


@app.route('/admin/quality-monitoring/reset/availability', methods=['POST'])
def reset_availability_metrics():
    """Reset availability circuit breaker and metrics"""
    if not is_admin_user():
        abort(403)
    
    try:
        quality_manager = get_quality_manager()
        
        # Reset circuit breaker state
        quality_manager.circuit_breaker.reset()
        
        record_event("availability_metrics_reset", {"reset_by": g.current_user.username if g.current_user else "admin"})
        
        return jsonify({"success": True, "message": "Availability metrics reset successfully"})
        
    except Exception as e:
        logger.exception("Failed to reset availability metrics")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/quality-monitoring/reset/performance', methods=['POST'])
def reset_performance_metrics():
    """Reset performance throttling state"""
    if not is_admin_user():
        abort(403)
    
    try:
        quality_manager = get_quality_manager()
        
        # Reset throttling state
        with quality_manager.throttling.lock:
            quality_manager.throttling.request_times.clear()
        
        record_event("performance_metrics_reset", {"reset_by": g.current_user.username if g.current_user else "admin"})
        
        return jsonify({"success": True, "message": "Performance metrics reset successfully"})
        
    except Exception as e:
        logger.exception("Failed to reset performance metrics")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/dashboard', methods=['GET'])
def admin_dashboard():
    if not is_admin_user():
        abort(403)
    db = get_db()
    quarter_windows = generate_quarter_windows()
    selected_window = select_quarter_window(quarter_windows, request.args.get('quarter'))

    orders_metrics = compute_orders_metrics(db, selected_window)
    refund_metrics = compute_refund_metrics(db, selected_window)
    rma_overview = compute_rma_summary(db, selected_window)
    orders_total = orders_metrics["total"] or 0
    rma_rate = (rma_overview["count"] / orders_total * 100) if orders_total else 0.0
    rma_metrics = {
        "count": rma_overview["count"],
        "rate": rma_rate,
        "cycle_hours": rma_overview["avg_cycle_hours"],
    }

    metrics = get_metrics_snapshot()
    db_status = check_database_health()
    error_rate = _calculate_error_rate(metrics)
    scenario_metrics = _calculate_quality_scenario_metrics(metrics)
    
    # Checkpoint 4: Get low stock alerts and notify admins
    low_stock_service = LowStockAlertService(db)
    low_stock_summary = low_stock_service.get_alert_summary()
    
    # Notify admins of any new low stock items
    low_stock_service.notify_admins_of_low_stock()
    
    # Get additional data for dashboard portal cards
    users = db.query(User).all()
    products = db.query(Product).all()
    flash_service = FlashSaleService(db)
    flash_sales = flash_service.get_active_flash_sales()
    
    # Get return request counts by status (accurate metrics for Returns Portal)
    pending_returns = db.query(ReturnRequest).filter(
        ReturnRequest.status == 'PENDING_AUTHORIZATION'
    ).count()
    in_transit_returns = db.query(ReturnRequest).filter_by(status='IN_TRANSIT').count()
    inspection_returns = db.query(ReturnRequest).filter_by(status='UNDER_INSPECTION').count()
    
    user = db.query(User).filter_by(userID=session.get('user_id')).first()
    
    return render_template(
        'admin_dashboard.html',
        metrics=metrics,
        db_status=db_status,
        quarter_windows=quarter_windows,
        selected_window=selected_window,
        orders_metrics=orders_metrics,
        refund_metrics=refund_metrics,
        rma_metrics=rma_metrics,
        scenario_metrics=scenario_metrics,
        error_rate=error_rate,
        low_stock_summary=low_stock_summary,
        users=users,
        products=products,
        flash_sales=flash_sales,
        pending_returns=pending_returns,
        in_transit_returns=in_transit_returns,
        inspection_returns=inspection_returns,
        username=user.username if user else 'Admin',
    )


def _calculate_error_rate(snapshot: dict) -> float:
    counters = snapshot.get("counters", {})
    total_requests = sum(entry["value"] for entry in counters.get("http_requests_total", []))
    total_errors = sum(entry["value"] for entry in counters.get("http_errors_total", []))
    if not total_requests:
        return 0.0
    return round((total_errors / total_requests) * 100, 2)


def _sum_counter(snapshot: dict, name: str) -> float:
    counters = snapshot.get("counters", {})
    return sum(entry["value"] for entry in counters.get(name, []))


def _calculate_quality_scenario_metrics(snapshot: dict) -> Dict[str, Any]:
    submitted_raw = _sum_counter(snapshot, "orders_submitted_total")
    accepted_raw = _sum_counter(snapshot, "orders_accepted_total")
    submitted = int(submitted_raw)
    accepted = int(accepted_raw)
    success_rate = (accepted / submitted * 100) if submitted else None
    success_rate_fulfilled = success_rate is not None and success_rate >= 99.0

    outage_events = _sum_counter(snapshot, "payment_circuit_open_events_total")
    had_outage = outage_events > 0

    mttr_hist = snapshot.get("histograms", {}).get("payment_circuit_mttr_seconds", [])
    mttr_seconds = mttr_hist[0]["stats"].get("avg") if mttr_hist else None
    if mttr_seconds is None:
        # If we've never opened the circuit breaker, we treat MTTR as implicitly
        # satisfied for the high‑availability case (no outages to repair).
        mttr_fulfilled = not had_outage
    else:
        mttr_fulfilled = mttr_seconds < 300

    latency_hist = snapshot.get("histograms", {}).get("order_processing_latency_ms", [])
    p95_values = [
        entry["stats"].get("p95")
        for entry in latency_hist
        if entry["stats"].get("p95") is not None
    ]
    latency_p95 = max(p95_values) if p95_values else None
    latency_fulfilled = latency_p95 is not None and latency_p95 <= 500

    scenario_a1 = {
        "submitted": submitted,
        "accepted": accepted,
        "success_rate": success_rate,
        "success_rate_fulfilled": success_rate_fulfilled,
        "mttr_seconds": mttr_seconds,
        "mttr_display": _format_duration(mttr_seconds) if had_outage else ("No outages" if mttr_seconds is None else _format_duration(mttr_seconds)),
        "mttr_fulfilled": mttr_fulfilled,
        "fulfilled": (success_rate_fulfilled and mttr_fulfilled),
    }

    scenario_p1 = {
        "latency_p95": latency_p95,
        "fulfilled": latency_fulfilled,
    }

    return {"A1": scenario_a1, "P1": scenario_p1}


def _format_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "N/A"
    total_seconds = int(max(0, round(seconds)))
    minutes, secs = divmod(total_seconds, 60)
    return f"{minutes}m {secs:02d}s"

@app.route('/admin/users', methods=['GET', 'POST'])
def admin_users():
    if not is_admin_user():
        abort(403)
    db = get_db()
    message = None
    if request.method == 'POST':
        try:
            user_id = int(request.form['user_id'])
        except (TypeError, ValueError):
            abort(400)
        new_role = request.form.get('role', 'customer')
        if new_role not in {'customer', 'admin'}:
            new_role = 'customer'
        user = db.query(User).filter_by(userID=user_id).first()
        if user and user.username != Config.SUPER_ADMIN_USERNAME:
            user.role = new_role
            db.commit()
            message = f"Updated {user.username} to {new_role}"
    users = db.query(User).order_by(User.userID).all()
    return render_template(
        'admin_users.html',
        users=users,
        message=message,
        super_admin_username=Config.SUPER_ADMIN_USERNAME,
    )


# ---------------------------------------------
# Admin: Product Management
# ---------------------------------------------
@app.route('/admin/products', methods=['GET', 'POST'])
def admin_products():
    """Allow admins to add, edit, and delete products."""
    if not is_admin_user():
        abort(403)

    db = get_db()
    message = None
    error = None

    if request.method == 'POST':
        action = request.form.get('action', '').lower()
        try:
            if action == 'create':
                name = (request.form.get('name') or '').strip()
                description = (request.form.get('description') or '').strip()
                price = float(request.form.get('price', '0'))
                stock = int(request.form.get('stock', '0'))
                if not name:
                    raise ValueError("Product name is required.")
                if price < 0:
                    raise ValueError("Price must be non-negative.")
                if stock < 0:
                    raise ValueError("Stock must be non-negative.")
                product = Product(name=name, description=description, price=price, stock=stock)
                db.add(product)
                db.commit()
                message = f"Product '{name}' created."
            elif action == 'update':
                product_id = int(request.form.get('product_id', '0'))
                product = db.query(Product).filter_by(productID=product_id).first()
                if not product:
                    raise ValueError("Product not found.")
                name = (request.form.get('name') or product.name).strip()
                description = (request.form.get('description') or '').strip()
                price = float(request.form.get('price', product.price))
                stock = int(request.form.get('stock', product.stock))
                if not name:
                    raise ValueError("Product name is required.")
                if price < 0 or stock < 0:
                    raise ValueError("Price and stock must be non-negative.")
                product.name = name
                product.description = description
                product.price = price
                product.stock = stock
                db.commit()
                message = f"Product '{name}' updated."
            elif action == 'delete':
                product_id = int(request.form.get('product_id', '0'))
                product = db.query(Product).filter_by(productID=product_id).first()
                if not product:
                    raise ValueError("Product not found.")
                db.delete(product)
                db.commit()
                message = f"Product '{product.name}' deleted."
        except Exception as e:
            db.rollback()
            error = str(e)

    products = db.query(Product).order_by(Product.productID.desc()).all()
    return render_template('admin_products.html', products=products, message=message, error=error)


# ---------------------------------------------
# Admin: Flash Sale Management
# ---------------------------------------------
@app.route('/admin/flash-sales', methods=['GET', 'POST'])
def admin_flash_sales():
    """Allow admins to create flash sales with title and time window."""
    if not is_admin_user():
        abort(403)

    db = get_db()
    flash_service = FlashSaleService(db)
    message = None
    error = None

    if request.method == 'POST':
        try:
            title = (request.form.get('title') or '').strip()
            product_id = int(request.form.get('product_id', '0'))
            discount_percent = float(request.form.get('discount_percent', '0'))
            max_quantity = int(request.form.get('max_quantity', '0'))
            start_date = request.form.get('start_date') or ''
            start_time = request.form.get('start_time') or '00:00'
            end_date = request.form.get('end_date') or ''
            end_time = request.form.get('end_time') or '00:00'

            # Combine date and time into UTC datetimes
            start_dt = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            end_dt = datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)

            success, msg, _ = flash_service.create_flash_sale(
                product_id=product_id,
                start_time=start_dt,
                end_time=end_dt,
                discount_percent=discount_percent,
                max_quantity=max_quantity,
                title=title or "Flash Sale",
            )
            if success:
                message = msg
            else:
                error = msg
        except Exception as e:
            db.rollback()
            error = f"Error creating flash sale: {e}"

    products = db.query(Product).order_by(Product.name).all()
    active_sales = flash_service.get_active_flash_sales()
    upcoming_sales = db.query(FlashSale).filter(FlashSale._status == 'active').order_by(FlashSale._start_time.asc()).all()

    return render_template(
        'admin_flash_sales.html',
        products=products,
        active_sales=active_sales,
        upcoming_sales=upcoming_sales,
        message=message,
        error=error
    )


# ---------------------------------------------
# Admin: Manage Store (Unified Products, Stock, Flash Sales, Partner Catalog)
# ---------------------------------------------
@app.route('/admin/manage-store', methods=['GET'])
def manage_store():
    """Unified store management page with products, stock alerts, flash sales, and partner catalog."""
    if not is_admin_user():
        abort(403)
    
    db = get_db()
    
    # Get products
    products = db.query(Product).order_by(Product.productID.desc()).all()
    
    # Get low stock alerts and send notifications to admins
    low_stock_service = LowStockAlertService(db)
    low_stock_summary = low_stock_service.get_alert_summary()
    
    # Notify admins of any new low stock items
    low_stock_service.notify_admins_of_low_stock()
    
    # Get flash sales
    flash_service = FlashSaleService(db)
    active_flash_sales = flash_service.get_active_flash_sales()
    flash_sales = db.query(FlashSale).order_by(FlashSale._start_time.desc()).all()
    
    # Get partner catalog data (Checkpoint 2: Partner VAR Catalog Ingest)
    partner_service = PartnerCatalogService(db)
    partners = partner_service.get_all_partners()
    catalog_stats = partner_service.get_catalog_statistics()
    
    # Get any messages from session
    message = request.args.get('message')
    flash_sale_message = request.args.get('flash_message')
    partner_message = request.args.get('partner_message')
    
    return render_template(
        'manage_store.html',
        products=products,
        low_stock_summary=low_stock_summary,
        active_flash_sales=active_flash_sales,
        flash_sales=flash_sales,
        partners=partners,
        catalog_stats=catalog_stats,
        message=message,
        flash_sale_message=flash_sale_message,
        partner_message=partner_message,
    )

# ---------------------------------------------
# Admin: Partner Catalog Management (Checkpoint 2: Partner VAR Catalog Ingest)
# ---------------------------------------------
@app.route('/admin/partner-catalog', methods=['POST'])
def admin_partner_catalog():
    """
    Handle partner catalog management actions.
    
    Implements Checkpoint 2 requirements:
    - Ingest partner product feed (CSV/JSON) via adapter pattern
    - Validate, transform, and upsert items
    - Schedule periodic ingestion for partners
    
    Quality Scenarios Addressed:
    - S.1: Authenticate Actors - API key validation for partners
    - S.2: Validate Input - SQL injection prevention
    - M.1: Adapter Pattern - Support for CSV/JSON/XML formats
    - I.2: Publish-Subscribe - Event broadcasting for catalog updates
    """
    if not is_admin_user():
        abort(403)
    
    db = get_db()
    partner_service = PartnerCatalogService(db)
    action = request.form.get('action', '')
    
    try:
        if action == 'add_partner':
            # Add new partner
            name = request.form.get('name', '').strip()
            api_endpoint = request.form.get('api_endpoint', '').strip() or None
            sync_frequency = int(request.form.get('sync_frequency', 3600))
            
            if not name:
                return redirect(url_for('manage_store', partner_message='Partner name is required'))
            
            success, message, partner = partner_service.create_partner(
                name=name,
                api_endpoint=api_endpoint,
                sync_frequency=sync_frequency
            )
            
            return redirect(url_for('manage_store', partner_message=message))
        
        elif action == 'ingest_file':
            # Ingest catalog from uploaded file (CSV/JSON)
            partner_id = int(request.form.get('partner_id', 0))
            
            if 'catalog_file' not in request.files:
                return redirect(url_for('manage_store', partner_message='No file uploaded'))
            
            file = request.files['catalog_file']
            if file.filename == '':
                return redirect(url_for('manage_store', partner_message='No file selected'))
            
            # Read file content
            file_content = file.read().decode('utf-8')
            filename = file.filename.lower()
            
            # Determine format and ingest
            if filename.endswith('.csv'):
                success, message, count = partner_service.ingest_csv_file(partner_id, file_content)
            elif filename.endswith('.json'):
                success, message, count = partner_service.ingest_json_file(partner_id, file_content)
            else:
                return redirect(url_for('manage_store', partner_message='Unsupported file format. Use CSV or JSON'))
            
            return redirect(url_for('manage_store', partner_message=message))
        
        elif action == 'sync':
            # Sync partner catalog from API endpoint
            partner_id = int(request.form.get('partner_id', 0))
            success, message, count = partner_service.sync_partner_catalog(partner_id)
            return redirect(url_for('manage_store', partner_message=message))
        
        elif action == 'delete':
            # Delete partner
            partner_id = int(request.form.get('partner_id', 0))
            success, message = partner_service.delete_partner(partner_id)
            return redirect(url_for('manage_store', partner_message=message))
        
        elif action == 'update_frequency':
            # Update sync frequency
            partner_id = int(request.form.get('partner_id', 0))
            frequency = int(request.form.get('sync_frequency', 3600))
            success, message = partner_service.update_sync_frequency(partner_id, frequency)
            return redirect(url_for('manage_store', partner_message=message))
        
        else:
            return redirect(url_for('manage_store', partner_message='Unknown action'))
            
    except Exception as e:
        logger.error(f"Partner catalog error: {e}")
        return redirect(url_for('manage_store', partner_message=f'Error: {str(e)}'))


@app.route('/api/features/<feature_name>/toggle', methods=['POST'])
def toggle_feature(feature_name):
    """Toggle feature on/off"""
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401
    
    db = get_db()
    quality_manager = get_quality_manager()
    
    try:
        action = request.json.get('action')  # 'enable' or 'disable'
        rollout_percentage = request.json.get('rollout_percentage', 100)
        
        if action == 'enable':
            success, message = quality_manager.enable_feature(
                feature_name, rollout_percentage, updated_by=f"user_{session['user_id']}"
            )
        elif action == 'disable':
            success, message = quality_manager.disable_feature(
                feature_name, updated_by=f"user_{session['user_id']}"
            )
        else:
            return jsonify({'error': 'Invalid action. Use "enable" or "disable"'}), 400
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/progress/<operation_id>', methods=['GET'])
def get_operation_progress(operation_id):
    """Get progress for an operation"""
    try:
        quality_manager = get_quality_manager()
        progress = quality_manager.get_progress(operation_id)
        
        if progress:
            return jsonify(progress)
        else:
            return jsonify({'error': 'Operation not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==============================================
# CHECKPOINT 4: NEW FEATURES
# ==============================================

# ---------------------------------------------
# Feature 2.1: Order History Filtering & Search
# ---------------------------------------------

@app.route('/order-history', methods=['GET'])
def order_history():
    """
    Order History with filtering and search.
    Supports filtering by status, date range, and keyword search.
    
    Date Validation (CP4 Feature 2.1):
    - 'To Date' must be on or after 'From Date'
    - 'From Date' cannot be in the future
    - Invalid dates are cleared with error message displayed
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    user = db.query(User).filter_by(userID=session['user_id']).first()
    if not user:
        session.clear()
        return redirect(url_for('login'))
    
    # Get filter parameters
    status_filter = request.args.get('status', '').strip() or None
    start_date_str = request.args.get('start_date', '').strip() or None
    end_date_str = request.args.get('end_date', '').strip() or None
    keyword = request.args.get('keyword', '').strip() or None
    
    # Validate page number
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    
    # Parse dates
    history_service = HistoryService(db)
    start_date = history_service.parse_date(start_date_str)
    end_date = history_service.parse_date(end_date_str)
    
    # Date validation error message
    date_error = None
    today = datetime.now(timezone.utc)
    today_date_str = today.strftime('%Y-%m-%d')  # For HTML max attribute
    
    # Validate date range: end_date must be >= start_date
    if start_date and end_date and end_date < start_date:
        date_error = "Invalid date range: 'To Date' must be on or after 'From Date'. The invalid 'To Date' has been cleared."
        end_date = None
        end_date_str = ''
    
    # Validate start_date is not in the future
    if start_date and start_date.date() > today.date():
        date_error = "Invalid date: 'From Date' cannot be in the future. The invalid date has been cleared."
        start_date = None
        start_date_str = ''
    
    # Get filtered order history
    order_data = history_service.get_order_history(
        user_id=session['user_id'],
        status_filter=status_filter,
        start_date=start_date,
        end_date=end_date,
        keyword=keyword,
        page=page,
    )
    
    # Get returns history with same filters
    returns_data = history_service.get_returns_history(
        user_id=session['user_id'],
        status_filter=status_filter if status_filter and status_filter.upper() in ['PENDING_AUTHORIZATION', 'AUTHORIZED', 'IN_TRANSIT', 'RECEIVED', 'UNDER_INSPECTION', 'APPROVED', 'REJECTED', 'REFUNDED', 'CANCELLED'] else None,
        start_date=start_date,
        end_date=end_date,
        keyword=keyword,
        page=page,
    )
    
    # Available status options for dropdown
    status_options = [
        {'value': '', 'label': 'All Statuses'},
        {'value': 'completed', 'label': 'Completed'},
        {'value': 'pending', 'label': 'Pending'},
        {'value': 'returned', 'label': 'Returned'},
        {'value': 'refunded', 'label': 'Refunded'},
    ]
    
    return render_template(
        'order_history.html',
        username=user.username,
        order_data=order_data,
        returns_data=returns_data,
        status_options=status_options,
        current_filters={
            'status': status_filter or '',
            'start_date': start_date_str or '',
            'end_date': end_date_str or '',
            'keyword': keyword or '',
        },
        date_error=date_error,
        today_date=today_date_str,
    )


@app.route('/api/order-history', methods=['GET'])
def api_order_history():
    """API endpoint for order history with filters.
    
    Date Validation:
    - 'end_date' must be on or after 'start_date'
    - 'start_date' cannot be in the future
    """
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    db = get_db()
    history_service = HistoryService(db)
    
    # Get filter parameters
    status_filter = request.args.get('status') or None
    start_date = history_service.parse_date(request.args.get('start_date'))
    end_date = history_service.parse_date(request.args.get('end_date'))
    keyword = request.args.get('keyword') or None
    
    # Validate page number
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    
    # Validate date range: end_date must be >= start_date
    if start_date and end_date and end_date < start_date:
        return jsonify({
            'error': "Invalid date range: 'end_date' must be on or after 'start_date'.",
            'code': 'INVALID_DATE_RANGE'
        }), 400
    
    # Validate start_date is not in the future
    today = datetime.now(timezone.utc)
    if start_date and start_date.date() > today.date():
        return jsonify({
            'error': "Invalid date: 'start_date' cannot be in the future.",
            'code': 'FUTURE_DATE'
        }), 400
    
    order_data = history_service.get_order_history(
        user_id=session['user_id'],
        status_filter=status_filter,
        start_date=start_date,
        end_date=end_date,
        keyword=keyword,
        page=page,
    )
    
    return jsonify(order_data)


# ---------------------------------------------
# Feature 2.2: Low Stock Alerts API
# ---------------------------------------------

@app.route('/api/admin/low-stock', methods=['GET'])
def api_low_stock_alerts():
    """API endpoint for low stock alerts (admin only)."""
    if not is_admin_user():
        return jsonify({'error': 'Forbidden'}), 403
    
    db = get_db()
    low_stock_service = LowStockAlertService(db)
    summary = low_stock_service.get_alert_summary()
    
    return jsonify(summary)


# ---------------------------------------------
# Feature 2.3: Notifications API
# ---------------------------------------------

@app.route('/api/notifications', methods=['GET'])
def api_get_notifications():
    """Get notifications for the current user."""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    notification_service = NotificationService()
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    limit = int(request.args.get('limit', 20))
    
    notifications = notification_service.get_notifications(
        user_id=session['user_id'],
        unread_only=unread_only,
        limit=limit,
    )
    unread_count = notification_service.get_unread_count(session['user_id'])
    
    return jsonify({
        'notifications': notifications,
        'unread_count': unread_count,
    })


@app.route('/api/notifications/<notification_id>/read', methods=['POST'])
def api_mark_notification_read(notification_id):
    """Mark a notification as read."""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    notification_service = NotificationService()
    success = notification_service.mark_as_read(session['user_id'], notification_id)
    
    return jsonify({
        'success': success,
        'unread_count': notification_service.get_unread_count(session['user_id']),
    })


@app.route('/api/notifications/mark-all-read', methods=['POST'])
def api_mark_all_notifications_read():
    """Mark all notifications as read."""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    notification_service = NotificationService()
    count = notification_service.mark_all_as_read(session['user_id'])
    
    return jsonify({
        'success': True,
        'marked_count': count,
        'unread_count': 0,
    })

