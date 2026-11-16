# ShopEase assistant and email OTP setup

## Shopping assistant

The floating assistant appears only for signed-in customers; it is omitted from
the login and signup pages, and its API endpoints reject logged-out requests.
The browser sends chat messages only to Flask at `/api/assistant/chat`; Groq
credentials stay on the server. With no Groq key, the endpoint uses an offline,
catalogue-backed rule-based assistant.

The assistant reads categories and products from MongoDB's `products`
collection. On startup it inserts any missing entries from the existing
ShopEase catalogue without overwriting existing product data. Budget searches
and comparisons use those database records, and the latest-order flow is scoped
to the signed-in customer. Optional product details such as discounts, ratings,
specifications, and stock are shown only when available in the database; absent
details are labeled as not listed.

For local configuration, install the requirements and copy `.env.example` to
`.env` in the project root only if you do not already have a `.env` file:

```powershell
python -m pip install -r requirements.txt
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item .env.example .env
}
```

Fill in the values you need. `python-dotenv` loads this file when Flask starts;
process environment variables take precedence. `.env` is Git-ignored and must
not be committed or shared.

To enable Groq:

1. Create an API key in the Groq console at <https://console.groq.com/keys>.
2. Set `GROQ_API_KEY` in the environment where Flask starts. Never put the key
   in HTML, JavaScript, source control, or a browser setting.
3. Optionally set `GROQ_MODEL`. The default is
   `llama-3.3-70b-versatile`; `llama-3.1-8b-instant` is a smaller option.
   Model availability and names change; confirm the current choices at
   <https://console.groq.com/docs/models>.
4. Restart Flask. The app has an in-memory limit of 20 assistant messages per
   session/IP in a 10-minute window. If Groq is unavailable, the application
   falls back to local catalogue rules.

PowerShell example:

```powershell
$env:GROQ_API_KEY = "your-groq-api-key"
$env:GROQ_MODEL = "llama-3.3-70b-versatile"
python app.py
```

`GROQ_API_KEY` is optional. Do not send customer records to a third-party model
unless your deployment's privacy practices and applicable terms permit it. The
backend includes only the signed-in user's own cart and a small set of their
recent order IDs/statuses in the assistant context. Product cards are built
server-side from the MongoDB catalogue.

The assistant is a prototype feature, not a source of live inventory or
delivery estimates. The database is seeded from the project's existing static
catalogue; update product records in MongoDB when adding or changing listings.

## SMTP and one-time codes

Signup email verification and password reset use the existing SMTP settings:

```powershell
$env:SMTP_HOST = "smtp.gmail.com"
$env:SMTP_PORT = "587"
$env:SMTP_USERNAME = "your-email@gmail.com"
$env:SMTP_PASSWORD = "your-google-app-password"
$env:SMTP_FROM = "your-email@gmail.com"
```

For Gmail, enable 2-Step Verification and create an App Password in your Google
Account security settings. Use that App Password, not your normal account
password. Keep all SMTP credentials private and out of source control. The
sender uses STARTTLS and a 10-second connection timeout. Signup and reset codes
are six digits, expire after 10 minutes, are stored as HMAC-SHA256 hashes, and
are invalidated after use or five incorrect attempts. Resends have a 60-second
cooldown and are limited to five requests per email per hour.

The `LOGIN_OTP_ENABLED` environment setting is reserved for the optional
second-step login flow. It defaults to disabled; the current login flow does
not request or verify a login OTP.

## Tests

Run the API and assistant/OTP tests with:

```powershell
python -m pytest
```

Tests use `mongomock`, replace the email sender, and stub the Groq request. They
do not send email or make live Groq requests. Dotenv loading is disabled by the
test configuration, so the suite does not depend on a developer's `.env`.
