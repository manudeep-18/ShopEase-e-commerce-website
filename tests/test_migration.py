import sqlite3

import app
from migrate_sqlite_to_mongodb import migrate


def test_sqlite_migration_copies_records_and_is_safe_to_rerun(tmp_path):
    source = tmp_path / 'legacy.db'
    connection = sqlite3.connect(source)
    connection.executescript('''
        CREATE TABLE users (
            email TEXT PRIMARY KEY, name TEXT NOT NULL, password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL, phone TEXT NOT NULL DEFAULT '',
            alternate_phone TEXT NOT NULL DEFAULT '', address TEXT NOT NULL DEFAULT '',
            addresses_json TEXT NOT NULL DEFAULT '[]'
        );
        CREATE TABLE cart_items (
            id INTEGER PRIMARY KEY, email TEXT, name TEXT, price REAL, image TEXT, quantity INTEGER
        );
        CREATE TABLE orders (
            id TEXT PRIMARY KEY, email TEXT, items_json TEXT, total REAL, status TEXT,
            delivery_agent TEXT, created_at TEXT, updated_at TEXT,
            customer_name TEXT, phone TEXT, shipping_address TEXT, payment_method TEXT,
            payment_status TEXT, razorpay_payment_id TEXT
        );
        CREATE TABLE payment_attempts (
            razorpay_order_id TEXT PRIMARY KEY, email TEXT, items_json TEXT, subtotal INTEGER,
            tax INTEGER, delivery INTEGER, total INTEGER, customer_name TEXT, phone TEXT,
            shipping_address TEXT, status TEXT, razorpay_payment_id TEXT, order_id TEXT,
            created_at TEXT, updated_at TEXT
        );
        CREATE TABLE wishlist_items (
            email TEXT, product_name TEXT, product_json TEXT, created_at TEXT
        );
        CREATE TABLE product_ratings (
            email TEXT, product_name TEXT, rating INTEGER, updated_at TEXT
        );
        INSERT INTO users VALUES (
            'legacy@example.com', 'Legacy User', 'hash', '2026-01-01T00:00:00Z',
            '123', '', 'Somewhere', '["Somewhere", "Elsewhere"]'
        );
        INSERT INTO cart_items VALUES (1, 'legacy@example.com', 'Headphones', 20, '', 2);
        INSERT INTO orders VALUES (
            'ORD-LEGACY', 'legacy@example.com', '[{"name":"Headphones"}]', 20, 'Packed',
            'Agent', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z',
            'Legacy User', '123', 'Somewhere', 'Cash on delivery', 'pending', ''
        );
        INSERT INTO payment_attempts VALUES (
            'pay-order-legacy', 'legacy@example.com', '[{"name":"Headphones"}]',
            20, 1, 99, 120, 'Legacy User', '123', 'Somewhere', 'created',
            NULL, NULL, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'
        );
        INSERT INTO wishlist_items VALUES (
            'legacy@example.com', 'Headphones', '{"name":"Headphones"}', '2026-01-01T00:00:00Z'
        );
        INSERT INTO product_ratings VALUES (
            'legacy@example.com', 'Headphones', 5, '2026-01-01T00:00:00Z'
        );
    ''')
    connection.commit()
    connection.close()

    counts = migrate(str(source))
    assert counts == {
        'users': 1,
        'cart_items': 1,
        'orders': 1,
        'payment_attempts': 1,
        'wishlist_items': 1,
        'product_ratings': 1,
    }
    assert app.database.users.find_one({'email': 'legacy@example.com'})['addresses'] == [
        'Somewhere', 'Elsewhere'
    ]
    assert app.database.orders.find_one({'id': 'ORD-LEGACY'})['items'] == [
        {'name': 'Headphones'}
    ]
    assert migrate(str(source)) == {
        'users': 0,
        'cart_items': 0,
        'orders': 0,
        'payment_attempts': 0,
        'wishlist_items': 0,
        'product_ratings': 0,
    }
    assert source.exists()
