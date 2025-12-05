// static/js/main.js

/**
 * Toggles the visibility of the card detail fields based on the selected payment method.
 */
function toggleCardDetails() {
    const paymentMethod = document.getElementById('payment_method').value;
    const cardDetailsDiv = document.getElementById('card-details');
    if (paymentMethod === 'Card') {
        cardDetailsDiv.classList.remove('hidden');
        cardDetailsDiv.querySelectorAll('input').forEach(input => input.required = true);
    } else {
        cardDetailsDiv.classList.add('hidden');
        cardDetailsDiv.querySelectorAll('input').forEach(input => input.required = false);
    }
}

/**
 * Displays a notification message to the user.
 * @param {string} message - The message to display.
 * @param {boolean} isError - Whether the message is an error.
 */
function showMessage(message, isError = false) {
    // Remove any existing popups to prevent stacking
    document.querySelectorAll('.notification-popup').forEach(p => p.remove());

    const popup = document.createElement('div');
    const bgColor = isError ? 'bg-red-500' : 'bg-green-500';
    popup.className = `notification-popup fixed top-5 right-5 p-4 rounded-md shadow-lg text-white flex items-start gap-2 z-50 ${bgColor}`;
    
    const messageEl = document.createElement('p');
    messageEl.textContent = message;
    popup.appendChild(messageEl);

    document.body.appendChild(popup);

    setTimeout(() => {
        popup.remove();
    }, 4000); // Popup disappears after 4 seconds
}

/**
 * Renders the shopping cart UI with data from the server.
 * @param {object} cartData - The cart object containing items and totals.
 */
function renderCart(cartData) {
    const cartItemsDiv = document.getElementById('cart-items');
    const cartTotalsDiv = document.getElementById('cart-totals');
    
    // Clear previous content
    cartItemsDiv.innerHTML = '';
    cartTotalsDiv.innerHTML = '';

    if (!cartData || !cartData.items || cartData.items.length === 0) {
        // Check if there's a payment failure message being displayed
        const paymentFailureAlert = document.querySelector('.bg-yellow-100.border-l-4.border-yellow-500');
        const hasPaymentFailure = paymentFailureAlert && paymentFailureAlert.textContent.includes('Payment failed');
        
        if (hasPaymentFailure) {
            cartItemsDiv.innerHTML = '<p class="text-gray-500">Your cart has your last sale preserved. Continue by selecting one option below.</p>';
        } else {
            cartItemsDiv.innerHTML = '<p class="text-gray-500">Your cart is empty.</p>';
        }
        return; // Exit if cart is empty
    }

    // Render each cart item
    cartData.items.forEach(item => {
        const itemDiv = document.createElement('div');
        itemDiv.className = 'cart-item border-b py-3';
        const hasConflict = typeof item.available_stock === 'number' && item.quantity > item.available_stock;
        const flashSaleBadge = item.is_flash_sale ? '<span class="text-xs bg-red-500 text-white px-2 py-0.5 rounded ml-1">⚡ FLASH SALE</span>' : '';
        itemDiv.innerHTML = `
            <div class="flex justify-between items-center">
                <span class="font-semibold">${item.name}${flashSaleBadge}</span>
                <div class="flex items-center gap-2">
                    <input 
                        type="number" 
                        value="${item.quantity}" 
                        min="0" 
                        class="w-16 text-center border rounded-md"
                        onchange="setCartQuantity(${item.product_id}, this.value)"
                        data-product-id="${item.product_id}">
                    <span>$${item.subtotal.toFixed(2)}</span>
                    <button onclick="setCartQuantity(${item.product_id}, 0)" class="text-red-500 hover:text-red-700 font-bold ml-2">X</button>
                </div>
            </div>
            <div class="text-xs ${item.is_flash_sale ? 'text-red-600 font-semibold' : 'text-gray-500'} mt-1">
                ${item.is_flash_sale ? '⚡ Flash Sale ' : ''}Discount: $${item.discount_applied.toFixed(2)} | Fees: $${(item.shipping_fee + item.import_duty).toFixed(2)}
            </div>
            ${hasConflict ? `
            <div class="mt-2 p-2 bg-yellow-100 border border-yellow-300 text-yellow-800 rounded">
                Only ${item.available_stock} in stock. Choose an action:
                <div class="mt-2 flex gap-2">
                    <button class="bg-blue-500 text-white px-3 py-1 rounded" onclick="setCartQuantity(${item.product_id}, ${item.available_stock})">Reduce to ${item.available_stock}</button>
                    <button class="bg-yellow-500 text-white px-3 py-1 rounded" onclick="setCartQuantity(${item.product_id}, 0)">Remove item</button>
                    <button class="bg-red-500 text-white px-3 py-1 rounded" onclick="document.getElementById('cancel-sale-form').submit()">Cancel sale</button>
                </div>
            </div>` : ''}
        `;
        cartItemsDiv.appendChild(itemDiv);
    });

    // Render cart totals
    cartTotalsDiv.innerHTML = `
        <div class="text-right space-y-1 mt-4">
            <p>Subtotal: <span class="font-semibold">$${cartData.items.reduce((acc, item) => acc + item.subtotal, 0).toFixed(2)}</span></p>
            <p>Shipping: <span class="font-semibold">$${cartData.items.reduce((acc, item) => acc + item.shipping_fee, 0).toFixed(2)}</span></p>
            <p>Duties: <span class="font-semibold">$${cartData.items.reduce((acc, item) => acc + item.import_duty, 0).toFixed(2)}</span></p>
            <p class="text-xl font-bold border-t pt-2">Grand Total: <span>$${cartData.grand_total.toFixed(2)}</span></p>
        </div>
    `;
}

/**
 * Adds an item to the cart via an AJAX request.
 * @param {Event} event - The form submission event.
 */
async function addToCart(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    
    try {
        const response = await fetch('/add_to_cart', { method: 'POST', body: formData });
        const result = await response.json();
        
        if (response.ok) {
            // --- FIX HIGHLIGHT: Use product name from response with a robust fallback ---
            const productName = result.product_name || 'Item'; // Use server name, fallback to 'Item' if missing.
            showMessage(`'${productName}' added to cart.`);
            renderCart(result.cart);
            form.reset(); // Clear the form after successful submission
        } else {
            showMessage(result.error, true);
        }
    } catch (error) {
        showMessage('An error occurred while adding the item.', true);
    }
}

/**
 * Sets the quantity of a product in the cart via an AJAX request.
 * @param {number} productId - The ID of the product to update.
 * @param {number} quantity - The new quantity for the product.
 */
async function setCartQuantity(productId, quantity) {
    const formData = new FormData();
    formData.append('product_id', productId);
    formData.append('quantity', quantity);
    
    try {
        const response = await fetch('/set_cart_quantity', { method: 'POST', body: formData });
        const result = await response.json();

        if (response.ok) {
            if (quantity > 0) {
                showMessage(`Quantity updated.`);
            } else {
                showMessage('Item removed from cart.');
            }
            renderCart(result.cart);
        } else if (response.status === 409) {
            showStockOptions(result.product_id, result.available, result.product_name);
        } else {
            showMessage(result.error || 'Could not update quantity.', true);
        }
    } catch (error) {
        showMessage('An error occurred while updating the cart.', true);
    }
}


/**
 * Initializes the application when the page is loaded.
 */
document.addEventListener('DOMContentLoaded', () => {
    const body = document.querySelector('body');
    try {
        const initialCart = JSON.parse(body.dataset.initialCart);
        renderCart(initialCart);
    } catch (e) {
        console.error("Could not parse initial cart data from server:", e);
        renderCart({ items: [], grand_total: 0 }); // Render an empty cart on failure
    }
});

/**
 * Validates checkout form for card payments and empty cart.
 * - Checks if cart has items
 * - Card number: 15-19 digits
 * - Expiry: MM/YYYY and not in the past
 */
function validateCheckout(event) {
    // First check if cart is empty
    const cartItemsDiv = document.getElementById('cart-items');
    const cartTotalsDiv = document.getElementById('cart-totals');
    
    // Check if there's a payment failure message being displayed
    const paymentFailureAlert = document.querySelector('.bg-yellow-100.border-l-4.border-yellow-500');
    const hasPaymentFailure = paymentFailureAlert && paymentFailureAlert.textContent.includes('Payment failed');
    
    // Only check for empty cart if there's no payment failure message
    if (!hasPaymentFailure) {
        const isEmptyCart = cartItemsDiv.innerHTML.includes('Your cart is empty') || 
                           cartItemsDiv.innerHTML.includes('Your cart has your last sale preserved') ||
                           cartTotalsDiv.innerHTML.trim() === '';
        
        if (isEmptyCart) {
            showMessage('Cannot complete purchase: Your cart is empty. Please add items to your cart first.', true);
            event?.preventDefault();
            return false;
        }
    }

    const methodEl = document.getElementById('payment_method');
    if (!methodEl || methodEl.value !== 'Card') return true;

    const numberEl = document.getElementById('card_number');
    const expEl = document.getElementById('card_exp_date');
    const number = (numberEl?.value || '').replace(/\s|-/g, '');
    const exp = (expEl?.value || '').trim();

    if (!/^\d{15,19}$/.test(number)) {
        showMessage('Card number must be 15-19 digits.', true);
        numberEl?.focus();
        event?.preventDefault();
        return false;
    }

    const expMatch = exp.match(/^(0[1-9]|1[0-2])\/(\d{4})$/);
    if (!expMatch) {
        showMessage('Expiry must be MM/YYYY.', true);
        expEl?.focus();
        event?.preventDefault();
        return false;
    }

    const month = parseInt(expMatch[1], 10);
    const year = parseInt(expMatch[2], 10);
    const now = new Date();
    const currentMonth = now.getUTCMonth() + 1;
    const currentYear = now.getUTCFullYear();
    if (year < currentYear || (year === currentYear && month < currentMonth)) {
        showMessage('Card has expired.', true);
        expEl?.focus();
        event?.preventDefault();
        return false;
    }

    return true;
}
/**
 * Presents options to resolve insufficient stock for an item.
 * @param {number} productId
 * @param {number} available
 * @param {string} productName
 */
function showStockOptions(productId, available, productName) {
    // Remove existing modal if any
    const existing = document.getElementById('stock-options-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'stock-options-modal';
    overlay.className = 'fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50';

    const modal = document.createElement('div');
    modal.className = 'bg-white rounded-lg shadow-lg p-6 w-full max-w-md';
    modal.innerHTML = `
        <h3 class="text-xl font-semibold mb-2">Insufficient stock</h3>
        <p class="text-gray-700 mb-4">Only ${available} in stock for '${productName}'. Choose an action:</p>
        <div class="flex flex-col gap-2">
            <button id="reduce-btn" class="bg-blue-500 text-white px-4 py-2 rounded-md hover:bg-blue-600">Reduce to ${available}</button>
            <button id="remove-btn" class="bg-yellow-500 text-white px-4 py-2 rounded-md hover:bg-yellow-600">Remove item</button>
            <button id="cancel-btn" class="bg-red-500 text-white px-4 py-2 rounded-md hover:bg-red-600">Cancel sale</button>
            <button id="close-btn" class="bg-gray-200 text-gray-800 px-4 py-2 rounded-md hover:bg-gray-300">Close</button>
        </div>
    `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    document.getElementById('reduce-btn').onclick = async () => {
        await setCartQuantity(productId, available);
        overlay.remove();
    };
    document.getElementById('remove-btn').onclick = async () => {
        await setCartQuantity(productId, 0);
        overlay.remove();
    };
    document.getElementById('cancel-btn').onclick = () => {
        const cancelForm = document.getElementById('cancel-sale-form');
        if (cancelForm) cancelForm.submit();
    };
    document.getElementById('close-btn').onclick = () => overlay.remove();
}

