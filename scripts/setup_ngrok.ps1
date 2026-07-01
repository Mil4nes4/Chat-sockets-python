# Levanta un tunel TCP con ngrok hacia el servidor de chat (puerto 5000).
# El token NO se guarda aqui: se lee de la variable de entorno NGROK_TOKEN,
# que hay que definir antes de correr este script, por ejemplo:
#   $env:NGROK_TOKEN = "tu_token_aqui"
#   .\scripts\setup_ngrok.ps1

if (-not (Get-Command ngrok -ErrorAction SilentlyContinue)) {
    Write-Host "Error: ngrok no esta instalado o no esta en el PATH." -ForegroundColor Red
    Write-Host "Instalalo con: winget install --id Ngrok.Ngrok -e"
    exit 1
}

if (-not $env:NGROK_TOKEN) {
    Write-Host "Error: no se encontro la variable de entorno NGROK_TOKEN." -ForegroundColor Red
    Write-Host 'Definela antes de correr este script: $env:NGROK_TOKEN = "tu_token_aqui"'
    exit 1
}

ngrok config add-authtoken $env:NGROK_TOKEN
ngrok tcp 5000
