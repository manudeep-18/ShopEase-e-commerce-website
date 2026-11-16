# Database setup

ShopEase connects to a local MongoDB server at `mongodb://localhost:27017` by default. To use another MongoDB server, set `MONGODB_URI` in the shell before starting the app. The previous `shopease.db` SQLite file is left untouched as a backup and is not used by the Flask app.

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

Replace `DB_USER`, `URL_ENCODED_PASSWORD`, and `CLUSTER_HOST`; do not type those placeholder values literally. The app reads configuration from process environment variables and does not load a `.env` file. Keep the connection string private. Connection errors are reported rather than silently switching databases.

The app creates its MongoDB indexes on startup.

## Configure password reset email

Password reset codes are sent through an SMTP account. Configure these environment variables before starting the app:

```powershell
$env:SMTP_HOST = "smtp.gmail.com"
$env:SMTP_PORT = "587"
$env:SMTP_USERNAME = "your-email@gmail.com"
$env:SMTP_PASSWORD = "your-email-app-password"
$env:SMTP_FROM = "your-email@gmail.com"
python app.py
```

For Gmail, use a Google App Password (with 2-Step Verification enabled), not your normal account password. Keep SMTP credentials out of source control. The reset code expires after 10 minutes and is invalidated after use.

## Run with Atlas and SMTP

From PowerShell in the project folder, start the interactive launcher:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_app.ps1
```

Enter the Gmail sender address, its Google App Password, and the complete MongoDB Atlas URI copied from **Connect → Drivers**. The App Password input is hidden; the Atlas URI is visible as you paste it. Do not share screenshots containing credentials. The values are not saved to a file. Keep the terminal open while the app runs.

## Copy data from the SQLite backup

To copy existing users, carts, orders, payment attempts, wishlists, and ratings to MongoDB, run this once while MongoDB is available:

```powershell
python migrate_sqlite_to_mongodb.py
```

Use `--source PATH` to select a different SQLite backup. The importer is safe to rerun: it adds missing records but does not overwrite records already present in MongoDB. It never modifies the SQLite source. Back up the source file before migration and verify the copied collections before relying on MongoDB data.

## Tests

The API tests use `mongomock` and do not require a running MongoDB service. They do not read or modify the SQLite backup.
