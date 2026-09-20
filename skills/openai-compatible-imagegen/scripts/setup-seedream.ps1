param(
    [string]$ConfigPath = ""
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

try {
    if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
        if ([string]::IsNullOrWhiteSpace($env:APPDATA)) {
            throw "Windows APPDATA directory is unavailable."
        }
        $ConfigPath = Join-Path $env:APPDATA "WonderbellImagegen\.env"
    }

    $secureKey = Read-Host "火山 Ark API Key（粘贴后不会显示，这是正常的）" -AsSecureString
    $keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    try {
        $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
    }

    if ([string]::IsNullOrWhiteSpace($apiKey) -or $apiKey.Contains("`r") -or $apiKey.Contains("`n")) {
        throw "API Key 不能为空。"
    }

    $configDirectory = Split-Path -Parent $ConfigPath
    New-Item -ItemType Directory -Path $configDirectory -Force | Out-Null
    $temporaryPath = Join-Path $configDirectory (".env." + [Guid]::NewGuid().ToString("N") + ".tmp")
    $lines = @(
        "IMAGEGEN_PROVIDER=ark",
        "IMAGEGEN_API_KEY=$apiKey",
        "IMAGEGEN_BASE_URL=https://ark.cn-beijing.volces.com/api/v3",
        "IMAGEGEN_MODEL=doubao-seedream-5-0-pro-260628",
        "IMAGEGEN_TIMEOUT_SECONDS=180",
        "IMAGEGEN_GENERATIONS_PATH=/images/generations"
    )
    $utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText(
        $temporaryPath,
        (($lines -join [Environment]::NewLine) + [Environment]::NewLine),
        $utf8WithoutBom
    )
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $account = [Security.Principal.NTAccount]::new($identity)
    $rule = [Security.AccessControl.FileSystemAccessRule]::new(
        $identity,
        [Security.AccessControl.FileSystemRights]::FullControl,
        [Security.AccessControl.AccessControlType]::Allow
    )
    $acl = [Security.AccessControl.FileSecurity]::new()
    $acl.SetOwner($account)
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule($rule)
    Set-Acl -Path $temporaryPath -AclObject $acl
    Move-Item -Path $temporaryPath -Destination $ConfigPath -Force

    $apiKey = $null
    Write-Host ""
    Write-Host "配置完成。" -ForegroundColor Green
    Write-Host "以后直接告诉你的 AI 助手想生成什么图片即可。"
    Write-Host "Key 已保存在当前 Windows 用户的私有配置中。"
    exit 0
}
catch {
    Write-Host "配置失败：$($_.Exception.Message)" -ForegroundColor Red
    if ($temporaryPath -and (Test-Path $temporaryPath)) {
        Remove-Item -Path $temporaryPath -Force
    }
    exit 1
}
