# Pushes secrets from .env to the Cloudflare Worker (never commit .env).
# Usage:
#   .\scripts\cloudflare-secrets.ps1            # push all recognized keys
#   .\scripts\cloudflare-secrets.ps1 -DryRun    # show what would be pushed (values masked)
param([switch]$DryRun)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root ".env"
if (-not (Test-Path -LiteralPath $envFile)) { throw ".env not found at $envFile" }

$allowed = @(
  "NVIDIA_API_KEY","NVIDIA_MODEL","OPENROUTER_API_KEY","OPENROUTER_MODEL",
  "OPENROUTER_REFERER","OPENROUTER_TITLE","OPENAI_API_KEY","ANTHROPIC_API_KEY",
  "TIKTOK_CLIENT_KEY","TIKTOK_CLIENT_SECRET","TIKTOK_ACCESS_TOKEN","TIKTOK_REFRESH_TOKEN",
  "YOUTUBE_CLIENT_ID","YOUTUBE_CLIENT_SECRET","YOUTUBE_REFRESH_TOKEN","YOUTUBE_API_KEY",
  "TWITTER_API_KEY","TWITTER_API_SECRET","TWITTER_ACCESS_TOKEN","TWITTER_ACCESS_SECRET",
  "META_USER_ACCESS_TOKEN","META_APP_ID","META_APP_SECRET","IG_USER_ID",
  "PAYPAL_CLIENT_ID","PAYPAL_CLIENT_SECRET","PAYPAL_MODE",
  "DASHBOARD_PASSWORD",
  "SMTP_HOST","SMTP_PORT","SMTP_USER","SMTP_PASS","SMTP_FROM","ALERT_EMAIL"
)

$map = @{}
Get-Content -LiteralPath $envFile | ForEach-Object {
  $line = $_.Trim()
  if (-not $line -or $line.StartsWith("#")) { return }
  $i = $line.IndexOf("=")
  if ($i -lt 1) { return }
  $k = $line.Substring(0, $i).Trim()
  $v = $line.Substring($i + 1).Trim().Trim('"').Trim("'")
  if ($allowed -contains $k -and $v) { $map[$k] = $v }
}

if ($map.Count -eq 0) { throw "No recognized secret values found in .env" }

if ($DryRun) {
  Write-Output "Would push $($map.Count) secrets:"
  $map.Keys | Sort-Object | ForEach-Object {
    $v = $map[$_]
    $hint = if ($v.Length -gt 4) { "…$($v.Substring($v.Length - 4))" } else { "…" }
    Write-Output "  $_ = $hint"
  }
  return
}

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("asp-secrets-" + [guid]::NewGuid().ToString("N") + ".json")
($map | ConvertTo-Json -Compress) | Set-Content -LiteralPath $tmp -Encoding utf8
try {
  # Use local wrangler (npx) — global installs are often outdated and reject
  # the current Containers config format (scheduling_policy/images/exports).
  & npx wrangler secret bulk $tmp
} finally {
  Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
}
