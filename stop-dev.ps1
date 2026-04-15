$ErrorActionPreference = "Stop"
$RootPath = if ($PSScriptRoot) {
	(Resolve-Path $PSScriptRoot).Path
} else {
	(Get-Location).Path
}

$LogsPath = Join-Path $RootPath "logs"
$NginxConfigPath = Join-Path $RootPath "docker\nginx\nginx.local.conf"
$ManagedPorts = @(2026, 2024, 8001, 3000)

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
	$escapedRootPath = [Regex]::Escape($RootPath)
	$processes = Get-CimInstance Win32_Process | Where-Object {
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

	return $processes | Select-Object -ExpandProperty ProcessId -Unique
}

function Stop-RepoServices {
	foreach ($pass in 1..5) {
		foreach ($port in $ManagedPorts) {
			foreach ($listenerProcessId in (Get-ListenerPidsForPort -Port $port)) {
				Stop-ProcessTree -ProcessId $listenerProcessId
			}
		}

		foreach ($repoScopedProcessId in (Get-RepoScopedProcessPids | Sort-Object -Unique)) {
			Stop-ProcessTree -ProcessId $repoScopedProcessId
		}

		try {
			& nginx -c $NginxConfigPath -p $RootPath -s quit *> $null
		} catch {
		}

		$nginxPidFile = Join-Path $LogsPath "nginx.pid"
		if (Test-Path -LiteralPath $nginxPidFile) {
			try {
				$nginxPid = [int](Get-Content -LiteralPath $nginxPidFile | Select-Object -First 1)
				Stop-ProcessTree -ProcessId $nginxPid
			} catch {
			}
		}
	}

	foreach ($path in @(
		(Join-Path $LogsPath "start-dev-processes.json"),
		(Join-Path $LogsPath "nginx.pid")
	)) {
		if (Test-Path -LiteralPath $path) {
			try {
				Remove-Item -LiteralPath $path -Force
			} catch {
			}
		}
	}
}

Set-Location $RootPath
& (Join-Path $RootPath "start-dev.ps1") -Stop
Stop-RepoServices