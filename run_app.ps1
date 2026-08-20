$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Iniciando Ecosistema Bot Biblico (MVP)..." -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Iniciar la aplicación Streamlit
Write-Host "Levantando el front-end (Streamlit)..." -ForegroundColor Yellow
Write-Host "La app estará disponible en tu red local en el puerto 8502." -ForegroundColor Green
Write-Host "Puedes entrar desde tu tablet buscando la IP local de tu PC seguida de :8502" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

python -m streamlit run app.py --server.port 8502 --server.address 0.0.0.0
