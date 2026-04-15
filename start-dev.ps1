param(
	[switch]$VisibleWindows,
	[switch]$Stop
)

$ErrorActionPreference = "Stop"
$RootPath = if ($PSScriptRoot) {
	(Resolve-Path $PSScriptRoot).Path
} else {
	(Get-Location).Path
}

$BackendPath = Join-Path $RootPath "backend"
$FrontendPath = Join-Path $RootPath "frontend"
$LogsPath = Join-Path $RootPath "logs"
$NginxConfigPath = Join-Path $RootPath "docker\nginx\nginx.local.conf"
$RootEnvPath = Join-Path $RootPath ".env"
$FrontendEnvPath = Join-Path $FrontendPath ".env"
$ProcessStatePath = Join-Path $LogsPath "start-dev-processes.json"
$ManagedPorts = @(2026, 2024, 8001, 3000)
$RunStamp = Get-Date -Format "yyyyMMdd-HHmmss"

function Write-Step {
	param(
		[string]$Message,
		[ConsoleColor]$Color = [ConsoleColor]::Cyan
	)

	Write-Host $Message -ForegroundColor $Color
}

function Assert-Command {
	param(
		[string]$CommandName,
		[string]$InstallHint
	)

	if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
		throw "Required command '$CommandName' was not found. $InstallHint"
	}
}

function Assert-File {
	param([string]$Path)

	if (-not (Test-Path -LiteralPath $Path)) {
		throw "Required file not found: $Path"
	}
}

function Import-DotEnv {
	param([string]$Path)

	if (-not (Test-Path -LiteralPath $Path)) {
		return
	}

	Get-Content -LiteralPath $Path | ForEach-Object {
		$line = $_.Trim()
		if (-not $line -or $line.StartsWith("#")) {
			return
		}

		if ($line.StartsWith("export ")) {
			$line = $line.Substring(7).Trim()
		}

		$parts = $line -split '=', 2
		if ($parts.Count -ne 2) {
			return
		}

		$name = $parts[0].Trim()
		if (-not $name) {
			return
		}

		$value = $parts[1].Trim()
		if ($value.Length -ge 2) {
			$isDoubleQuoted = $value.StartsWith('"') -and $value.EndsWith('"')
			$isSingleQuoted = $value.StartsWith("'") -and $value.EndsWith("'")
			if ($isDoubleQuoted -or $isSingleQuoted) {
				$value = $value.Substring(1, $value.Length - 2)
			}
		}

		[Environment]::SetEnvironmentVariable($name, $value, "Process")
	}
}

function Invoke-Step {
	param(
		[string]$Message,
		[scriptblock]$Action
	)

	Write-Step $Message
	$global:LASTEXITCODE = 0
	& $Action
	if ($LASTEXITCODE -ne 0) {
		throw "Step failed: $Message"
	}
}

function Get-ManagedProcesses {
	if (-not (Test-Path -LiteralPath $ProcessStatePath)) {
		return @()
	}

	$state = Get-Content -LiteralPath $ProcessStatePath -Raw | ConvertFrom-Json
	if ($state -is [System.Array]) {
		return $state
	}

	return @($state)
}

function Save-ManagedProcesses {
	param([object[]]$Processes)

	$Processes | ConvertTo-Json | Set-Content -LiteralPath $ProcessStatePath
}

function Stop-ProcessTree {
	param([int]$ProcessId)

	if (-not $ProcessId) {
		return
	}

	if (-not (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) {
		return
	}

	$taskkillProcess = Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", "taskkill /PID $ProcessId /T /F >nul 2>&1") -NoNewWindow -Wait -PassThru -ErrorAction SilentlyContinue
	if ($taskkillProcess -and $taskkillProcess.ExitCode -notin @(0, 128, 255)) {
		throw "taskkill failed for PID $ProcessId with exit code $($taskkillProcess.ExitCode)."
	}
}

function Get-RepoScopedProcesses {
	$escapedRootPath = [Regex]::Escape($RootPath)
	return Get-CimInstance Win32_Process | Where-Object {
		$commandLine = $_.CommandLine
		if (-not $commandLine) {
			return $false
		}

		$commandLine -match $escapedRootPath -and (
			$commandLine -match 'langgraph(\.exe)?\s+dev' -or
			$commandLine -match 'uvicorn(\.exe)?\s+app\.gateway\.app:app' -or
			$commandLine -match 'next(\.exe)?\s+dev' -or
			$commandLine -match 'nginx(\.exe)?'
		)
	}
}

function Get-ListenerPidsForPort {
	param([int]$Port)

	$pids = @()
	$connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
	if ($connections) {
		$pids += $connections | Select-Object -ExpandProperty OwningProcess
	}

	$netstatLines = netstat -ano -p tcp | Select-String -Pattern (":$Port\s")
	foreach ($line in $netstatLines) {
		$text = $line.ToString().Trim()
		if ($text -match '^TCP\s+\S+:' + $Port + '\s+\S+\s+LISTENING\s+(\d+)$') {
			$pids += [int]$matches[1]
		}
	}

	return $pids | Sort-Object -Unique
}

function Get-RepoScopedProcessPids {
	return Get-RepoScopedProcesses | Select-Object -ExpandProperty ProcessId -Unique
}

function Get-RepoScopedNginxPids {
	return Get-RepoScopedProcesses |
		Where-Object { $_.Name -eq 'nginx.exe' } |
		Select-Object -ExpandProperty ProcessId -Unique
}

function Stop-NginxProcesses {
	try {
		& nginx -c $NginxConfigPath -p $RootPath -s quit *> $null
	} catch {
	}

	if (Test-Path -LiteralPath (Join-Path $LogsPath 'nginx.pid')) {
		try {
			$nginxPid = [int](Get-Content -LiteralPath (Join-Path $LogsPath 'nginx.pid') | Select-Object -First 1)
			Stop-ProcessTree -ProcessId $nginxPid
		} catch {
		}
	}

	$nginxListenerPids = Get-ListenerPidsForPort -Port 2026
	foreach ($nginxListenerPid in $nginxListenerPids) {
		Stop-ProcessTree -ProcessId $nginxListenerPid
	}

	foreach ($nginxPid in (Get-RepoScopedNginxPids | Sort-Object -Unique)) {
		Stop-ProcessTree -ProcessId $nginxPid
	}
}

function Stop-ManagedProcesses {
	$managedProcesses = Get-ManagedProcesses
	$managedProcessPorts = @()
	foreach ($managedProcess in $managedProcesses) {
		if ($managedProcess.Port) {
			$managedProcessPorts += [int]$managedProcess.Port
		}
	}
	if (-not $managedProcessPorts) {
		$managedProcessPorts = $ManagedPorts
	}

	foreach ($pass in 1..3) {
		foreach ($managedProcess in $managedProcesses) {
			if (-not $managedProcess.Pid) {
				continue
			}

			try {
				$process = Get-Process -Id $managedProcess.Pid -ErrorAction SilentlyContinue
				if ($process) {
					Stop-ProcessTree -ProcessId $managedProcess.Pid
				}
			} catch {
			}
		}

		$listenerPids = @()
		foreach ($port in $managedProcessPorts) {
			$listenerPids += Get-ListenerPidsForPort -Port $port
		}

		foreach ($listenerPid in ($listenerPids | Sort-Object -Unique)) {
			try {
				$listenerProcess = Get-Process -Id $listenerPid -ErrorAction SilentlyContinue
				if ($listenerProcess) {
					Stop-ProcessTree -ProcessId $listenerPid
				}
			} catch {
			}
		}

		foreach ($repoScopedPid in (Get-RepoScopedProcessPids | Sort-Object -Unique)) {
			try {
				$repoScopedProcess = Get-Process -Id $repoScopedPid -ErrorAction SilentlyContinue
				if ($repoScopedProcess) {
					Stop-ProcessTree -ProcessId $repoScopedPid
				}
			} catch {
			}
		}

		Stop-NginxProcesses
	}

	if (Test-Path -LiteralPath $ProcessStatePath) {
		Remove-Item -LiteralPath $ProcessStatePath -Force
	}

	if (Test-Path -LiteralPath (Join-Path $LogsPath 'nginx.pid')) {
		try {
			Remove-Item -LiteralPath (Join-Path $LogsPath 'nginx.pid') -Force
		} catch {
		}
	}
}

function Start-ManagedProcess {
	param(
		[string]$Name,
		[string]$Title,
		[int]$Port,
		[string]$WorkingDirectory,
		[string]$Command,
		[string]$StartupMessage
	)

	$psCommand = "& { `$Host.UI.RawUI.WindowTitle = '$Title'; Set-Location '$WorkingDirectory'; Write-Host '$StartupMessage' -ForegroundColor Cyan; $Command }"

	if ($VisibleWindows) {
		$process = Start-Process powershell -PassThru -ArgumentList @(
			"-NoExit",
			"-ExecutionPolicy",
			"ByPass",
			"-Command",
			$psCommand
		)
		return [pscustomobject]@{
			Name = $Name
			Pid = $process.Id
			Port = $Port
			Mode = "visible"
			StdoutLog = $null
			StderrLog = $null
		}
	}

	$stdoutLog = Join-Path $LogsPath "$RunStamp.$Name.stdout.log"
	$stderrLog = Join-Path $LogsPath "$RunStamp.$Name.stderr.log"

	$process = Start-Process powershell -WindowStyle Hidden -PassThru -ArgumentList @(
		"-NoProfile",
		"-ExecutionPolicy",
		"ByPass",
		"-Command",
		$psCommand
	) -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog

	return [pscustomobject]@{
		Name = $Name
		Pid = $process.Id
		Port = $Port
		Mode = "hidden"
		StdoutLog = $stdoutLog
		StderrLog = $stderrLog
	}
}

Write-Host "🦌 Starting DeerFlow Local Development (Windows helper)" -ForegroundColor Green
if ($VisibleWindows) {
	Write-Host "Preparing dependencies, migrations, and 4 service windows..." -ForegroundColor Yellow
} else {
	Write-Host "Preparing dependencies, migrations, and 4 hidden background services..." -ForegroundColor Yellow
}
Write-Host "----------------------------------------------------"

if ($Stop) {
	Write-Step "Stopping any previously managed start-dev services..."
	Stop-ManagedProcesses
	Write-Host "Managed services stopped." -ForegroundColor Green
	return
}

Assert-Command "uv" "Install uv and make sure it is on PATH."
Assert-Command "pnpm" "Install pnpm and make sure it is on PATH."
Assert-Command "nginx" "Install nginx for Windows and make sure it is on PATH."

Assert-File (Join-Path $RootPath "config.yaml")
Assert-File (Join-Path $RootPath "extensions_config.json")
Assert-File $NginxConfigPath
Assert-File (Join-Path $BackendPath "alembic.ini")
Assert-File (Join-Path $FrontendPath "src\server\better-auth\config.ts")

Import-DotEnv $RootEnvPath

if (-not $env:DATABASE_URL) {
	throw "DATABASE_URL is not set. Define it in .env or frontend/.env before running start-dev.ps1."
}

if (-not $env:NEXT_PUBLIC_BACKEND_BASE_URL) {
	$env:NEXT_PUBLIC_BACKEND_BASE_URL = "http://localhost:8001"
}

if (-not $env:NEXT_PUBLIC_LANGGRAPH_BASE_URL) {
	$env:NEXT_PUBLIC_LANGGRAPH_BASE_URL = "http://localhost:2024"
}

Invoke-Step "Creating nginx log/temp directories..." {
	New-Item -ItemType Directory -Force -Path @(
		$LogsPath,
		(Join-Path $RootPath "temp\client_body_temp"),
		(Join-Path $RootPath "temp\proxy_temp"),
		(Join-Path $RootPath "temp\fastcgi_temp"),
		(Join-Path $RootPath "temp\uwsgi_temp"),
		(Join-Path $RootPath "temp\scgi_temp")
	) | Out-Null
}

Invoke-Step "Installing backend Python packages with uv..." {
	Push-Location $BackendPath
	try {
		uv sync
	} finally {
		Pop-Location
	}
}

Invoke-Step "Installing frontend npm packages with pnpm..." {
	Push-Location $FrontendPath
	try {
		pnpm install
	} finally {
		Pop-Location
	}
}

Invoke-Step "Applying Better Auth database migrations..." {
	Push-Location $FrontendPath
	try {
		Import-DotEnv $FrontendEnvPath
		pnpm exec better-auth migrate --config .\src\server\better-auth\config.ts
	} finally {
		Pop-Location
	}
}

Invoke-Step "Applying backend Alembic migrations..." {
	Push-Location $BackendPath
	try {
		Import-DotEnv $RootEnvPath
		$env:PYTHONPATH = "."
		uv run alembic upgrade head
	} finally {
		Pop-Location
	}
}

Write-Step "Stopping any previously managed start-dev services..."
Stop-ManagedProcesses

Import-DotEnv $RootEnvPath

Write-Host "----------------------------------------------------"
if ($VisibleWindows) {
	Write-Host "Opening 4 separate PowerShell windows..." -ForegroundColor Yellow
} else {
	Write-Host "Starting 4 hidden background services from this terminal session..." -ForegroundColor Yellow
}

$managedProcesses = @()

$managedProcesses += Start-ManagedProcess -Name "nginx" -Title "DeerFlow - Nginx (2026)" -Port 2026 -WorkingDirectory $RootPath -StartupMessage "Starting Nginx local dev server..." -Command "nginx -c '$NginxConfigPath' -p '$RootPath'"
Write-Host "✅ Nginx starting..."

$managedProcesses += Start-ManagedProcess -Name "langgraph" -Title "DeerFlow - LangGraph (2024)" -Port 2024 -WorkingDirectory $BackendPath -StartupMessage "Starting LangGraph with reload enabled..." -Command "uv run langgraph dev --no-browser --allow-blocking"
Write-Host "✅ LangGraph server starting..."

$managedProcesses += Start-ManagedProcess -Name "gateway" -Title "DeerFlow - Gateway (8001)" -Port 8001 -WorkingDirectory $BackendPath -StartupMessage "Starting Gateway API with reload enabled..." -Command "`$env:PYTHONPATH = '.'; uv run uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001 --reload"
Write-Host "✅ Gateway API starting..."

$managedProcesses += Start-ManagedProcess -Name "frontend" -Title "DeerFlow - Frontend (3000)" -Port 3000 -WorkingDirectory $FrontendPath -StartupMessage "Starting frontend with pnpm run dev..." -Command "pnpm run dev"
Write-Host "✅ Frontend starting..."

Save-ManagedProcesses -Processes $managedProcesses

Write-Host "----------------------------------------------------"
Write-Host "Dependencies and migrations completed successfully." -ForegroundColor Green
if ($VisibleWindows) {
	Write-Host "LangGraph, Gateway, Frontend, and Nginx are launching in separate windows." -ForegroundColor Green
} else {
	Write-Host "LangGraph, Gateway, Frontend, and Nginx are running hidden in the background." -ForegroundColor Green
	Write-Host "Logs are written under $LogsPath" -ForegroundColor Yellow
	Write-Host "To stop everything, run .\start-dev.ps1 -Stop" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "👉 App URL: http://localhost:2026" -ForegroundColor Cyan
Write-Host ""
if ($VisibleWindows) {
	Write-Host "To stop everything later, close the 4 service windows or run .\start-dev.ps1 -Stop"
} else {
	$langGraphLog = ($managedProcesses | Where-Object { $_.Name -eq "langgraph" } | Select-Object -First 1).StdoutLog
	Write-Host "Use Get-Content -Wait '$langGraphLog' to watch service logs in this terminal."
}
