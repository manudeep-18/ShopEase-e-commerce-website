const cartCountEl = document.getElementById('cart-count');
let cartCount = 0;

function addCart() {
    cartCount += 1;
    cartCountEl.textContent = cartCount;
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
