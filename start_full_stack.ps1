###############################################################################
#  start_full_stack.ps1  –  Arranca el ecosistema completo de Bot Bíblico
#  Fases:
#    0. Docker (Langfuse + ClickHouse + Postgres + Redis + MinIO)
#    0.5. LiteLLM Gateway Proxy (localhost:4000)
#    1. Base de datos SQLite (migraciones)
#    1.5. Auditoría Doctrinal + Ingesta vectorial a ChromaDB
#    2. Aplicación Web Teos AI (Streamlit localhost:8502)
###############################################################################
param(
    [switch]$SkipDocker,
    [switch]$SkipLiteLLM,
    [switch]$SkipAudit,
    [switch]$OnlyApp,
    [int]$AuditLimit = 5,
    [switch]$AuditAll
)

$ErrorActionPreference = "Continue"

# --- 1. Cargar variables de entorno desde .env ---
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line.Split("=", 2)
            $key = $parts[0].Trim()
            $val = $parts[1].Trim().Trim('"').Trim("'")
            if ($key) {
                [System.Environment]::SetEnvironmentVariable($key, $val, "Process")
                Set-Item -Path "env:$key" -Value $val
            }
        }
    }
}

# --- 2. Registrar rutas críticas en PATH para la sesión actual ---
$extraPaths = @(
    "$env:APPDATA\Python\Python313\Scripts",
    "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin",
    "C:\Program Files\Docker\Docker\resources\bin",
    "$env:LOCALAPPDATA\Programs\Ollama"
)
foreach ($p in $extraPaths) {
    if ((Test-Path $p) -and ($env:Path -notlike "*$p*")) {
        $env:Path = "$p;$env:Path"
    }
}

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

# --- Utilidades ---
function Write-Phase($num, $title) {
    Write-Host ""
    Write-Host ("=" * 65) -ForegroundColor Cyan
    Write-Host "  FASE $num : $title" -ForegroundColor Yellow
    Write-Host ("=" * 65) -ForegroundColor Cyan
}

function Test-PortOpen($port) {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect("127.0.0.1", $port)
        $tcp.Close()
        return $true
    } catch {
        return $false
    }
}

# =====================================================================
#  FASE 0 – Docker: Langfuse + Infraestructura de Observabilidad
# =====================================================================
if (-not $SkipDocker -and -not $OnlyApp) {
    Write-Phase 0 "Infraestructura Docker (Langfuse, ClickHouse, Postgres, Redis, MinIO)"

    if (Test-PortOpen 3000) {
        Write-Host "  [OK] Langfuse ya esta corriendo en http://localhost:3000" -ForegroundColor Green
    } else {
        $dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
        if (-not $dockerCmd) {
            Write-Host "  [AVISO] Docker no fue detectado en PATH. Omitiendo Langfuse." -ForegroundColor Yellow
            Write-Host "          Puedes iniciar Docker Desktop mas tarde para habilitar telemetria." -ForegroundColor DarkGray
        } else {
            # Verificar si el daemon de Docker responde
            $dockerReady = $false
            try {
                $check = & docker info 2>&1
                if ($LASTEXITCODE -eq 0) { $dockerReady = $true }
            } catch {}

            if (-not $dockerReady) {
                Write-Host "  [AVISO] Docker Desktop esta instalado pero el motor aun no esta corriendo." -ForegroundColor Yellow
                Write-Host "          Iniciando Docker Desktop en segundo plano..." -ForegroundColor DarkGray
                $dockerDesktopApp = "$env:LOCALAPPDATA\Programs\DockerDesktop\Docker Desktop.exe"
                if (Test-Path $dockerDesktopApp) {
                    Start-Process $dockerDesktopApp
                }
                Write-Host "          Continuando con la aplicacion mientras Docker inicia..." -ForegroundColor DarkGray
            } else {
                Write-Host "  [INFO] Levantando contenedores Docker con docker compose up -d..." -ForegroundColor Yellow
                docker compose up -d
                
                # Esperar a que Langfuse responda
                $attempts = 0
                $maxAttempts = 15
                while (-not (Test-PortOpen 3000) -and $attempts -lt $maxAttempts) {
                    Start-Sleep -Seconds 2
                    $attempts++
                    Write-Host "  [INFO] Esperando Langfuse... ($attempts/$maxAttempts)" -ForegroundColor DarkGray
                }
                
                if (Test-PortOpen 3000) {
                    Write-Host "  [OK] Langfuse operativo en http://localhost:3000" -ForegroundColor Green
                } else {
                    Write-Host "  [AVISO] Langfuse tardara unos momentos mas en completar migraciones internas." -ForegroundColor Yellow
                }
            }
        }
    }
}

# =====================================================================
#  FASE 0.5 – LiteLLM Gateway Proxy (localhost:4000) + Ollama Local
# =====================================================================
if (-not $SkipLiteLLM -and -not $OnlyApp) {
    Write-Phase "0.5" "Gateway LiteLLM (Proxy unificado de LLMs)"

    # Verificar Ollama local como seguro offline
    $ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
    if ($ollamaCmd -and -not (Test-PortOpen 11434)) {
        Write-Host "  [INFO] Iniciando servicio local Ollama en segundo plano..." -ForegroundColor DarkGray
        Start-Process -FilePath $ollamaCmd.Source -ArgumentList "serve" -WindowStyle Minimized
        Start-Sleep -Seconds 1
    }

    if (Test-PortOpen 4000) {
        Write-Host "  [OK] LiteLLM Proxy ya esta corriendo en http://localhost:4000" -ForegroundColor Green
    } else {
        Write-Host "  [INFO] Levantando LiteLLM Proxy en segundo plano..." -ForegroundColor Yellow
        Write-Host "         Endpoint: http://localhost:4000/v1" -ForegroundColor DarkGray
        
        $scriptsPath = "$env:APPDATA\Python\Python313\Scripts"
        $litellmCmd = (Get-Command litellm.exe -ErrorAction SilentlyContinue).Source
        if (-not $litellmCmd) {
            $litellmCmd = "$scriptsPath\litellm.exe"
        }

        if (Test-Path $litellmCmd) {
            $litellmJob = Start-Process -FilePath $litellmCmd `
                -ArgumentList "--config", "litellm_config.yaml", "--port", "4000" `
                -PassThru -WindowStyle Minimized
            Write-Host "  [OK] LiteLLM Proxy lanzado (PID: $($litellmJob.Id))" -ForegroundColor Green
        } else {
            $litellmJob = Start-Process -FilePath "python" `
                -ArgumentList "-m", "litellm.proxy.proxy_cli", "--config", "litellm_config.yaml", "--port", "4000" `
                -PassThru -WindowStyle Minimized
            Write-Host "  [OK] LiteLLM Proxy lanzado via python CLI (PID: $($litellmJob.Id))" -ForegroundColor Green
        }
        Start-Sleep -Seconds 3
    }
}

# =====================================================================
#  FASE 1 – Inicializar Base de Datos SQLite (Migraciones)
# =====================================================================
if (-not $OnlyApp) {
    Write-Phase 1 "Base de Datos (Migraciones SQLite)"
    
    Write-Host "  [INFO] Ejecutando migraciones en biblico.db..." -ForegroundColor Yellow
    python database/connection.py
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] Base de datos inicializada correctamente" -ForegroundColor Green
    } else {
        Write-Host "  [AVISO] Hubo un problema con las migraciones (codigo: $LASTEXITCODE)" -ForegroundColor Yellow
    }
}

# =====================================================================
#  FASE 1.5 – Auditoria Doctrinal e Ingesta Vectorial (EN SEGUNDO PLANO)
# =====================================================================
if (-not $SkipAudit -and -not $OnlyApp) {
    Write-Phase "1.5" "Auditoria Doctrinal e Ingesta a ChromaDB (segundo plano)"
    
    Write-Host "  [INFO] Lanzando auditoria en segundo plano para no bloquear el frontend..." -ForegroundColor Yellow
    Write-Host "         Solo los documentos [Alineado] seran vectorizados." -ForegroundColor DarkGray
    
    $auditArgs = "scripts/doctrinal_audit.py"
    if ($AuditAll) {
        $auditArgs += " --all"
        Write-Host "         Modo completo: Auditando todos los pendientes de la biblioteca." -ForegroundColor Cyan
    } else {
        $auditArgs += " --limit $AuditLimit"
        Write-Host "         Tanda rapida: Procesando hasta $AuditLimit archivos nuevos." -ForegroundColor Cyan
    }

    $auditLogFile = Join-Path $PSScriptRoot "logs\audit_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"
    $logsDir = Join-Path $PSScriptRoot "logs"
    if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }

    $auditJob = Start-Process -FilePath "python" `
        -ArgumentList $auditArgs `
        -PassThru -WindowStyle Minimized `
        -RedirectStandardOutput $auditLogFile `
        -RedirectStandardError "$auditLogFile.err"
    
    Write-Host "  [OK] Auditoria lanzada en segundo plano (PID: $($auditJob.Id))" -ForegroundColor Green
    Write-Host "       Log: $auditLogFile" -ForegroundColor DarkGray
}

# =====================================================================
#  FASE 2 – Aplicacion Web Streamlit (localhost:8502)
# =====================================================================
Write-Phase 2 "Aplicacion Web Teos AI (Streamlit)"

Write-Host "  [INFO] Levantando Streamlit en http://localhost:8502" -ForegroundColor Green
Write-Host "         Acceso local: http://localhost:8502" -ForegroundColor Cyan
Write-Host ""
Write-Host ("=" * 65) -ForegroundColor Cyan
Write-Host "  RESUMEN DE SERVICIOS ACTIVOS:" -ForegroundColor Yellow
Write-Host "    * Langfuse Dashboard    -> http://localhost:3000" -ForegroundColor White
Write-Host "    * LiteLLM Proxy         -> http://localhost:4000/v1" -ForegroundColor White
Write-Host "    * Teos AI (Streamlit)   -> http://localhost:8502" -ForegroundColor White
if (-not $SkipAudit -and -not $OnlyApp) {
    Write-Host "    * Auditoria Doctrinal   -> corriendo en segundo plano" -ForegroundColor White
}
Write-Host ("=" * 65) -ForegroundColor Cyan
Write-Host ""

python -m streamlit run app.py --server.port 8502 --server.address 0.0.0.0

