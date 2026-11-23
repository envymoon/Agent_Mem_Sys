<#
Windows entry point for the local profiling study. Everything runs inside WSL2 Ubuntu as root, on the WSL ext4
disk (which lives on your NVMe); the GPU is used through the Windows NVIDIA driver (CUDA on WSL).

Run with PowerShell 7:
  C:\Users\ianha\Documents\Codex\Tools\PowerShell\7.6.5\pwsh.exe -File scripts\win\memprof.ps1 <command> [args]

commands:
  check                      show Windows-side facts: WSL distros/version, GPU + driver, RAM, .wslconfig
  install-wsl                install Ubuntu-24.04 under WSL2 (needs admin, may need a reboot)
  clone [-Branch b]          clone/update the repo inside WSL at /root/Agent_Mem_Sys (NOT under /mnt/c)
  setup                      scripts/local/setup.sh inside WSL (CUDA toolkit, llama.cpp, services, models)
  suite <suites...>          scripts/local/run_local_suite.sh <suites> in the background (log: results/local/<host>/suite.log)
  status                     tail of the suite log + GPU state
  shell "<bash command>"     run an arbitrary bash command inside the repo in WSL
#>
param(
  [Parameter(Position = 0)][string]$Command = "check",
  [Parameter(Position = 1, ValueFromRemainingArguments = $true)][string[]]$Rest,
  [string]$Distro = "Ubuntu-24.04",
  [string]$Branch = "claude/gifted-maxwell-td8cnz",
  [string]$Repo = "https://github.com/envymoon/Agent_Mem_Sys.git",
  [string]$SuiteEnv = ""   # extra env for setup/suite, e.g. -SuiteEnv "PROFILE=q4b TURNS=100"
)
$ErrorActionPreference = "Stop"
$RepoDir = "/root/Agent_Mem_Sys"

function Invoke-Wsl([string]$bash) {
  & wsl.exe -d $Distro -u root -- bash -lc $bash
  if ($LASTEXITCODE -ne 0) { throw "WSL command failed ($LASTEXITCODE): $bash" }
}

switch ($Command) {
  "check" {
    Write-Host "== WSL"; & wsl.exe --status; & wsl.exe -l -v
    Write-Host "== GPU"; & nvidia-smi --query-gpu=name,memory.total,memory.used,driver_version,pcie.link.gen.max,pcie.link.width.max --format=csv
    $cs = Get-CimInstance Win32_ComputerSystem
    Write-Host ("== RAM {0:N1} GB" -f ($cs.TotalPhysicalMemory / 1GB))
    Get-PhysicalDisk | Select-Object FriendlyName, MediaType, BusType, @{n = "SizeGB"; e = { [math]::Round($_.Size / 1GB) } } | Format-Table
    $cfg = Join-Path $env:USERPROFILE ".wslconfig"
    if (Test-Path $cfg) { Write-Host "== $cfg"; Get-Content $cfg } else {
      Write-Host "== no .wslconfig: WSL2 gets 50% of RAM. For the DRAM-tier / MoE runs consider:"
      Write-Host "[wsl2]`nmemory=<~75% of RAM>GB`nswap=8GB"
    }
  }
  "install-wsl" { & wsl.exe --install -d $Distro --no-launch; Write-Host "then start '$Distro' once to finish, or reboot if asked" }
  "clone" {
    Invoke-Wsl "command -v git >/dev/null || (apt-get update -q && apt-get install -y -q git); if [ -d $RepoDir/.git ]; then cd $RepoDir && git fetch -q origin $Branch && git checkout -q $Branch && git pull -q --ff-only origin $Branch; else git clone -q -b $Branch $Repo $RepoDir; fi; cd $RepoDir && git log --oneline -1"
  }
  "setup" { Invoke-Wsl "cd $RepoDir && $SuiteEnv scripts/local/setup.sh" }
  "suite" {
    $s = ($Rest -join " ")
    Invoke-Wsl "cd $RepoDir && mkdir -p results/local && (export $SuiteEnv HOME=/root; nohup scripts/local/run_local_suite.sh $s > results/local/suite_console.log 2>&1 &) ; sleep 2; echo started: $s"
  }
  "status" { Invoke-Wsl "cd $RepoDir && tail -n 25 results/local/*/suite.log 2>/dev/null; nvidia-smi --query-gpu=utilization.gpu,memory.used,power.draw --format=csv" }
  "shell" { Invoke-Wsl "cd $RepoDir && $($Rest -join ' ')" }
  default { Get-Help $PSCommandPath; exit 1 }
}
