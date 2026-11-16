from uuid import uuid4

import app as backend
from app import app


def test_health_check():
    client = app.test_client()
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.get_json()['status'] == 'ok'


def test_signup_and_login_flow():
    client = app.test_client()
    payload = {
        'name': 'Test User',
        'email': 'testuser@example.com',
        'password': 'secret123'
    }

    signup = client.post('/api/signup', json=payload)
    assert signup.status_code == 201
    assert signup.get_json()['user']['email'] == payload['email']

    login = client.post('/api/login', json={
        'email': payload['email'],
        'password': payload['password']
    })
    assert login.status_code == 200
    assert login.get_json()['user']['email'] == payload['email']
    assert client.get('/api/session').get_json()['user']['email'] == payload['email']
    assert client.post('/api/logout').status_code == 200
    assert client.get('/api/session').get_json()['user'] is None


def test_password_reset_uses_email_code_and_code_is_single_use(monkeypatch):
    sent_emails = []
    monkeypatch.setenv('SMTP_HOST', 'smtp.example.com')
    monkeypatch.setenv('SMTP_USERNAME', 'shop@example.com')
    monkeypatch.setenv('SMTP_PASSWORD', 'smtp-password')
    monkeypatch.setattr(
        backend,
        'send_password_reset_email',
        lambda email, otp: sent_emails.append((email, otp)),
    )
    client = app.test_client()
    email = f'reset-{uuid4().hex}@example.com'
    assert client.post('/api/signup', json={
        'name': 'Reset User',
        'email': email,
        'password': 'old-password'
    }).status_code == 201

    requested = client.post('/api/forgot-password', json={'email': email})
    assert requested.status_code == 200
    assert sent_emails[0][0] == email
    otp = sent_emails[0][1]

    invalid = client.post('/api/reset-password', json={
        'email': email,
        'otp': '000000' if otp != '000000' else '000001',
        'newPassword': 'new-password'
    })
    assert invalid.status_code == 400
    changed = client.post('/api/reset-password', json={
        'email': email,
        'otp': otp,
        'newPassword': 'new-password'
    })
    assert changed.status_code == 200
    assert client.post('/api/reset-password', json={
        'email': email,
        'otp': otp,
        'newPassword': 'another-password'
    }).status_code == 400
    assert client.post('/api/login', json={
        'email': email,
        'password': 'old-password'
    }).status_code == 401
    assert client.post('/api/login', json={
        'email': email,
        'password': 'new-password'
    }).status_code == 200


def test_password_reset_rejects_expired_code(monkeypatch):
    monkeypatch.setenv('SMTP_HOST', 'smtp.example.com')
    monkeypatch.setenv('SMTP_USERNAME', 'shop@example.com')
    monkeypatch.setenv('SMTP_PASSWORD', 'smtp-password')
    monkeypatch.setattr(backend, 'send_password_reset_email', lambda email, otp: None)
    email = f'expired-{uuid4().hex}@example.com'
    client = app.test_client()
    client.post('/api/signup', json={
        'name': 'Expired User',
        'email': email,
        'password': 'old-password'
    })
    client.post('/api/forgot-password', json={'email': email})
    backend.database.password_reset_otps.update_one(
        {'email': email},
        {'$set': {'expires_at': 0}},
    )
    response = client.post('/api/reset-password', json={
        'email': email,
        'otp': '123456',
        'newPassword': 'new-password'
    })
    assert response.status_code == 400


def test_account_data_requires_authenticated_matching_user():
    client = app.test_client()
    assert client.get('/api/cart').status_code == 401
    first_email = f'first-{uuid4().hex}@example.com'
    second_email = f'second-{uuid4().hex}@example.com'
    for email in (first_email, second_email):
        response = client.post('/api/signup', json={
            'name': 'Test User',
            'email': email,
            'password': 'secret123'
        })
        assert response.status_code == 201

    client.post('/api/login', json={
        'email': first_email,
        'password': 'secret123'
    })
    assert client.get(f'/api/profile?email={second_email}').status_code == 401
    assert client.get('/api/profile').status_code == 200


def test_order_details_and_status_are_limited_to_the_owner():
    owner = app.test_client()
    owner_email = f'owner-{uuid4().hex}@example.com'
    owner.post('/api/signup', json={
        'name': 'Order Owner',
        'email': owner_email,
        'password': 'secret123'
    })
    created = owner.post('/api/orders', json={
        'paymentMethod': 'Cash on delivery',
        'customerName': 'Order Owner',
        'phone': '9876543210',
        'address': '12 Market Road, Bengaluru',
        'items': [{'name': 'Smartphone', 'price': 100000, 'quantity': 1}]
    })
    assert created.status_code == 201
    order_id = created.get_json()['order']['id']

    other_user = app.test_client()
    other_user.post('/api/signup', json={
        'name': 'Other User',
        'email': f'other-{uuid4().hex}@example.com',
        'password': 'secret123'
    })
    assert other_user.get(f'/api/orders/{order_id}').status_code == 404
    assert other_user.patch(
        f'/api/orders/{order_id}/status',
        json={'status': 'Delivered'}
    ).status_code == 404


def test_wishlist_and_ratings_persist_per_user():
    client = app.test_client()
    email = f'products-{uuid4().hex}@example.com'
    assert client.get('/api/wishlist').status_code == 401
    client.post('/api/signup', json={
        'name': 'Product User',
        'email': email,
        'password': 'secret123'
    })

    product = {
        'name': 'Wireless Headphones',
        'category': 'Audio',
        'price': 20000,
        'image': 'https://example.com/headphones.jpg'
    }
    saved_wishlist = client.put('/api/wishlist', json={
        'email': email,
        'items': [product]
    })
    assert saved_wishlist.status_code == 200
    assert client.get(f'/api/wishlist?email={email}').get_json()['items'] == [product]

    assert client.put('/api/ratings', json={
        'email': email,
        'name': product['name'],
        'rating': 6
    }).status_code == 400
    saved_rating = client.put('/api/ratings', json={
        'email': email,
        'name': product['name'],
        'rating': 5
    })
    assert saved_rating.status_code == 200
    assert client.get(f'/api/ratings?email={email}').get_json()['ratings'] == {
        product['name']: 5
    }


def test_profile_details_can_be_saved_and_reloaded():
    client = app.test_client()
    email = f'profile-{uuid4().hex}@example.com'
    signup = client.post('/api/signup', json={
        'name': 'Profile User',
        'email': email,
        'password': 'secret123'
    })
    assert signup.status_code == 201

    details = {
        'email': email,
        'name': 'Updated Profile User',
        'phone': '9876543210',
        'alternatePhone': '9123456780',
        'address': '12 Market Road, Bengaluru',
        'addresses': ['12 Market Road, Bengaluru', '8 Lake View, Bengaluru']
    }
    saved = client.put('/api/profile', json=details)
    assert saved.status_code == 200
    assert saved.get_json()['profile']['alternatePhone'] == details['alternatePhone']

    loaded = client.get(f'/api/profile?email={email}')
    assert loaded.status_code == 200
    assert loaded.get_json()['profile'] == {
        'name': details['name'],
        'email': email,
        'phone': details['phone'],
        'alternatePhone': details['alternatePhone'],
        'address': details['address'],
        'addresses': details['addresses']
    }


def test_cart_endpoints_for_logged_in_user():
    client = app.test_client()
    email = 'cartuser@example.com'
    client.post('/api/signup', json={
        'name': 'Cart User',
        'email': email,
        'password': 'secret123'
    })
    client.post('/api/login', json={
        'email': email,
        'password': 'secret123'
    })

    add = client.post('/api/cart', json={
        'name': 'Apple Laptop',
        'price': 120000,
        'image': 'https://example.com/laptop.jpg',
        'quantity': 1
    })
    assert add.status_code == 200
    data = add.get_json()
    assert data['cart'][0]['name'] == 'Apple Laptop'

    items = client.get('/api/cart')
    assert items.status_code == 200
    assert len(items.get_json()['cart']) >= 1


def test_order_creation_and_status_updates():
    client = app.test_client()
    email = 'ordersuser@example.com'
    client.post('/api/signup', json={
        'name': 'Order User',
        'email': email,
        'password': 'secret123'
    })

    create = client.post('/api/orders', json={
        'email': email,
        'items': [{'name': 'Smartphone', 'price': 100000, 'quantity': 1, 'image': 'https://example.com/phone.jpg'}],
        'paymentMethod': 'Cash on delivery',
        'customerName': 'Order User',
        'phone': '9876543210',
        'address': '12 Market Road, Bengaluru'
    })
    assert create.status_code == 201
    order = create.get_json()['order']
    assert order['status'] == 'Packed'
    assert order['total'] == 105099
    assert order['paymentStatus'] == 'pending'

    dispatched = client.patch(f"/api/orders/{order['id']}/status", json={'status': 'Dispatched'})
    assert dispatched.status_code == 200
    update = client.patch(f"/api/orders/{order['id']}/status", json={'status': 'Out for Delivery'})
    assert update.status_code == 200
    assert update.get_json()['order']['status'] == 'Out for Delivery'

    deliver = client.patch(f"/api/orders/{order['id']}/status", json={'status': 'Delivered'})
    assert deliver.status_code == 200
    assert deliver.get_json()['order']['status'] == 'Delivered'

    return_requested = client.patch(f"/api/orders/{order['id']}/status", json={'status': 'Return Requested'})
    assert return_requested.status_code == 200
    assert return_requested.get_json()['order']['status'] == 'Return Requested'

    refund = client.patch(f"/api/orders/{order['id']}/status", json={'status': 'Refund Processing'})
    assert refund.status_code == 200
    assert refund.get_json()['order']['status'] == 'Refund Processing'

    list_orders = client.get(f'/api/orders?email={email}')
    assert list_orders.status_code == 200
    assert len(list_orders.get_json()['orders']) >= 1


def test_razorpay_payment_is_verified_before_order_creation(monkeypatch):
    client = app.test_client()
    email = f'payment-{uuid4().hex}@example.com'
    client.post('/api/signup', json={
        'name': 'Payment User',
        'email': email,
        'password': 'secret123'
    })

    class FakeOrderAPI:
        def create(self, data):
            self.amount = data['amount']
            return {'id': 'order_test_123', **data}

    class FakePaymentAPI:
        def fetch(self, payment_id):
            return {
                'id': payment_id,
                'order_id': 'order_test_123',
                'amount': 10509900,
                'currency': 'INR',
                'status': 'captured'
            }

    class FakeUtilityAPI:
        def verify_payment_signature(self, parameters):
            if parameters['razorpay_signature'] == 'invalid':
                raise backend.SignatureVerificationError()
            return True

    class FakeRazorpayClient:
        def __init__(self):
            self.order = FakeOrderAPI()
            self.payment = FakePaymentAPI()
            self.utility = FakeUtilityAPI()

    fake_client = FakeRazorpayClient()
    monkeypatch.setattr(backend, 'get_razorpay_client', lambda: ('rzp_test_key', fake_client))
    payment_order = client.post('/api/payment/orders', json={
        'email': email,
        'items': [{'name': 'Smartphone', 'price': 100000, 'quantity': 1}],
        'customerName': 'Payment User',
        'phone': '9876543210',
        'address': '12 Market Road, Bengaluru'
    })
    assert payment_order.status_code == 201
    assert payment_order.get_json()['amount'] == 10509900

    bad_price = client.post('/api/payment/orders', json={
        'email': email,
        'items': [{'name': 'Smartphone', 'price': 1, 'quantity': 1}],
        'customerName': 'Payment User',
        'phone': '9876543210',
        'address': '12 Market Road, Bengaluru'
    })
    assert bad_price.status_code == 400

    invalid_signature = client.post('/api/payment/verify', json={
        'email': email,
        'razorpay_order_id': 'order_test_123',
        'razorpay_payment_id': 'pay_test_123',
        'razorpay_signature': 'invalid'
    })
    assert invalid_signature.status_code == 400

    verification = client.post('/api/payment/verify', json={
        'email': email,
        'razorpay_order_id': 'order_test_123',
        'razorpay_payment_id': 'pay_test_123',
        'razorpay_signature': 'verified-by-the-provider'
    })
    assert verification.status_code == 200
    order = verification.get_json()['order']
    assert order['paymentMethod'] == 'Razorpay'
    assert order['paymentStatus'] == 'paid'
    assert order['razorpayPaymentId'] == 'pay_test_123'

    repeated_verification = client.post('/api/payment/verify', json={
        'email': email,
        'razorpay_order_id': 'order_test_123',
        'razorpay_payment_id': 'pay_test_123',
        'razorpay_signature': 'verified-by-the-provider'
    })
    assert repeated_verification.status_code == 200
    assert repeated_verification.get_json()['order']['id'] == order['id']


def test_razorpay_checkout_requires_server_credentials(monkeypatch):
    client = app.test_client()
    email = f'no-keys-{uuid4().hex}@example.com'
    client.post('/api/signup', json={
        'name': 'No Keys User',
        'email': email,
        'password': 'secret123'
    })
    monkeypatch.delenv('RAZORPAY_KEY_ID', raising=False)
    monkeypatch.delenv('RAZORPAY_KEY_SECRET', raising=False)

    response = client.post('/api/payment/orders', json={
        'email': email,
        'items': [{'name': 'Smartphone', 'price': 100000, 'quantity': 1}],
        'customerName': 'No Keys User',
        'phone': '9876543210',
        'address': '12 Market Road, Bengaluru'
    })
    assert response.status_code == 503


def test_uncaptured_razorpay_payment_does_not_create_order(monkeypatch):
    client = app.test_client()
    email = f'uncaptured-{uuid4().hex}@example.com'
    client.post('/api/signup', json={
        'name': 'Uncaptured User',
        'email': email,
        'password': 'secret123'
    })

    class FakeOrderAPI:
        def create(self, data):
            return {'id': 'order_uncaptured_123', **data}

    class FakePaymentAPI:
        def fetch(self, payment_id):
            return {
                'id': payment_id,
                'order_id': 'order_uncaptured_123',
                'amount': 10509900,
                'currency': 'INR',
                'status': 'authorized'
            }

    class FakeUtilityAPI:
        def verify_payment_signature(self, parameters):
            return True

    class FakeRazorpayClient:
        def __init__(self):
            self.order = FakeOrderAPI()
            self.payment = FakePaymentAPI()
            self.utility = FakeUtilityAPI()

    monkeypatch.setattr(
        backend,
        'get_razorpay_client',
        lambda: ('rzp_test_key', FakeRazorpayClient())
    )
    payment_order = client.post('/api/payment/orders', json={
        'email': email,
        'items': [{'name': 'Smartphone', 'price': 100000, 'quantity': 1}],
        'customerName': 'Uncaptured User',
        'phone': '9876543210',
        'address': '12 Market Road, Bengaluru'
    })
    assert payment_order.status_code == 201

    verification = client.post('/api/payment/verify', json={
        'email': email,
        'razorpay_order_id': 'order_uncaptured_123',
        'razorpay_payment_id': 'pay_uncaptured_123',
        'razorpay_signature': 'valid-signature'
    })
    assert verification.status_code == 409
    assert verification.get_json()['error'] == 'Razorpay payment is not captured for the expected amount'

    orders = client.get(f'/api/orders?email={email}')
    assert orders.status_code == 200
    assert orders.get_json()['orders'] == []
