$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

Write-Host 'Enter the Gmail account used to create the ShopEase App Password.'
$env:SMTP_HOST = 'smtp.gmail.com'
$env:SMTP_PORT = '587'
$env:SMTP_USERNAME = (Read-Host 'Sender Gmail address').Trim()
$env:SMTP_FROM = $env:SMTP_USERNAME

$smtpPassword = Read-Host 'Google App Password (input is hidden)' -AsSecureString
$env:SMTP_PASSWORD = [System.Net.NetworkCredential]::new('', $smtpPassword).Password.Replace(' ', '')

Write-Host 'In Atlas, copy the URI from Connect > Drivers, replace its password placeholder, and paste the complete URI below.'
$env:MONGODB_URI = (Read-Host 'MongoDB Atlas URI').Trim()
$env:MONGODB_DATABASE = 'shopease'

if ([string]::IsNullOrWhiteSpace($env:SMTP_USERNAME) -or [string]::IsNullOrWhiteSpace($env:SMTP_PASSWORD)) {
    throw 'A Gmail address and Google App Password are required.'
}
if (-not $env:MONGODB_URI.StartsWith('mongodb+srv://')) {
    throw 'The MongoDB URI must start with mongodb+srv://. Copy the full Atlas URI from Connect > Drivers.'
}
if ($env:MONGODB_URI -match 'YOUR_CLUSTER|CLUSTER_HOST|DB_USER|URL_ENCODED_PASSWORD|<password>') {
    throw 'The MongoDB URI still contains a placeholder. Replace placeholders with your Atlas values.'
}

Write-Host 'Configuration loaded. Starting ShopEase; leave this window open.'
try {
    python .\app.py
}
finally {
    Remove-Item Env:\SMTP_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:\MONGODB_URI -ErrorAction SilentlyContinue
}
