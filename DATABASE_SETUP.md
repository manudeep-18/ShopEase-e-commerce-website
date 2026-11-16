# Database setup

ShopEase connects to a local MongoDB server at `mongodb://localhost:27017` by default. To use another MongoDB server, set `MONGODB_URI` in the shell before starting the app. The previous `shopease.db` SQLite file is left untouched as a backup and is not used by the Flask app.

## Configure environment variables with `.env`

Install the requirements, then copy the example file in the project root and
replace its placeholders with your own values:

```powershell
python -m pip install -r requirements.txt
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item .env.example .env
} else {
    Write-Host ".env already exists; edit it without overwriting it."
}
```

The app loads `.env` with `python-dotenv` at startup. Values already set in the
process environment take precedence. Keep your local `.env` private; it is
ignored by Git. Never commit or share the file.

## Run locally without a MongoDB server

For temporary in-memory data, explicitly enable the test mock:

```powershell
$env:MONGO_MOCK_FOR_TESTS = "1"
python app.py
```

Mock data is cleared when the app stops.

## Connect to a local MongoDB

Install and start MongoDB Community Server locally. The default connection uses `mongodb://localhost:27017`, so no additional configuration is needed. To select a different connection string, set it in the shell before starting the app. For example, in PowerShell:

```powershell
$env:MONGODB_URI = "mongodb://localhost:27017"
$env:MONGODB_DATABASE = "shopease"
python app.py
```

## Connect to MongoDB Atlas

In Atlas, create a database user and allow your current public IP under **Network Access**. If connected to a VPN, Atlas must allow the VPN's public exit IP. In **Connect → Drivers**, copy the connection string and replace its username, password, and cluster host with your Atlas values. URL-encode special characters in the database user's password.

In Command Prompt, set the connection string in the same window where you start the app:

```cmd
set "MONGODB_URI=mongodb+srv://DB_USER:URL_ENCODED_PASSWORD@CLUSTER_HOST/?retryWrites=true&w=majority&appName=ShopEase"
set "MONGODB_DATABASE=shopease"
python app.py
```

Replace `DB_USER`, `URL_ENCODED_PASSWORD`, and `CLUSTER_HOST`; do not type those placeholder values literally. Keep the connection string private. Connection errors are reported rather than silently switching databases.

The app creates its MongoDB indexes on startup.
The startup indexes include a unique email/purpose key for OTP records and a
TTL index on their `expires_at` field.

The shopping assistant uses the MongoDB `products` collection. On startup,
missing catalogue entries are seeded from ShopEase's existing product
catalogue; existing product documents are preserved. Assistant budget searches
and comparisons query this collection, so optional fields such as ratings,
descriptions, discounts, and stock appear only when they are present in the
database.

## Configure email verification and password reset

Signup verification and password reset codes are sent through an SMTP account.
Configure these environment variables before starting the app:

```powershell
$env:SMTP_HOST = "smtp.gmail.com"
$env:SMTP_PORT = "587"
$env:SMTP_USERNAME = "your-email@gmail.com"
$env:SMTP_PASSWORD = "your-email-app-password"
$env:SMTP_FROM = "your-email@gmail.com"
python app.py
```

For Gmail, use a Google App Password (with 2-Step Verification enabled), not
your normal account password. Keep SMTP credentials out of source control.
Codes expire after 10 minutes, are stored as hashes, and are invalidated after
use or five incorrect attempts. A 60-second resend cooldown and five-requests
per-email hourly limit apply.

## Optional Groq shopping assistant

The assistant works without Groq by using an offline catalogue-based fallback.
To enable model responses, set `GROQ_API_KEY` on the Flask server. Optionally
set `GROQ_MODEL`; it defaults to `llama-3.3-70b-versatile`. Model names can
change; `llama-3.1-8b-instant` is a smaller option. Check
<https://console.groq.com/docs/models> for current names. Create/manage keys at
<https://console.groq.com/keys>. Never expose the Groq key to frontend code.
`LOGIN_OTP_ENABLED` defaults to `0`; the optional login OTP flow is not enabled
in the current application.

See [ASSISTANT_SETUP.md](ASSISTANT_SETUP.md) for the assistant behavior,
environment examples, and additional setup details.

## Run with Atlas and SMTP

From PowerShell in the project folder, start the interactive launcher:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_app.ps1
```

The launcher uses values already supplied in the process environment or `.env`
and prompts only for missing or still-placeholder credentials. If you prefer
not to use `.env`, enter the Gmail sender address, its Google App Password,
optional Groq API key, and MongoDB URI when prompted. Secret inputs are hidden;
the URI is visible as you paste it. Do not share screenshots containing
credentials. Keep the terminal open while the app runs.

## Copy data from the SQLite backup

To copy existing users, carts, orders, payment attempts, wishlists, and ratings to MongoDB, run this once while MongoDB is available:

```powershell
python migrate_sqlite_to_mongodb.py
```

Use `--source PATH` to select a different SQLite backup. The importer is safe to rerun: it adds missing records but does not overwrite records already present in MongoDB. It never modifies the SQLite source. Back up the source file before migration and verify the copied collections before relying on MongoDB data.

## Tests

The API tests use `mongomock` and do not require a running MongoDB service.
`tests/conftest.py` disables dotenv loading, so tests do not depend on a local
`.env` file. Tests do not read or modify the SQLite backup.
