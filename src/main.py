# src/main.py
import logging
import random
import time
from datetime import datetime, timezone
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
from src.models import Product, User, Sale, SaleItem, Payment, Cash, Card, FailedPaymentLog, Base
from src.tactics.manager import QualityTacticsManager
from src.blueprints.returns import returns_bp
from src.observability import (
    configure_logging,
    increment_counter,
    observe_latency,
    get_metrics_snapshot,
    check_database_health,
)
from src.observability.logging_config import ensure_request_id

app = Flask(__name__, template_folder='../templates', static_folder='../static')
Config.configure_app(app)
configure_logging(app)
app.register_blueprint(returns_bp)

logger = logging.getLogger(__name__)

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
    return QualityTacticsManager(db, {
        'throttling': {'max_rps': 100, 'window_size': 1},
        'queue': {'max_size': 1000},
        'concurrency': {'max_concurrent': 10, 'lock_timeout': 50},
        'monitoring': {'metrics_interval': 60},
        'usability': {}
    })

def is_admin_user() -> bool:
    return bool(session.get('is_admin')) or session.get('user_id') == 1

@app.context_processor
def inject_nav_context():
    user = None
    if 'user_id' in session:
        db = get_db()
        user = db.query(User).filter_by(userID=session['user_id']).first()
    return {
        "current_user": user,
        "is_admin": is_admin_user(),
    }

@app.before_request
def before_request_logging():
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

def get_cart_items(user_id, db):
    """Get all items in the user's cart from database."""
    cart_sale = get_or_create_cart_sale(user_id, db)
    cart_items = []
    grand_total = 0.0
    
    for sale_item in cart_sale.items:
        product = db.query(Product).filter_by(productID=sale_item.productID).first()
        if product:
            # Calculate current values
            discounted_unit_price = product.get_discounted_unit_price()
            subtotal = product.get_subtotal_for_quantity(sale_item.quantity)
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
                'available_stock': product.stock
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
    
    products = db.query(Product).all()
    
    # Get cart from database instead of session
    cart = get_cart_items(session['user_id'], db)
    
    # Note: Do not auto-adjust quantities; user decides how to resolve stock issues
    cart_update_message = None

    # Get recent completed sales (exclude cart sales)
    recent_sales = db.query(Sale).filter_by(userID=session['user_id']).filter(Sale._status != 'cart').order_by(desc(Sale._sale_date)).limit(5).all()
    username = user.username
    
    return render_template('index.html', products=products, cart=cart, username=username, recent_sales=recent_sales, cart_update_message=cart_update_message)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        db = get_db()
        if db.query(User).filter_by(username=username).first():
            return render_template('register.html', error='Username already exists.')
        if db.query(User).filter_by(email=email).first():
            return render_template('register.html', error='Email already registered.')

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, passwordHash=hashed_password)
        db.add(new_user)
        db.commit()
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        user = db.query(User).filter_by(username=username).first()
        if user and check_password_hash(user.passwordHash, password):
            session['user_id'] = user.userID
            session['is_admin'] = bool(user.userID == 1 or user.username.lower() == 'admin')
            # Preserve existing cart or initialize empty cart if none exists
            if 'cart' not in session:
                session['cart'] = {'items': [], 'grand_total': 0.0}
            return redirect(url_for('index'))
        return render_template('login.html', error='Invalid username or password.')
    return render_template('login.html')

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
    
    # Get cart from database instead of session
    cart = get_cart_items(session['user_id'], db)
    if not cart.get('items'):
        # Return to index with error message instead of silent redirect
        user = db.query(User).filter_by(userID=session['user_id']).first()
        products = db.query(Product).all()
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
        products = db.query(Product).all()
        recent_sales = db.query(Sale).filter_by(userID=session['user_id']).filter(Sale._status != 'cart').order_by(desc(Sale._sale_date)).limit(5).all()
        msg = f"System is busy. Please try again in a moment. ({throttle_msg})"
        return render_template('index.html', products=products, cart=cart, username=user.username, recent_sales=recent_sales, cart_update_message=msg), 429

    try:
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
                products = db.query(Product).all()
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
                products_local = db.query(Product).all()
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
                products = db.query(Product).all()
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
            
            for item in cart['items']:
                product = product_map[item['product_id']]
                quantity = item['quantity']

                final_unit_price = product.get_discounted_unit_price()
                subtotal = product.get_subtotal_for_quantity(quantity)
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
            # Mark the sale as failed instead of rolling back
            new_sale._status = 'failed'
            payment._status = 'failed'
            
            # Log the failed payment attempt
            log = FailedPaymentLog(
                userID=session['user_id'],
                attempt_date=datetime.now(timezone.utc),
                amount=total_amount,
                payment_method=payment_method,
                reason=reason
            )
            db.add(log)
            db.commit()
            
            # Convert the failed sale back to cart status to preserve items
            new_sale._status = 'cart'
            db.commit()
            
            # Get fresh cart from database
            cart = get_cart_items(session['user_id'], db)
            user = db.query(User).filter_by(userID=session['user_id']).first()
            products = db.query(Product).all()
            recent_sales = db.query(Sale).filter_by(userID=session['user_id']).filter(Sale._status != 'cart').order_by(desc(Sale._sale_date)).limit(5).all()
            msg = f"Payment failed: {reason}. Failed payment attempt #{log.logID}. Please use a different payment method or cancel your sale."
            return render_template('index.html', products=products, cart=cart, username=user.username, recent_sales=recent_sales, cart_update_message=msg), 400

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
    """Ingest partner catalog data"""
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return jsonify({'error': 'API key required'}), 401
    
    db = get_db()
    quality_manager = get_quality_manager()
    
    try:
        data = request.get_data(as_text=True)
        partner_format = request.headers.get('Content-Type', '').split('/')[-1]
        
        # Process with all quality tactics
        success, result = quality_manager.process_partner_catalog_ingest(
            partner_id=1,  # This would be determined from API key
            data=data,
            api_key=api_key
        )
        
        if success:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

@app.route('/admin/dashboard', methods=['GET'])
def admin_dashboard():
    if not is_admin_user():
        abort(403)
    metrics = get_metrics_snapshot()
    db_status = check_database_health()
    return render_template('admin_dashboard.html', metrics=metrics, db_status=db_status)

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

