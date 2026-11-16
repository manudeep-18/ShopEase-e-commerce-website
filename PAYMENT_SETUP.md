# Razorpay checkout setup

1. Install the project dependencies with `pip install -r requirements.txt`.
2. Create Razorpay test keys in the Razorpay Dashboard and set these variables in the server environment:
   - `RAZORPAY_KEY_ID`
   - `RAZORPAY_KEY_SECRET`
   - `FLASK_SECRET_KEY` (a long, random value used to sign login sessions)
3. Run the Flask app and test a card or UPI payment using Razorpay's test payment details. Never put the key secret in browser code or commit it to the repository.
4. Enable automatic payment capture in the Razorpay Dashboard. The server only creates an order after Razorpay reports that the payment is captured.
5. For HTTPS deployments, set `FLASK_SESSION_COOKIE_SECURE=1`. Keep it unset or `0` for local HTTP development.

The server validates checkout items against `PRODUCT_CATALOG` in `app.py` and calculates tax and delivery charges itself. Update that catalogue when product names or prices change in the storefront. The backend integration tests use a mocked Razorpay client and do not make live charges.

Card number, expiry, CVV, and bank verification are handled in Razorpay's secure checkout rather than collected or stored by ShopEase. The payment chooser lets customers select card, UPI/QR, netbanking, wallet, or pay-later, then opens Razorpay Checkout filtered to that category. The exact choices depend on the Razorpay account and device. UPI ID collection is restricted for many merchant/payment flows, so checkout may offer an app or QR flow instead. Enable and configure the desired methods in the Razorpay Dashboard. ShopEase verifies captured payments with Razorpay before creating a paid order.
