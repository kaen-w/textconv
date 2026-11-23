#Requires -Version 5.1
<#
    TextConv for Windows —— 一键安装 / 卸载

    安装时会做这些事：
      1. 找 Python 3.9+；没有就自动装（winget / 官方安装包，国内镜像优先）
      2. 建 .venv，装依赖（清华 → 阿里 → 官方 PyPI 依次回退）
      3. 生成图标
      4. 把 .venv\Scripts 加进“用户 PATH”（这样命令行里能直接敲 tc）
      5. 注册开机自启（HKCU Run）
      6. 注册资源管理器右键菜单：任意文件 → TextConv 转换 → 复制为 SQL/JSON/...
      7. 注册“应用和功能”里的卸载项
      8. 跑自检并启动托盘

    卸载：  install.ps1 -Uninstall
    可选：  -NoAutostart  -NoContextMenu  -NoPath  -NoStart  -Quiet
            -Mirror https://pypi.tuna.tsinghua.edu.cn/simple
            -PythonExe C:\Python312\python.exe
#>
[CmdletBinding()]
param(
    [switch]$Uninstall,
    [switch]$NoAutostart,
    [switch]$NoContextMenu,
    [switch]$NoPath,
    [switch]$NoStart,
    [switch]$Quiet,
    [switch]$InstallerMode,
    [string]$Mirror = "",
    [string]$PythonExe = ""
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
if ($InstallerMode) {
    # NSIS 的 nsExec 按系统 ANSI 代码页解码子进程输出；这里对齐，避免中文变乱码
    try { [Console]::OutputEncoding = [System.Text.Encoding]::Default } catch { }
}

# ---------------------------------------------------------------- 常量
$Root = $PSScriptRoot
$Venv = Join-Path $Root '.venv'
$VenvPython = Join-Path $Venv 'Scripts\python.exe'
$VenvPythonW = Join-Path $Venv 'Scripts\pythonw.exe'
$VenvScripts = Join-Path $Venv 'Scripts'
$AppDir = Join-Path $env:APPDATA 'TextConv'
$IconPath = Join-Path $Root 'assets\textconv.ico'

$RunKey = 'Software\Microsoft\Windows\CurrentVersion\Run'
$RunValue = 'TextConv'
$UninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\TextConv'
$MenuBase = 'Software\Classes\*\shell\TextConv'
$StartupLnk = Join-Path ([Environment]::GetFolderPath('Startup')) 'TextConv.lnk'

$PythonVersion = '3.12.10'
$PythonSources = @(
    "https://mirrors.huaweicloud.com/python/$PythonVersion/python-$PythonVersion-amd64.exe",
    "https://registry.npmmirror.com/-/binary/python/$PythonVersion/python-$PythonVersion-amd64.exe",
    "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe"
)

$MenuItems = @(
    @{ Verb = '01sql';    Label = '复制为 SQL IN 子句'; Format = 'sql' },
    @{ Verb = '02excel';  Label = '复制为 Excel 粘贴';  Format = 'excel' },
    @{ Verb = '03json';   Label = '复制为 JSON 数组';   Format = 'json' },
    @{ Verb = '04tuple';  Label = '复制为 Python 元组'; Format = 'tuple' },
    @{ Verb = '05list';   Label = '复制为 Python 列表'; Format = 'list' },
    @{ Verb = '06column'; Label = '复制为 Excel 一列';  Format = 'column' }
)

# ---------------------------------------------------------------- 输出
function Write-Step($message) {
    Write-Host ''
    Write-Host "==> $message" -ForegroundColor Cyan
}
function Write-Ok($message) {
    Write-Host "    [ok] $message" -ForegroundColor Green
}
function Write-Note($message) {
    Write-Host "    [..] $message" -ForegroundColor Yellow
}
function Fail($message) {
    Write-Host ''
    Write-Host "  [失败] $message" -ForegroundColor Red
    exit 1
}
function Ask-Yes($question) {
    if ($Quiet) { return $true }
    $answer = Read-Host "$question [Y/n]"
    return (-not $answer) -or ($answer -match '^(y|yes|Y|YES|是)$')
}

# ---------------------------------------------------------------- 注册表（.NET API，避免 * 被当通配符）
function Set-RegValue([string]$subKey, [string]$name, [string]$value) {
    $key = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($subKey)
    try { $key.SetValue($name, $value, [Microsoft.Win32.RegistryValueKind]::String) }
    finally { $key.Close() }
}
function Set-RegDword([string]$subKey, [string]$name, [int]$value) {
    $key = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($subKey)
    try { $key.SetValue($name, $value, [Microsoft.Win32.RegistryValueKind]::DWord) }
    finally { $key.Close() }
}
function Remove-RegValue([string]$subKey, [string]$name) {
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($subKey, $true)
    if ($null -ne $key) {
        try { $key.DeleteValue($name, $false) } finally { $key.Close() }
    }
}
function Remove-RegTree([string]$subKey) {
    try {
        [Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($subKey, $false)
    } catch { }
}

# ---------------------------------------------------------------- Python
function Test-Python([string]$exe) {
    if (-not $exe) { return $null }
    try {
        $out = & $exe -c "import sys; print(str(sys.version_info[0]) + '|' + str(sys.version_info[1]) + '|' + sys.executable)" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $out) { return $null }
        $parts = ($out | Select-Object -First 1).Trim().Split('|')
        $major = [int]$parts[0]
        $minor = [int]$parts[1]
        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 9)) { return $null }
        return $parts[2]
    } catch {
        return $null
    }
}

function Find-Python {
    $candidates = @()
    if ($PythonExe) { $candidates += $PythonExe }

    foreach ($name in @('python', 'python3')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source) { $candidates += $cmd.Source }
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try {
            $exe = & py -3 -c "import sys; print(sys.executable)" 2>$null
            if ($exe) { $candidates += $exe.Trim() }
        } catch { }
    }
    foreach ($pattern in @(
        "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
        "$env:ProgramFiles\Python3*\python.exe",
        "C:\Python3*\python.exe"
    )) {
        $candidates += @(Get-ChildItem $pattern -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
    }

    foreach ($candidate in $candidates) {
        $found = Test-Python $candidate
        if ($found) { return $found }
    }
    return $null
}

function Install-Python {
    Write-Step "没有找到可用的 Python 3.9+"
    if (-not (Ask-Yes "要现在自动安装 Python $PythonVersion 吗？（仅当前用户，不需要管理员）")) {
        Fail '没有 Python 无法继续。装好 Python 3.9+ 后再运行本脚本。'
    }

    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Step '尝试用 winget 安装 Python 3.12'
        try {
            & winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements --silent 2>&1 | Out-Null
        } catch { }
        $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                    [Environment]::GetEnvironmentVariable('Path', 'User')
        $found = Find-Python
        if ($found) { Write-Ok "winget 装好了：$found"; return $found }
        Write-Note 'winget 没成功，改用官方安装包'
    }

    $installer = Join-Path $env:TEMP "textconv-python-$PythonVersion-amd64.exe"
    $downloaded = $false
    foreach ($url in $PythonSources) {
        try {
            Write-Step "下载 Python：$url"
            Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing -TimeoutSec 600
            $downloaded = $true
            break
        } catch {
            Write-Note "下载失败：$($_.Exception.Message)"
        }
    }
    if (-not $downloaded) {
        Fail "Python 下载失败。请手动安装 Python 3.9+（https://www.python.org/downloads/），再运行本脚本。"
    }

    Write-Step '静默安装 Python（仅当前用户）'
    Start-Process -FilePath $installer -Wait -ArgumentList @(
        '/quiet', 'InstallAllUsers=0', 'PrependPath=1', 'Include_test=0', 'Include_launcher=1'
    )
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User')
    $found = Find-Python
    if (-not $found) {
        Fail 'Python 安装完成但没找到，请注销后重新运行 install.bat。'
    }
    Write-Ok "Python 已就绪：$found"
    return $found
}

# ---------------------------------------------------------------- 依赖
function Install-Dependencies {
    $indexes = @()
    if ($Mirror) {
        $hostName = ([Uri]$Mirror).Host
        $indexes += @{ Url = $Mirror; Host = $hostName }
    }
    $indexes += @(
        @{ Url = 'https://pypi.tuna.tsinghua.edu.cn/simple'; Host = 'pypi.tuna.tsinghua.edu.cn' },
        @{ Url = 'https://mirrors.aliyun.com/pypi/simple/'; Host = 'mirrors.aliyun.com' },
        @{ Url = 'https://pypi.org/simple'; Host = 'pypi.org' }
    )

    $requirements = Join-Path $Root 'requirements-win.txt'
    foreach ($index in $indexes) {
        Write-Step "安装依赖（PyPI 源：$($index.Url)）"
        & $VenvPython -m pip install --disable-pip-version-check --no-input `
            -i $index.Url --trusted-host $index.Host -r $requirements
        if ($LASTEXITCODE -ne 0) {
            Write-Note '这个源失败，换下一个'
            continue
        }
        Write-Ok '运行库安装完成'

        & $VenvPython -m pip install --disable-pip-version-check --no-input `
            -i $index.Url --trusted-host $index.Host -e $Root
        if ($LASTEXITCODE -eq 0) {
            Write-Ok 'TextConv 已安装（可编辑模式）'
            return
        }
        Write-Note '可编辑安装失败，改成普通安装'
        & $VenvPython -m pip install --disable-pip-version-check --no-input `
            -i $index.Url --trusted-host $index.Host $Root
        if ($LASTEXITCODE -eq 0) {
            Write-Ok 'TextConv 已安装'
            return
        }
        Write-Note '这个源连包本身也装不上，换下一个'
    }
    Fail "依赖安装失败。可以手动指定镜像，例如：`n  install.bat -Mirror https://pypi.tuna.tsinghua.edu.cn/simple"
}

# ---------------------------------------------------------------- 环境变量 / 注册表集成
function Add-UserPath([string]$directory) {
    $current = [Environment]::GetEnvironmentVariable('Path', 'User')
    $parts = @()
    if ($current) { $parts = @($current -split ';' | Where-Object { $_.Trim() }) }
    $exists = $parts | Where-Object { $_.TrimEnd('\') -ieq $directory.TrimEnd('\') }
    if ($exists) {
        Write-Ok "用户 PATH 里已经有：$directory"
    } else {
        $newPath = (@($parts) + $directory) -join ';'
        [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
        Write-Ok "已加入用户 PATH：$directory"
    }
    if (($env:Path -split ';') -notcontains $directory) {
        $env:Path = "$env:Path;$directory"
    }
}

function Remove-UserPath([string]$directory) {
    $current = [Environment]::GetEnvironmentVariable('Path', 'User')
    if (-not $current) { return }
    $parts = @($current -split ';' | Where-Object { $_.Trim() })
    $kept = @($parts | Where-Object { $_.TrimEnd('\') -ine $directory.TrimEnd('\') })
    if ($kept.Count -ne $parts.Count) {
        [Environment]::SetEnvironmentVariable('Path', ($kept -join ';'), 'User')
        Write-Ok "已从用户 PATH 移除：$directory"
    }
}

function Register-Autostart {
    Set-RegValue $RunKey $RunValue ('"{0}" -m textconv.win_tray' -f $VenvPythonW)
    Write-Ok '已注册开机自启（HKCU\...\Run）'
}

function Unregister-Autostart {
    Remove-RegValue $RunKey $RunValue
    if (Test-Path $StartupLnk) { Remove-Item $StartupLnk -Force -ErrorAction SilentlyContinue }
    Write-Ok '已移除开机自启'
}

function Register-ContextMenu {
    Remove-RegTree $MenuBase
    Set-RegValue $MenuBase '' 'TextConv 转换'
    Set-RegValue $MenuBase 'MUIVerb' 'TextConv 转换'
    Set-RegValue $MenuBase 'SubCommands' ''
    if (Test-Path $IconPath) { Set-RegValue $MenuBase 'Icon' $IconPath }

    foreach ($item in $MenuItems) {
        $key = "$MenuBase\shell\$($item.Verb)"
        $commandKey = "$key\command"
        Set-RegValue $key '' $item.Label
        Set-RegValue $key 'MUIVerb' $item.Label
        Set-RegValue $commandKey '' ('"{0}" -m textconv.fileconv {1} "%1"' -f $VenvPythonW, $item.Format)
    }
    Write-Ok '已注册资源管理器右键菜单（任意文件 → TextConv 转换）'
}

function Register-UninstallEntry([string]$version) {
    Set-RegValue $UninstallKey 'DisplayName' 'TextConv'
    Set-RegValue $UninstallKey 'DisplayVersion' $version
    Set-RegValue $UninstallKey 'Publisher' 'TextConv'
    Set-RegValue $UninstallKey 'InstallLocation' $Root
    Set-RegValue $UninstallKey 'DisplayIcon' $IconPath
    Set-RegValue $UninstallKey 'UninstallString' ('powershell -NoProfile -ExecutionPolicy Bypass -File "{0}" -Uninstall' -f (Join-Path $Root 'install.ps1'))
    Set-RegDword $UninstallKey 'NoModify' 1
    Set-RegDword $UninstallKey 'NoRepair' 1
    Write-Ok '已注册卸载项（设置 → 应用 里能看到）'
}

# ---------------------------------------------------------------- 安装流程
function Invoke-Install {
    Write-Host ''
    Write-Host '  TextConv for Windows' -ForegroundColor White
    Write-Host '  文本 → SQL IN / Excel / JSON / Python，一键粘贴' -ForegroundColor DarkGray

    $python = Find-Python
    if ($python) {
        Write-Ok "使用 Python：$python"
    } else {
        $python = Install-Python
    }

    if (-not (Test-Path $VenvPython)) {
        Write-Step '创建虚拟环境 .venv'
        & $python -m venv $Venv
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPython)) {
            Fail '创建虚拟环境失败（可能是目录没有写权限，换个目录再试）'
        }
        Write-Ok '虚拟环境就绪'
    } else {
        Write-Ok '.venv 已存在'
    }

    Install-Dependencies

    Write-Step '准备图标'
    New-Item -ItemType Directory -Path (Split-Path $IconPath) -Force | Out-Null
    $shippedIcon = Join-Path $Root 'assets\textconv.ico'
    try {
        if (Test-Path $shippedIcon) {
            Copy-Item -Path $shippedIcon -Destination $IconPath -Force
            Write-Ok "图标已就位：$IconPath"
        } else {
            $iconScript = @"
from textconv.win_tray import _make_icon
_make_icon().save(r'$IconPath', sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
"@
            & $VenvPython -c $iconScript
            if (Test-Path $IconPath) { Write-Ok "图标已生成：$IconPath" }
        }
    } catch {
        Write-Note '图标准备失败，不影响使用'
    }

    if (-not $NoPath) {
        Write-Step '写入环境变量'
        Add-UserPath $VenvScripts
    }

    Write-Step '注册表集成'
    if (-not $NoAutostart) { Register-Autostart } else { Write-Note '跳过开机自启（-NoAutostart）' }
    if (-not $NoContextMenu) { Register-ContextMenu } else { Write-Note '跳过右键菜单（-NoContextMenu）' }

    $version = '0.2.9'
    try {
        $version = (& $VenvPython -c "import textconv; print(textconv.__version__)" 2>$null | Select-Object -First 1).Trim()
    } catch { }
    Register-UninstallEntry $version

    Write-Step '自检'
    & $VenvPython -m textconv.win_tray --self-test
    $selfTestOk = ($LASTEXITCODE -eq 0)

    if (-not $NoStart) {
        Write-Step '启动托盘'
        # 升级场景：旧进程如果还在，会因为单实例锁让新进程直接退出，界面仍是旧版本
        $stale = @(Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like '*textconv.win_tray*' })
        if ($stale.Count -gt 0) {
            foreach ($proc in $stale) { Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue }
            Start-Sleep -Milliseconds 600
            Write-Note "已结束旧的托盘进程（$($stale.Count) 个）"
        }
        Start-Process -FilePath $VenvPythonW -ArgumentList '-m', 'textconv.win_tray' -WorkingDirectory $Root -WindowStyle Hidden
        Start-Sleep -Seconds 2
        $running = @(Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like '*textconv.win_tray*' }).Count -gt 0
        if ($running) { Write-Ok '托盘已启动，看右下角蓝色的 TC' } else { Write-Note '没检测到托盘进程，运行 debug.bat 看日志' }
    }

    Write-Host ''
    Write-Host '  安装完成' -ForegroundColor Green
    Write-Host ''
    Write-Host '  现在可以：'
    Write-Host '    · 复制文字 → Ctrl+Alt+Shift+S → 光标处直接出现 SQL IN'
    Write-Host '    · 任意文件右键 → TextConv 转换 → 复制为 SQL/JSON/...'
    Write-Host '    · 命令行直接敲 tc --formats（新开的终端里生效）'
    Write-Host ''
    if (-not $selfTestOk) {
        Write-Host '  [注意] 自检没有全部通过，把上面的输出发给我看看。' -ForegroundColor Yellow
    }
}

# ---------------------------------------------------------------- 卸载流程
function Invoke-Uninstall {
    Write-Host ''
    Write-Host '  卸载 TextConv' -ForegroundColor White

    Write-Step '停止托盘进程'
    $procs = @(Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*textconv*' })
    foreach ($proc in $procs) {
        try { Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue } catch { }
    }
    if ($procs.Count -gt 0) { Write-Ok "已结束 $($procs.Count) 个进程" } else { Write-Ok '没有在运行的进程' }

    Write-Step '清理注册表'
    Unregister-Autostart
    Remove-RegTree $MenuBase
    Write-Ok '已移除右键菜单'
    Remove-RegTree $UninstallKey
    Write-Ok '已移除卸载项'

    Write-Step '清理环境变量'
    Remove-UserPath $VenvScripts

    if (Test-Path $Venv) {
        Write-Step '删除虚拟环境'
        if (Ask-Yes '要删除 .venv 吗？（会删掉依赖，重新安装需要重新下载）') {
            Remove-Item $Venv -Recurse -Force -ErrorAction SilentlyContinue
            Write-Ok '.venv 已删除'
        } else {
            Write-Note '保留 .venv'
        }
    }

    if (Test-Path $IconPath) { Remove-Item $IconPath -Force -ErrorAction SilentlyContinue }

    Write-Host ''
    Write-Host '  卸载完成。' -ForegroundColor Green
    Write-Host "  如果连目录也不要了，直接删掉：$Root" -ForegroundColor DarkGray
    Write-Host ''
}

# ---------------------------------------------------------------- 入口
if ($Uninstall) {
    Invoke-Uninstall
} else {
    Invoke-Install
}
