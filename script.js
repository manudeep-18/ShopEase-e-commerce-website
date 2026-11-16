(function () {
const cartCountEl = document.getElementById('cart-count');
let cartCount = 0;

function updateCartCounts(cart) {
    const count = cart.reduce((total, item) => total + Number(item.quantity || 0), 0);
    document.querySelectorAll('#cartCount, #cart-count, #headerCount').forEach(element => {
        element.textContent = count;
    });
}

function getCartCount() {
    let cart;
    try {
        cart = JSON.parse(localStorage.getItem('shopease_cart') || '[]');
    } catch {
        cart = [];
    }
    return Array.isArray(cart)
        ? cart.reduce((total, item) => total + Number(item.quantity || 0), 0)
        : 0;
}

function addCart() {
    cartCount += 1;
    if (cartCountEl) cartCountEl.textContent = cartCount;
    showToast('Added to cart');
}

function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(20px)';
    }, 1800);

    setTimeout(() => {
        toast.remove();
    }, 2200);
}

async function addItem(item) {
    const cartItem = {
        name: item.name,
        price: Number(item.price),
        image: item.image || '',
        quantity: 1
    };
    if (item.id !== undefined && item.id !== null && String(item.id)) {
        cartItem.id = String(item.id);
    }
    let cart;
    try {
        cart = JSON.parse(localStorage.getItem('shopease_cart') || '[]');
    } catch {
        cart = [];
    }
    if (!Array.isArray(cart)) cart = [];
    const existingItem = cart.find(cartEntry =>
        cartItem.id && cartEntry.id
            ? String(cartEntry.id) === cartItem.id
            : cartEntry.name === cartItem.name
    );
    if (existingItem) existingItem.quantity = Number(existingItem.quantity || 0) + 1;
    else cart.push(cartItem);

    const response = await fetch('/api/cart', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: cart })
    });
    if (response.status === 401) {
        localStorage.setItem('shopease_cart', JSON.stringify(cart));
        updateCartCounts(cart);
        return { authenticated: false };
    }
    let data;
    try {
        data = await response.json();
    } catch {
        throw new Error('Unexpected cart response');
    }
    if (!response.ok) throw new Error('Cart update failed');
    if (!data || !Array.isArray(data.cart)) {
        throw new Error('Updated cart was not returned');
    }
    localStorage.setItem('shopease_cart', JSON.stringify(data.cart));
    updateCartCounts(data.cart);
    return { authenticated: true, data };
}

window.ShopEaseCart = {
    addItem,
    getCount: getCartCount
};

document.addEventListener('DOMContentLoaded', () => {
    const shopNow = document.querySelector('[data-cta="shop"]');
    const productSection = document.querySelector('.products');

    if (shopNow && productSection) {
        shopNow.addEventListener('click', event => {
            event.preventDefault();
            productSection.scrollIntoView({ behavior: 'smooth' });
        });
    }
});
})();
