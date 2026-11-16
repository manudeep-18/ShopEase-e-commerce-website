from __future__ import annotations

import os
import hashlib
import hmac
import logging
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import math
from typing import Any
from uuid import uuid4

from flask import Flask, jsonify, request, send_from_directory, session

from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError
import razorpay
from requests.exceptions import ConnectionError, Timeout
from razorpay.errors import (
    BadRequestError,
    GatewayError,
    ServerError,
    SignatureVerificationError,
)

app = Flask(__name__)
logger = logging.getLogger(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY') or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('FLASK_SESSION_COOKIE_SECURE') == '1',
)
MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017').strip()
MONGODB_DATABASE = os.environ.get('MONGODB_DATABASE', 'shopease')
if os.environ.get('MONGO_MOCK_FOR_TESTS') == '1':
    import mongomock

    mongo_client = mongomock.MongoClient()
else:
    mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
database = mongo_client[MONGODB_DATABASE]


@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
    return response


VALID_ORDER_STATUSES = [
    'Packed',
    'Dispatched',
    'Out for Delivery',
    'Delivered',
    'Return Requested',
    'Replacement Requested',
    'Refund Processing',
    'Refunded',
    'Returned'
]

STATUS_RANK = {
    'Packed': 0,
    'Dispatched': 1,
    'Out for Delivery': 2,
    'Delivered': 3,
    'Return Requested': 4,
    'Replacement Requested': 4,
    'Refund Processing': 5,
    'Refunded': 6,
    'Returned': 6,
}

PRODUCT_CATALOG: dict[str, tuple[str, tuple[int, ...]]] = {
    'Apple Laptop': ('Computing', (45000, 50000)),
    'Apple Laptops': ('Computing', (50000,)),
    'Smartphone': ('Mobiles', (100000,)),
    'Iphone 15': ('Mobiles', (100000,)),
    'Noise Cancelling Earbuds': ('Audio', (7999,)),
    'Studio Wireless Headphones': ('Audio', (12999,)),
    'Wireless Headphones': ('Audio', (16000, 20000)),
    'Mechanical Keyboard': ('Accessories', (6499,)),
    '4K Monitor': ('Computing', (32999,)),
    'Portable Speaker': ('Audio', (5499,)),
    'Bass Bluetooth Speaker': ('Audio', (6999,)),
    'Pixel Pro 5G': ('Mobiles', (74999,)),
    'Galaxy Ultra': ('Mobiles', (89999,)),
    'Foldable Smart Phone': ('Mobiles', (109999,)),
    'Budget 5G Phone': ('Mobiles', (24999,)),
    'Fitness Smartwatch': ('Wearables', (5999,)),
    'Smart Watch': ('Wearables', (4499, 5000)),
    'Smart Fitness Band': ('Wearables', (2999,)),
    'Gaming Console': ('Gaming', (45999,)),
    'Wireless Mouse': ('Accessories', (2499,)),
    'Smart Home Hub': ('Smart Home', (8999,)),
    'Action Camera': ('Cameras', (26999,)),
}


def init_mongodb() -> None:
    database.users.create_index('email', unique=True)
    database.password_reset_otps.create_index('email', unique=True)
    database.cart_items.create_index([('email', 1), ('name', 1)], unique=True)
    database.orders.create_index('id', unique=True)
    database.orders.create_index([('email', 1), ('createdAt', -1)])
    database.payment_attempts.create_index('razorpayOrderId', unique=True)
    database.payment_attempts.create_index('razorpayPaymentId', unique=True, sparse=True)
    database.wishlist_items.create_index([('email', 1), ('productName', 1)], unique=True)
    database.product_ratings.create_index([('email', 1), ('productName', 1)], unique=True)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 120_000)
    return f'{salt}${digest.hex()}'


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, expected_digest = stored_hash.split('$', 1)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 120_000)
    return secrets.compare_digest(digest.hex(), expected_digest)


def password_reset_otp_hash(email: str, otp: str) -> str:
    return hmac.new(
        app.secret_key.encode(),
        f'{email}:{otp}'.encode(),
        hashlib.sha256,
    ).hexdigest()


def send_password_reset_email(email: str, otp: str) -> None:
    host = os.environ.get('SMTP_HOST')
    username = os.environ.get('SMTP_USERNAME')
    password = os.environ.get('SMTP_PASSWORD')
    sender = os.environ.get('SMTP_FROM') or username
    if not host or not username or not password or not sender:
        raise RuntimeError('Email is not configured. Set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, and SMTP_FROM.')

    message = EmailMessage()
    message['Subject'] = 'Your ShopEase password reset code'
    message['From'] = sender
    message['To'] = email
    message.set_content(
        f'Your ShopEase password reset code is {otp}. '
        'It expires in 10 minutes. If you did not request this, ignore this email.'
    )

    port = int(os.environ.get('SMTP_PORT', '587'))
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=10) as smtp:
            smtp.login(username, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(username, password)
            smtp.send_message(message)


def get_cart(email: str) -> list[dict[str, Any]]:
    return [
        {key: item[key] for key in ('name', 'price', 'image', 'quantity')}
        for item in database.cart_items.find({'email': email}).sort('_id', 1)
    ]


def order_from_document(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'id': row['id'],
        'email': row['email'],
        'items': row['items'],
        'total': row['total'],
        'status': row['status'],
        'deliveryAgent': row['deliveryAgent'],
        'createdAt': row['createdAt'],
        'updatedAt': row['updatedAt'],
        'customerName': row['customerName'],
        'phone': row['phone'],
        'shippingAddress': row['shippingAddress'],
        'paymentMethod': row['paymentMethod'],
        'paymentStatus': row['paymentStatus'],
        'razorpayPaymentId': row['razorpayPaymentId'],
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def normalize_order_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list) or not items:
        raise ValueError('items must be a non-empty list')
    if len(items) > 100:
        raise ValueError('an order cannot contain more than 100 items')

    normalized_items = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('each item must be an object')
        name = str(item.get('name') or '').strip()
        catalog_entry = PRODUCT_CATALOG.get(name)
        if not catalog_entry:
            raise ValueError(f'{name or "item"} is not in the product catalogue')

        price = item.get('price')
        if isinstance(price, bool) or not isinstance(price, (int, float)):
            raise ValueError(f'{name} has an invalid price')
        try:
            numeric_price = float(price)
        except OverflowError as exc:
            raise ValueError(f'{name} has an invalid price') from exc
        if not math.isfinite(numeric_price) or not numeric_price.is_integer():
            raise ValueError(f'{name} has an invalid price')
        price = int(numeric_price)
        category, approved_prices = catalog_entry
        if price not in approved_prices:
            raise ValueError(f'{name} price does not match the product catalogue')

        quantity = item.get('quantity')
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
            raise ValueError(f'{name} quantity must be a positive integer')
        image = str(item.get('image') or '')
        if len(image) > 2048:
            raise ValueError(f'{name} image URL is too long')
        normalized_items.append({
            'name': name,
            'category': category,
            'price': price,
            'image': image,
            'quantity': quantity,
        })
    return normalized_items


def order_totals(items: list[dict[str, Any]]) -> dict[str, int]:
    subtotal = sum(item['price'] * item['quantity'] for item in items)
    tax = (subtotal * 5 + 50) // 100
    delivery = 99 if subtotal else 0
    return {
        'subtotal': subtotal,
        'tax': tax,
        'delivery': delivery,
        'total': subtotal + tax + delivery,
    }


def get_razorpay_client() -> tuple[str, Any] | None:
    key_id = os.environ.get('RAZORPAY_KEY_ID')
    key_secret = os.environ.get('RAZORPAY_KEY_SECRET')
    if not key_id or not key_secret:
        return None
    return key_id, razorpay.Client(auth=(key_id, key_secret))


init_mongodb()


@app.get('/')
def homepage():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'index.html')


@app.get('/<path:filename>')
def frontend_file(filename):
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), filename)


def normalize_user_payload(data: dict[str, Any]) -> dict[str, Any]:
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = str(data.get('password') or '').strip()
    if not name or not email or not password:
        raise ValueError('name, email, and password are required')
    if '@' not in email:
        raise ValueError('invalid email')
    if len(password) < 6:
        raise ValueError('password must be at least 6 characters')
    return {'name': name, 'email': email, 'password': password}


def resolve_user_email(email_value: str | None = None) -> str | None:
    authenticated_email = session.get('user_email')
    if not authenticated_email:
        return None
    if email_value and email_value.strip().lower() != authenticated_email:
        return None
    return authenticated_email


@app.route('/api/health', methods=['GET', 'OPTIONS'])
def health_check():
    if request.method == 'OPTIONS':
        return '', 200
    return jsonify({'status': 'ok', 'message': 'ShopEase API is running'}), 200


@app.post('/api/signup')
def signup():
    try:
        payload = request.get_json(silent=True) or {}
        user = normalize_user_payload(payload)
    except (TypeError, ValueError) as exc:
        return jsonify({'error': str(exc)}), 400

    try:
        database.users.insert_one({
            'email': user['email'],
            'name': user['name'],
            'password_hash': hash_password(user['password']),
            'created_at': utc_now(),
            'phone': '',
            'alternate_phone': '',
            'address': '',
            'addresses': [],
        })
    except DuplicateKeyError:
        return jsonify({'error': 'User already exists'}), 409

    session.clear()
    session['user_email'] = user['email']
    return jsonify({'message': 'User created successfully', 'user': {'name': user['name'], 'email': user['email']}}), 201


@app.post('/api/login')
def login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get('email') or '').strip().lower()
    password = str(payload.get('password') or '').strip()

    user = database.users.find_one(
        {'email': email}, {'name': 1, 'email': 1, 'password_hash': 1}
    )
    if not user or not verify_password(password, user['password_hash']):
        return jsonify({'error': 'Invalid email or password'}), 401

    session.clear()
    session['user_email'] = email

    return jsonify({
        'message': 'Login successful',
        'user': {'name': user['name'], 'email': user['email']},
        'cart': get_cart(email)
    }), 200


@app.post('/api/forgot-password')
def forgot_password():
    payload = request.get_json(silent=True) or {}
    email = str(payload.get('email') or '').strip().lower()
    if not email or '@' not in email:
        return jsonify({'error': 'Enter a valid email address'}), 400

    # Keep responses consistent for known and unknown accounts.
    if not all(os.environ.get(key) for key in ('SMTP_HOST', 'SMTP_USERNAME', 'SMTP_PASSWORD')):
        return jsonify({'error': 'Password reset email is not configured on this server.'}), 503

    user = database.users.find_one({'email': email}, {'email': 1})
    if user:
        existing = database.password_reset_otps.find_one({'email': email})
        now = datetime.now(timezone.utc).timestamp()
        if existing and existing.get('requested_at', 0) > now - 60:
            return jsonify({'message': 'If an account exists for this email, a reset code has been sent.'}), 200

        otp = f'{secrets.randbelow(1_000_000):06d}'
        try:
            send_password_reset_email(email, otp)
        except (OSError, smtplib.SMTPException, RuntimeError, ValueError):
            logger.exception('Could not send password reset email')
            return jsonify({'error': 'Unable to send a reset email right now. Check the email settings and try again.'}), 503

        database.password_reset_otps.replace_one(
            {'email': email},
            {
                'email': email,
                'otp_hash': password_reset_otp_hash(email, otp),
                'expires_at': now + 600,
                'requested_at': now,
                'attempts': 0,
            },
            upsert=True,
        )
    return jsonify({'message': 'If an account exists for this email, a reset code has been sent.'}), 200


@app.post('/api/reset-password')
def reset_password():
    payload = request.get_json(silent=True) or {}
    email = str(payload.get('email') or '').strip().lower()
    otp = str(payload.get('otp') or '').strip()
    new_password = str(payload.get('newPassword') or '').strip()
    if not email or '@' not in email or not otp or not new_password:
        return jsonify({'error': 'Email, verification code, and new password are required'}), 400
    if len(new_password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    reset = database.password_reset_otps.find_one({'email': email})
    now = datetime.now(timezone.utc).timestamp()
    if not reset or reset.get('expires_at', 0) <= now:
        database.password_reset_otps.delete_one({'email': email})
        return jsonify({'error': 'The code is invalid or expired. Request a new code.'}), 400
    if reset.get('attempts', 0) >= 5:
        database.password_reset_otps.delete_one({'email': email})
        return jsonify({'error': 'Too many incorrect attempts. Request a new code.'}), 429

    expected_hash = password_reset_otp_hash(email, otp)
    if not hmac.compare_digest(expected_hash, reset['otp_hash']):
        database.password_reset_otps.update_one(
            {'email': email},
            {'$inc': {'attempts': 1}},
        )
        return jsonify({'error': 'The code is invalid or expired. Request a new code.'}), 400

    result = database.users.update_one(
        {'email': email},
        {'$set': {'password_hash': hash_password(new_password)}},
    )
    database.password_reset_otps.delete_one({'email': email})
    if result.matched_count != 1:
        return jsonify({'error': 'The code is invalid or expired. Request a new code.'}), 400
    session.clear()
    return jsonify({'message': 'Password updated. Sign in with your new password.'}), 200


@app.get('/api/session')
def current_session():
    email = session.get('user_email')
    if not email:
        return jsonify({'user': None}), 200

    user = database.users.find_one({'email': email}, {'name': 1, 'email': 1})
    if not user:
        session.clear()
        return jsonify({'user': None}), 200
    return jsonify({'user': {'name': user['name'], 'email': user['email']}}), 200


@app.post('/api/logout')
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'}), 200


@app.route('/api/profile', methods=['GET', 'PUT', 'OPTIONS'])
def profile_handler():
    if request.method == 'OPTIONS':
        return '', 200

    if request.method == 'GET':
        email = resolve_user_email(request.args.get('email'))
    else:
        payload = request.get_json(silent=True) or {}
        email = resolve_user_email(payload.get('email'))

    if not email:
        return jsonify({'error': 'Authentication required or requested user does not match the session'}), 401

    user = database.users.find_one({'email': email})
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if request.method == 'PUT':
        name = str(payload.get('name', user['name']) or '').strip()
        phone = str(payload.get('phone') or '').strip()
        alternate_phone = str(payload.get('alternatePhone') or '').strip()
        if 'addresses' in payload:
            addresses = payload.get('addresses')
            if not isinstance(addresses, list):
                return jsonify({'error': 'addresses must be a list'}), 400
            addresses = [str(item or '').strip() for item in addresses]
            addresses = [item for item in addresses if item]
        elif 'address' in payload:
            address = str(payload.get('address') or '').strip()
            addresses = [address] if address else []
        else:
            addresses = user.get('addresses', [])
        address = addresses[0] if addresses else ''
        if not name:
            return jsonify({'error': 'name is required'}), 400
        database.users.update_one(
            {'email': email},
            {'$set': {
                'name': name,
                'phone': phone,
                'alternate_phone': alternate_phone,
                'address': address,
                'addresses': addresses,
            }}
        )
        user = database.users.find_one({'email': email})

    profile = {
        'name': user['name'],
        'email': user['email'],
        'phone': user['phone'],
        'alternatePhone': user['alternate_phone'],
        'address': user['address'],
        'addresses': user.get('addresses', []),
    }
    return jsonify({'profile': profile}), 200


@app.route('/api/cart', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def cart_handler():
    if request.method == 'OPTIONS':
        return '', 200

    if request.method == 'GET':
        email = resolve_user_email(request.args.get('email'))
        if not email:
            return jsonify({'error': 'Authentication required or requested user does not match the session'}), 401
        return jsonify({'cart': get_cart(email)}), 200

    payload = request.get_json(silent=True) or {}
    email = resolve_user_email(payload.get('email'))
    if not email:
        return jsonify({'error': 'Authentication required or requested user does not match the session'}), 401

    if request.method == 'POST':
        item = {
            'name': str(payload.get('name') or '').strip(),
            'price': float(payload.get('price') or 0),
            'image': str(payload.get('image') or '').strip(),
            'quantity': int(payload.get('quantity') or 1),
        }
        if not item['name']:
            return jsonify({'error': 'name is required'}), 400

        database.cart_items.update_one(
            {'email': email, 'name': item['name']},
            {
                '$set': {'price': item['price'], 'image': item['image']},
                '$inc': {'quantity': item['quantity']},
            },
            upsert=True,
        )

        return jsonify({'message': 'Item added to cart', 'cart': get_cart(email)}), 200

    if request.method == 'PUT':
        normalized_items = {}
        items = payload.get('items') or []
        for item in items:
            if not item.get('name'):
                continue
            name = str(item.get('name')).strip()
            normalized_items[name] = {
                'name': name,
                'price': float(item.get('price') or 0),
                'image': str(item.get('image') or '').strip(),
                'quantity': int(item.get('quantity') or 1),
            }
        for item in normalized_items.values():
            database.cart_items.update_one(
                {'email': email, 'name': item['name']},
                {'$set': item},
                upsert=True,
            )
        database.cart_items.delete_many({
            'email': email,
            'name': {'$nin': list(normalized_items)},
        })
        return jsonify({'message': 'Cart updated', 'cart': get_cart(email)}), 200

    if request.method == 'DELETE':
        database.cart_items.delete_many({'email': email})
        return jsonify({'message': 'Cart cleared', 'cart': []}), 200

    return jsonify({'error': 'Unsupported method'}), 405


@app.route('/api/wishlist', methods=['GET', 'PUT', 'DELETE', 'OPTIONS'])
def wishlist_handler():
    if request.method == 'OPTIONS':
        return '', 200

    if request.method == 'GET':
        email = resolve_user_email(request.args.get('email'))
        if not email:
            return jsonify({'error': 'Authentication required or requested user does not match the session'}), 401
        rows = database.wishlist_items.find({'email': email}).sort(
            [('createdAt', 1), ('productName', 1)]
        )
        return jsonify({'items': [row['product'] for row in rows]}), 200

    payload = request.get_json(silent=True) or {}
    email = resolve_user_email(payload.get('email'))
    if not email:
        return jsonify({'error': 'Authentication required or requested user does not match the session'}), 401

    if request.method == 'DELETE':
        database.wishlist_items.delete_many({'email': email})
        return jsonify({'items': []}), 200

    items = payload.get('items')
    if not isinstance(items, list):
        return jsonify({'error': 'items must be a list'}), 400

    normalized_items = {}
    for item in items:
        if not isinstance(item, dict):
            return jsonify({'error': 'each wishlist item must be an object'}), 400
        name = str(item.get('name') or '').strip()
        if not name:
            return jsonify({'error': 'each wishlist item must have a name'}), 400
        normalized_item = {**item, 'name': name}
        normalized_items[name] = normalized_item

    for name, item in normalized_items.items():
        database.wishlist_items.update_one(
            {'email': email, 'productName': name},
            {'$set': {'product': item, 'createdAt': utc_now()}},
            upsert=True,
        )
    database.wishlist_items.delete_many({
        'email': email,
        'productName': {'$nin': list(normalized_items)},
    })
    return jsonify({
        'message': 'Wishlist updated',
        'items': list(normalized_items.values())
    }), 200


@app.route('/api/ratings', methods=['GET', 'PUT', 'OPTIONS'])
def ratings_handler():
    if request.method == 'OPTIONS':
        return '', 200

    if request.method == 'GET':
        email = resolve_user_email(request.args.get('email'))
        if not email:
            return jsonify({'error': 'Authentication required or requested user does not match the session'}), 401
        rows = database.product_ratings.find({'email': email}, {'productName': 1, 'rating': 1})
        return jsonify({'ratings': {row['productName']: row['rating'] for row in rows}}), 200

    payload = request.get_json(silent=True) or {}
    email = resolve_user_email(payload.get('email'))
    if not email:
        return jsonify({'error': 'Authentication required or requested user does not match the session'}), 401
    product_name = str(payload.get('name') or '').strip()
    rating = payload.get('rating')
    if not product_name:
        return jsonify({'error': 'name is required'}), 400
    if isinstance(rating, bool) or not isinstance(rating, int) or not 1 <= rating <= 5:
        return jsonify({'error': 'rating must be an integer from 1 to 5'}), 400

    database.product_ratings.update_one(
        {'email': email, 'productName': product_name},
        {'$set': {'rating': rating, 'updatedAt': utc_now()}},
        upsert=True,
    )
    return jsonify({'message': 'Rating saved', 'name': product_name, 'rating': rating}), 200


@app.post('/api/payment/orders')
def create_razorpay_order():
    payload = request.get_json(silent=True) or {}
    email = resolve_user_email(payload.get('email'))
    if not email:
        return jsonify({'error': 'Authentication required or requested user does not match the session'}), 401
    provider = get_razorpay_client()
    if not provider:
        return jsonify({'error': 'Razorpay is not configured on the server'}), 503

    try:
        items = normalize_order_items(payload.get('items'))
        customer_name = str(payload.get('customerName') or '').strip()
        phone = str(payload.get('phone') or '').strip()
        shipping_address = str(payload.get('address') or '').strip()
        if not customer_name or not phone or not shipping_address:
            raise ValueError('customerName, phone, and address are required')
    except (TypeError, ValueError) as exc:
        return jsonify({'error': str(exc)}), 400

    totals = order_totals(items)
    key_id, client = provider
    try:
        provider_order = client.order.create(data={
            'amount': totals['total'] * 100,
            'currency': 'INR',
            'receipt': f"shopease-{secrets.token_hex(8)}",
        })
    except (BadRequestError, GatewayError, ServerError, ConnectionError, Timeout):
        return jsonify({'error': 'Razorpay could not create the payment order'}), 502

    razorpay_order_id = str(provider_order.get('id') or '')
    if (
        not razorpay_order_id
        or provider_order.get('amount') != totals['total'] * 100
        or provider_order.get('currency') != 'INR'
    ):
        return jsonify({'error': 'Razorpay returned an invalid payment order'}), 502

    created_at = utc_now()
    database.payment_attempts.insert_one({
        'razorpayOrderId': razorpay_order_id,
        'email': email,
        'items': items,
        'subtotal': totals['subtotal'],
        'tax': totals['tax'],
        'delivery': totals['delivery'],
        'total': totals['total'],
        'customerName': customer_name,
        'phone': phone,
        'shippingAddress': shipping_address,
        'status': 'created',
        'orderId': '',
        'createdAt': created_at,
        'updatedAt': created_at,
    })

    return jsonify({
        'keyId': key_id,
        'orderId': razorpay_order_id,
        'amount': totals['total'] * 100,
        'currency': 'INR',
        'items': items,
        **totals,
    }), 201


@app.post('/api/payment/verify')
def verify_razorpay_payment():
    payload = request.get_json(silent=True) or {}
    email = resolve_user_email(payload.get('email'))
    if not email:
        return jsonify({'error': 'Authentication required or requested user does not match the session'}), 401

    razorpay_order_id = str(payload.get('razorpay_order_id') or '').strip()
    razorpay_payment_id = str(payload.get('razorpay_payment_id') or '').strip()
    razorpay_signature = str(payload.get('razorpay_signature') or '').strip()
    if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
        return jsonify({'error': 'Razorpay order, payment, and signature are required'}), 400

    attempt = database.payment_attempts.find_one({
        'razorpayOrderId': razorpay_order_id,
        'email': email,
    })
    if not attempt:
        return jsonify({'error': 'Payment order not found'}), 404
    if attempt['status'] == 'paid':
        if attempt.get('razorpayPaymentId') != razorpay_payment_id:
            return jsonify({'error': 'Payment order has already been completed'}), 409
        row = database.orders.find_one({'id': attempt['orderId']})
        return jsonify({'order': order_from_document(row)}), 200
    if attempt['status'] != 'created':
        return jsonify({'error': 'Payment order is not available for verification'}), 409

    provider = get_razorpay_client()
    if not provider:
        return jsonify({'error': 'Razorpay is not configured on the server'}), 503
    _, client = provider
    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature,
        })
    except SignatureVerificationError:
        return jsonify({'error': 'Razorpay payment signature is invalid'}), 400

    try:
        payment = client.payment.fetch(razorpay_payment_id)
    except (BadRequestError, GatewayError, ServerError, ConnectionError, Timeout):
        return jsonify({'error': 'Razorpay could not verify the payment status'}), 502
    if (
        str(payment.get('order_id') or '') != razorpay_order_id
        or payment.get('status') != 'captured'
        or payment.get('amount') != attempt['total'] * 100
        or payment.get('currency') != 'INR'
    ):
        return jsonify({'error': 'Razorpay payment is not captured for the expected amount'}), 409

    order_id = f"ORD-{uuid4().hex[:12].upper()}"
    claimed_attempt = database.payment_attempts.find_one_and_update(
        {
            'razorpayOrderId': razorpay_order_id,
            'email': email,
            'status': 'created',
        },
        {
            '$set': {
                'status': 'verifying',
                'razorpayPaymentId': razorpay_payment_id,
                'orderId': order_id,
                'updatedAt': utc_now(),
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if not claimed_attempt:
        current_attempt = database.payment_attempts.find_one({
            'razorpayOrderId': razorpay_order_id,
            'email': email,
        })
        if current_attempt and current_attempt['status'] == 'paid':
            if current_attempt['razorpayPaymentId'] != razorpay_payment_id:
                return jsonify({'error': 'Payment order was completed with another payment'}), 409
            row = database.orders.find_one({'id': current_attempt['orderId']})
            return jsonify({'order': order_from_document(row)}), 200
        if (
            not current_attempt
            or current_attempt['status'] != 'verifying'
            or current_attempt.get('razorpayPaymentId') != razorpay_payment_id
        ):
            return jsonify({'error': 'Payment order is not available for verification'}), 409
        claimed_attempt = current_attempt
        order_id = current_attempt['orderId']
        existing_order = database.orders.find_one({'id': order_id})
        if existing_order:
            database.payment_attempts.update_one(
                {'razorpayOrderId': razorpay_order_id, 'status': 'verifying'},
                {'$set': {'status': 'paid', 'updatedAt': utc_now()}}
            )
            database.cart_items.delete_many({'email': email})
            return jsonify({'order': order_from_document(existing_order)}), 200

    created_at = utc_now()
    order_document = {
        'id': order_id,
        'email': email,
        'items': claimed_attempt['items'],
        'total': claimed_attempt['total'],
        'status': 'Packed',
        'deliveryAgent': 'Rahul Verma',
        'createdAt': created_at,
        'updatedAt': created_at,
        'customerName': claimed_attempt['customerName'],
        'phone': claimed_attempt['phone'],
        'shippingAddress': claimed_attempt['shippingAddress'],
        'paymentMethod': 'Razorpay',
        'paymentStatus': 'paid',
        'razorpayPaymentId': razorpay_payment_id,
    }
    try:
        database.orders.insert_one(dict(order_document))
    except DuplicateKeyError:
        existing_order = database.orders.find_one({
            'id': order_id,
            'email': email,
            'razorpayPaymentId': razorpay_payment_id,
        })
        if not existing_order:
            raise
        order_document = existing_order
    database.payment_attempts.update_one(
        {'razorpayOrderId': razorpay_order_id, 'status': 'verifying'},
        {'$set': {'status': 'paid', 'updatedAt': utc_now()}}
    )
    database.cart_items.delete_many({'email': email})
    order = order_from_document(order_document)

    return jsonify({'order': order}), 200


@app.route('/api/orders', methods=['GET', 'POST', 'OPTIONS'])
def orders_handler():
    if request.method == 'OPTIONS':
        return '', 200

    if request.method == 'GET':
        email = resolve_user_email(request.args.get('email'))
        if not email:
            return jsonify({'error': 'Authentication required or requested user does not match the session'}), 401
        rows = database.orders.find({'email': email}).sort('createdAt', -1)
        return jsonify({'orders': [order_from_document(row) for row in rows]}), 200

    payload = request.get_json(silent=True) or {}
    email = resolve_user_email(payload.get('email'))
    if not email:
        return jsonify({'error': 'Authentication required or requested user does not match the session'}), 401

    if payload.get('paymentMethod') != 'Cash on delivery':
        return jsonify({'error': 'Use Razorpay checkout for prepaid orders'}), 400
    try:
        items = normalize_order_items(payload.get('items'))
        customer_name = str(payload.get('customerName') or '').strip()
        phone = str(payload.get('phone') or '').strip()
        shipping_address = str(payload.get('address') or '').strip()
        if not customer_name or not phone or not shipping_address:
            raise ValueError('customerName, phone, and address are required')
    except (TypeError, ValueError) as exc:
        return jsonify({'error': str(exc)}), 400

    totals = order_totals(items)
    order_id = f"ORD-{uuid4().hex[:12].upper()}"
    created_at = utc_now()
    order = {
        'id': order_id,
        'email': email,
        'items': items,
        'total': totals['total'],
        'status': 'Packed',
        'deliveryAgent': payload.get('deliveryAgent') or 'Rahul Verma',
        'createdAt': created_at,
        'updatedAt': created_at,
        'customerName': customer_name,
        'phone': phone,
        'shippingAddress': shipping_address,
        'paymentMethod': 'Cash on delivery',
        'paymentStatus': 'pending',
        'razorpayPaymentId': '',
    }
    database.orders.insert_one(dict(order))
    database.cart_items.delete_many({'email': email})
    return jsonify({'message': 'Order created successfully', 'order': order}), 201


@app.route('/api/orders/<order_id>/status', methods=['PATCH', 'OPTIONS'])
def update_order_status(order_id):
    if request.method == 'OPTIONS':
        return '', 200

    email = resolve_user_email()
    if not email:
        return jsonify({'error': 'Authentication required'}), 401

    payload = request.get_json(silent=True) or {}
    status = str(payload.get('status') or '').strip()
    if not status:
        return jsonify({'error': 'status is required'}), 400
    if status not in VALID_ORDER_STATUSES:
        return jsonify({'error': 'invalid status'}), 400

    row = database.orders.find_one({'id': order_id, 'email': email})
    if row:
        order = order_from_document(row)
        current_status = order.get('status', 'Packed')
        current_rank = STATUS_RANK.get(current_status, -1)
        next_rank = STATUS_RANK.get(status, -1)

        valid_transition = False
        if status == current_status:
            valid_transition = True
        elif current_status in {'Delivered', 'Return Requested', 'Replacement Requested', 'Refund Processing', 'Refunded', 'Returned'}:
            allowed = {
                'Delivered': {'Return Requested', 'Replacement Requested'},
                'Return Requested': {'Refund Processing'},
                'Replacement Requested': {'Returned'},
                'Refund Processing': {'Refunded'},
                'Refunded': set(),
                'Returned': set(),
            }
            valid_transition = status in allowed.get(current_status, set())
        elif next_rank > current_rank:
            valid_transition = True

        if not valid_transition:
            return jsonify({
                'error': f'Invalid status transition from {current_status} to {status}'
            }), 400
        updated_at = utc_now()
        delivery_agent = payload.get('deliveryAgent') or order['deliveryAgent']
        database.orders.update_one(
            {'id': order_id, 'email': email},
            {'$set': {
                'status': status,
                'updatedAt': updated_at,
                'deliveryAgent': delivery_agent,
            }}
        )
        order['status'] = status
        order['updatedAt'] = updated_at
        order['deliveryAgent'] = delivery_agent
        return jsonify({'message': 'Order status updated', 'order': order}), 200

    return jsonify({'error': 'Order not found'}), 404


@app.route('/api/orders/<order_id>', methods=['GET', 'OPTIONS'])
def get_order(order_id):
    if request.method == 'OPTIONS':
        return '', 200
    email = resolve_user_email()
    if not email:
        return jsonify({'error': 'Authentication required'}), 401
    row = database.orders.find_one({'id': order_id, 'email': email})
    if row:
        return jsonify({'order': order_from_document(row)}), 200
    return jsonify({'error': 'Order not found'}), 404


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG') == '1')
#-------------optional Run---------------------------#
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
