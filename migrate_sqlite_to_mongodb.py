from __future__ import annotations

import argparse
import json
import os
import sqlite3
from app import database


def legacy_rows(connection: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    return connection.execute(f'SELECT * FROM {table}').fetchall()


def migrate(source_path: str) -> dict[str, int]:
    if not os.path.isfile(source_path):
        raise FileNotFoundError(f'SQLite backup not found: {source_path}')

    connection = sqlite3.connect(source_path)
    connection.row_factory = sqlite3.Row
    migrated: dict[str, int] = {}
    try:
        for row in legacy_rows(connection, 'users'):
            document = dict(row)
            addresses_value = document.pop('addresses_json', '[]') or '[]'
            document['addresses'] = json.loads(addresses_value)
            document.pop('id', None)
            result = database.users.update_one(
                {'email': document['email']},
                {'$setOnInsert': document},
                upsert=True,
            )
            migrated['users'] = migrated.get('users', 0) + (result.upserted_id is not None)

        for row in legacy_rows(connection, 'cart_items'):
            document = dict(row)
            document.pop('id', None)
            key = {'email': document.pop('email'), 'name': document.pop('name')}
            result = database.cart_items.update_one(
                key,
                {'$setOnInsert': {**key, **document}},
                upsert=True,
            )
            migrated['cart_items'] = migrated.get('cart_items', 0) + (result.upserted_id is not None)

        for row in legacy_rows(connection, 'orders'):
            old = dict(row)
            document = {
                'id': old['id'],
                'email': old['email'],
                'items': json.loads(old['items_json']),
                'total': old['total'],
                'status': old['status'],
                'deliveryAgent': old['delivery_agent'],
                'createdAt': old['created_at'],
                'updatedAt': old['updated_at'],
                'customerName': old.get('customer_name') or '',
                'phone': old.get('phone') or '',
                'shippingAddress': old.get('shipping_address') or '',
                'paymentMethod': old.get('payment_method') or '',
                'paymentStatus': old.get('payment_status') or 'unknown',
                'razorpayPaymentId': old.get('razorpay_payment_id') or '',
            }
            result = database.orders.update_one(
                {'id': document['id']},
                {'$setOnInsert': document},
                upsert=True,
            )
            migrated['orders'] = migrated.get('orders', 0) + (result.upserted_id is not None)

        for row in legacy_rows(connection, 'payment_attempts'):
            old = dict(row)
            document = {
                'razorpayOrderId': old['razorpay_order_id'],
                'email': old['email'],
                'items': json.loads(old['items_json']),
                'subtotal': old['subtotal'],
                'tax': old['tax'],
                'delivery': old['delivery'],
                'total': old['total'],
                'customerName': old['customer_name'],
                'phone': old['phone'],
                'shippingAddress': old['shipping_address'],
                'status': old['status'],
                'createdAt': old['created_at'],
                'updatedAt': old['updated_at'],
            }
            if old.get('razorpay_payment_id'):
                document['razorpayPaymentId'] = old['razorpay_payment_id']
            if old.get('order_id'):
                document['orderId'] = old['order_id']
            result = database.payment_attempts.update_one(
                {'razorpayOrderId': document['razorpayOrderId']},
                {'$setOnInsert': document},
                upsert=True,
            )
            migrated['payment_attempts'] = migrated.get('payment_attempts', 0) + (result.upserted_id is not None)

        for row in legacy_rows(connection, 'wishlist_items'):
            old = dict(row)
            document = {
                'email': old['email'],
                'productName': old['product_name'],
                'product': json.loads(old['product_json']),
                'createdAt': old['created_at'],
            }
            result = database.wishlist_items.update_one(
                {'email': document['email'], 'productName': document['productName']},
                {'$setOnInsert': document},
                upsert=True,
            )
            migrated['wishlist_items'] = migrated.get('wishlist_items', 0) + (result.upserted_id is not None)

        for row in legacy_rows(connection, 'product_ratings'):
            old = dict(row)
            document = {
                'email': old['email'],
                'productName': old['product_name'],
                'rating': old['rating'],
                'updatedAt': old['updated_at'],
            }
            result = database.product_ratings.update_one(
                {'email': document['email'], 'productName': document['productName']},
                {'$setOnInsert': document},
                upsert=True,
            )
            migrated['product_ratings'] = migrated.get('product_ratings', 0) + (result.upserted_id is not None)
    finally:
        connection.close()
    return migrated


def main() -> None:
    parser = argparse.ArgumentParser(description='Copy ShopEase SQLite data into MongoDB.')
    parser.add_argument(
        '--source',
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shopease.db'),
        help='Path to the SQLite backup file (default: shopease.db beside this script)',
    )
    arguments = parser.parse_args()
    counts = migrate(arguments.source)
    for collection, count in counts.items():
        print(f'{collection}: {count} new document(s) copied')
    print('Migration complete. The SQLite source file was not changed.')


if __name__ == '__main__':
    main()
