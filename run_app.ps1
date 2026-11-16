$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

$dotenvValues = $null
$dotenvPath = Join-Path $PSScriptRoot '.env'
if (Test-Path -LiteralPath $dotenvPath) {
    $dotenvJson = & python -c 'import json, sys; from dotenv import dotenv_values; print(json.dumps(dotenv_values(sys.argv[1])))' $dotenvPath
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not read .env settings. Install the project requirements and try again.'
    }
    $dotenvValues = $dotenvJson | ConvertFrom-Json
}

function Get-ConfiguredValue([string]$Name) {
    $processValue = [Environment]::GetEnvironmentVariable($Name, 'Process')
    if (-not [string]::IsNullOrWhiteSpace($processValue)) {
        return $processValue
    }
    if ($null -ne $dotenvValues) {
        $property = $dotenvValues.PSObject.Properties[$Name]
        if ($null -ne $property -and -not [string]::IsNullOrWhiteSpace([string]$property.Value)) {
            return [string]$property.Value
        }
    }
    return ''
}

$smtpHost = Get-ConfiguredValue 'SMTP_HOST'
if ([string]::IsNullOrWhiteSpace($smtpHost)) {
    $smtpHost = 'smtp.gmail.com'
    $env:SMTP_HOST = $smtpHost
}
$smtpPort = Get-ConfiguredValue 'SMTP_PORT'
if ([string]::IsNullOrWhiteSpace($smtpPort)) {
    $smtpPort = '587'
    $env:SMTP_PORT = $smtpPort
}
$smtpUsername = Get-ConfiguredValue 'SMTP_USERNAME'
if ([string]::IsNullOrWhiteSpace($smtpUsername) -or $smtpUsername -match '^your-gmail-address@') {
    $smtpUsername = (Read-Host 'Sender Gmail address').Trim()
    $env:SMTP_USERNAME = $smtpUsername
}
$smtpPassword = Get-ConfiguredValue 'SMTP_PASSWORD'
if ([string]::IsNullOrWhiteSpace($smtpPassword) -or $smtpPassword -match '^your-16-character-app-password$') {
    $securePassword = Read-Host 'Google App Password (input is hidden)' -AsSecureString
    $smtpPassword = [System.Net.NetworkCredential]::new('', $securePassword).Password.Replace(' ', '')
    $env:SMTP_PASSWORD = $smtpPassword
}
$smtpFrom = Get-ConfiguredValue 'SMTP_FROM'
if ([string]::IsNullOrWhiteSpace($smtpFrom) -or $smtpFrom -match 'your-gmail-address@') {
    $env:SMTP_FROM = $smtpUsername
}

$groqKey = Get-ConfiguredValue 'GROQ_API_KEY'
if ([string]::IsNullOrWhiteSpace($groqKey) -or $groqKey -eq 'your-groq-api-key') {
    Write-Host 'Optionally enter a Groq API key. Leave blank to use the offline shopping assistant.'
    $secureGroqKey = Read-Host 'Groq API key (input is hidden)' -AsSecureString
    $groqKey = [System.Net.NetworkCredential]::new('', $secureGroqKey).Password
    $env:GROQ_API_KEY = $groqKey
}

$mongoUri = Get-ConfiguredValue 'MONGODB_URI'
if ([string]::IsNullOrWhiteSpace($mongoUri)) {
    Write-Host 'In Atlas, copy the URI from Connect > Drivers, replace its password placeholder, and paste it below.'
    $mongoUri = (Read-Host 'MongoDB URI').Trim()
    $env:MONGODB_URI = $mongoUri
}
$mongoDatabase = Get-ConfiguredValue 'MONGODB_DATABASE'
if ([string]::IsNullOrWhiteSpace($mongoDatabase)) {
    $mongoDatabase = 'shopease'
    $env:MONGODB_DATABASE = $mongoDatabase
}

if ([string]::IsNullOrWhiteSpace($smtpUsername) -or [string]::IsNullOrWhiteSpace($smtpPassword)) {
    throw 'A Gmail address and Google App Password are required for email OTPs.'
}
if (-not ($mongoUri.StartsWith('mongodb://') -or $mongoUri.StartsWith('mongodb+srv://'))) {
    throw 'The MongoDB URI must start with mongodb:// or mongodb+srv://.'
}
if ($mongoUri -match 'YOUR_CLUSTER|CLUSTER_HOST|DB_USER|URL_ENCODED_PASSWORD|<password>') {
    throw 'The MongoDB URI still contains a placeholder. Replace placeholders with your MongoDB values.'
}

Write-Host 'Configuration loaded. Starting ShopEase; leave this window open.'
try {
    python .\app.py
}
finally {
    Remove-Item Env:\SMTP_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:\MONGODB_URI -ErrorAction SilentlyContinue
    Remove-Item Env:\GROQ_API_KEY -ErrorAction SilentlyContinue
}
