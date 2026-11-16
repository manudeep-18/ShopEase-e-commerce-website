// DOM Elements
const loginForm = document.getElementById('loginForm');
const emailInput = document.getElementById('email');
const passwordInput = document.getElementById('password');
const rememberMeCheckbox = document.getElementById('rememberMe');
const togglePasswordBtn = document.getElementById('togglePassword');
const emailError = document.getElementById('emailError');
const passwordError = document.getElementById('passwordError');
const formError = document.getElementById('formError');
const forgotPasswordModal = document.getElementById('forgotPasswordModal');
const resetEmailInput = document.getElementById('resetEmail');
const requestResetForm = document.getElementById('requestResetForm');
const completeResetForm = document.getElementById('completeResetForm');

async function readApiResponse(response) {
    let data;
    try {
        data = await response.json();
    } catch {
        if (response.status === 404 || response.status === 405) {
            throw new Error('Password reset API is not available. Stop and restart Flask from the project folder, then reload this page.');
        }
        throw new Error(`The server returned an unexpected response (HTTP ${response.status}).`);
    }
    if (!response.ok) {
        throw new Error(data.error || 'The request could not be completed.');
    }
    return data;
}

document.getElementById('forgotPasswordLink').addEventListener('click', (event) => {
    event.preventDefault();
    resetEmailInput.value = emailInput.value.trim();
    document.getElementById('resetRequestError').textContent = '';
    document.getElementById('resetCompleteError').textContent = '';
    requestResetForm.classList.remove('hidden');
    completeResetForm.classList.add('hidden');
    forgotPasswordModal.classList.remove('hidden');
    resetEmailInput.focus();
});

document.getElementById('closeForgotPassword').addEventListener('click', () => {
    forgotPasswordModal.classList.add('hidden');
});

forgotPasswordModal.addEventListener('click', (event) => {
    if (event.target === forgotPasswordModal) {
        forgotPasswordModal.classList.add('hidden');
    }
});

requestResetForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const submitButton = requestResetForm.querySelector('button[type="submit"]');
    submitButton.disabled = true;
    document.getElementById('resetRequestError').textContent = '';
    try {
        const response = await fetch('/api/forgot-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: resetEmailInput.value.trim() })
        });
        const data = await readApiResponse(response);
        document.getElementById('resetCodeMessage').textContent =
            `${data.message} If an account exists, check your inbox. The code expires in 10 minutes.`;
        requestResetForm.classList.add('hidden');
        completeResetForm.classList.remove('hidden');
        document.getElementById('resetOtp').focus();
    } catch (error) {
        document.getElementById('resetRequestError').textContent = error.message || 'Unable to send a reset code.';
    } finally {
        submitButton.disabled = false;
    }
});

completeResetForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const errorElement = document.getElementById('resetCompleteError');
    errorElement.textContent = '';
    const newPassword = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmNewPassword').value;
    if (newPassword !== confirmPassword) {
        errorElement.textContent = 'Passwords do not match.';
        return;
    }
    const submitButton = completeResetForm.querySelector('button[type="submit"]');
    submitButton.disabled = true;
    try {
        const response = await fetch('/api/reset-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: resetEmailInput.value.trim(),
                otp: document.getElementById('resetOtp').value.trim(),
                newPassword
            })
        });
        const data = await readApiResponse(response);
        forgotPasswordModal.classList.add('hidden');
        loginForm.reset();
        emailInput.value = resetEmailInput.value.trim();
        passwordInput.focus();
        showToast(data.message, 'success');
    } catch (error) {
        errorElement.textContent = error.message || 'Unable to reset your password.';
    } finally {
        submitButton.disabled = false;
    }
});

// Load saved email if "Remember Me" was checked
document.addEventListener('DOMContentLoaded', () => {
    const savedEmail = localStorage.getItem('shopease_remember_email');
    if (savedEmail) {
        emailInput.value = savedEmail;
        rememberMeCheckbox.checked = true;
    }

    // Update cart count from localStorage
    const savedCartCount = localStorage.getItem('shopease_cart_count');
    if (savedCartCount) {
        const cartCountEl = document.getElementById('cart-count');
        if (cartCountEl) cartCountEl.textContent = savedCartCount;
    }
});

// Toggle Password Visibility
togglePasswordBtn.addEventListener('click', (e) => {
    e.preventDefault();
    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        togglePasswordBtn.classList.add('active');
    } else {
        passwordInput.type = 'password';
        togglePasswordBtn.classList.remove('active');
    }
});

// Email Validation
function validateEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

// Real-time Email Validation
emailInput.addEventListener('blur', () => {
    if (!emailInput.value) {
        emailError.textContent = 'Email is required';
        emailInput.classList.add('border-red-500');
        emailInput.classList.remove('border-gray-700');
    } else if (!validateEmail(emailInput.value)) {
        emailError.textContent = 'Please enter a valid email';
        emailInput.classList.add('border-red-500');
        emailInput.classList.remove('border-gray-700');
    } else {
        emailError.textContent = '';
        emailInput.classList.remove('border-red-500');
        emailInput.classList.add('border-gray-700');
    }
});

emailInput.addEventListener('focus', () => {
    emailError.textContent = '';
    emailInput.classList.remove('border-red-500');
    emailInput.classList.add('border-gray-700');
});

// Real-time Password Validation
passwordInput.addEventListener('blur', () => {
    if (!passwordInput.value) {
        passwordError.textContent = 'Password is required';
        passwordInput.classList.add('border-red-500');
        passwordInput.classList.remove('border-gray-700');
    } else if (passwordInput.value.length < 6) {
        passwordError.textContent = 'Password must be at least 6 characters';
        passwordInput.classList.add('border-red-500');
        passwordInput.classList.remove('border-gray-700');
    } else {
        passwordError.textContent = '';
        passwordInput.classList.remove('border-red-500');
        passwordInput.classList.add('border-gray-700');
    }
});

passwordInput.addEventListener('focus', () => {
    passwordError.textContent = '';
    passwordInput.classList.remove('border-red-500');
    passwordInput.classList.add('border-gray-700');
});

// Form Submission
loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    formError.textContent = '';
    emailError.textContent = '';
    passwordError.textContent = '';

    const email = emailInput.value.trim();
    const password = passwordInput.value;

    let hasError = false;

    if (!email) {
        emailError.textContent = 'Email is required';
        emailInput.classList.add('border-red-500');
        hasError = true;
    } else if (!validateEmail(email)) {
        emailError.textContent = 'Please enter a valid email';
        emailInput.classList.add('border-red-500');
        hasError = true;
    }

    if (!password) {
        passwordError.textContent = 'Password is required';
        passwordInput.classList.add('border-red-500');
        hasError = true;
    } else if (password.length < 6) {
        passwordError.textContent = 'Password must be at least 6 characters';
        passwordInput.classList.add('border-red-500');
        hasError = true;
    }

    if (hasError) return;

    const submitBtn = loginForm.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    submitBtn.textContent = 'Signing in...';
    submitBtn.disabled = true;

    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Invalid email or password');
        }

        if (rememberMeCheckbox.checked) {
            localStorage.setItem('shopease_remember_email', email);
        } else {
            localStorage.removeItem('shopease_remember_email');
        }

        localStorage.setItem('shopease_user_logged_in', 'true');
        localStorage.setItem('shopease_user_email', email);
        localStorage.setItem('shopease_user_name', data.user.name || 'ShopEase User');
        if (Array.isArray(data.cart)) {
            localStorage.setItem('shopease_cart', JSON.stringify(data.cart));
        }

        showToast('Login successful! Redirecting...', 'success');
        setTimeout(() => {
            window.location.href = 'index.html';
        }, 1500);
    } catch (error) {
        formError.textContent = error.message || 'Unable to login right now.';
        showToast(error.message || 'Invalid credentials', 'error');
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;
    }
});

// Toast Notification Function
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `${type}`;
    toast.classList.add('show');

    setTimeout(() => {
        toast.classList.remove('show');
    }, 2000);

    setTimeout(() => {
        toast.textContent = '';
        toast.className = '';
    }, 2300);
}

// Social Login Handlers
document.querySelectorAll('.social-login-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        e.preventDefault();
        const provider = btn.getAttribute('data-provider');
        showToast(`${provider.charAt(0).toUpperCase() + provider.slice(1)} login coming soon!`, 'info');
    });
});
