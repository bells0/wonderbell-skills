[CmdletBinding()]
param(
    [switch]$Check,
    [switch]$Execute,
    [string]$Prompt = "",
    [string]$PromptFile = "",
    [string[]]$Reference = @(),
    [string]$Size = "",
    [string]$Name = "image",
    [string]$OutputDir = "generated-images",
    [string]$ConfigPath = ""
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

function Write-Utf8Text {
    param([string]$Path, [string]$Value)
    [System.IO.File]::WriteAllText($Path, $Value, $script:Utf8WithoutBom)
}

function Write-JsonFile {
    param([string]$Path, $Value)
    $json = ConvertTo-Json -InputObject $Value -Depth 12
    Write-Utf8Text -Path $Path -Value ($json + [Environment]::NewLine)
}

function Read-ImagegenConfig {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "尚未配置火山 Seedream。请先双击 setup-seedream.cmd。"
    }
    $values = @{}
    foreach ($rawLine in [System.IO.File]::ReadAllLines($Path)) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#")) {
            continue
        }
        if ($line.StartsWith("export ")) {
            $line = $line.Substring(7).TrimStart()
        }
        $separator = $line.IndexOf("=")
        if ($separator -lt 1) {
            throw "配置文件格式不正确：$Path"
        }
        $key = $line.Substring(0, $separator).Trim()
        $value = $line.Substring($separator + 1).Trim()
        if ($value.Length -ge 2) {
            $first = $value.Substring(0, 1)
            $last = $value.Substring($value.Length - 1, 1)
            if (($first -eq '"' -and $last -eq '"') -or ($first -eq "'" -and $last -eq "'")) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }
        $values[$key] = $value
    }
    return $values
}

function Get-Setting {
    param($Config, [string]$Name, [string]$Default = "")
    $environmentValue = [Environment]::GetEnvironmentVariable($Name)
    if (-not [string]::IsNullOrWhiteSpace($environmentValue)) {
        return $environmentValue.Trim()
    }
    if ($Config.ContainsKey($Name) -and -not [string]::IsNullOrWhiteSpace($Config[$Name])) {
        return $Config[$Name].Trim()
    }
    return $Default
}

function Get-ReferenceData {
    param([string]$Path)
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    $extension = [System.IO.Path]::GetExtension($resolved).ToLowerInvariant()
    $mimeTypes = @{
        ".png" = "image/png"
        ".jpg" = "image/jpeg"
        ".jpeg" = "image/jpeg"
        ".webp" = "image/webp"
    }
    if (-not $mimeTypes.ContainsKey($extension)) {
        throw "参考图只支持 PNG、JPEG 或 WebP：$Path"
    }
    $bytes = [System.IO.File]::ReadAllBytes($resolved)
    return [ordered]@{
        Path = $resolved
        Bytes = $bytes
        DataUrl = "data:$($mimeTypes[$extension]);base64,$([Convert]::ToBase64String($bytes))"
    }
}

function Get-ImageExtension {
    param([byte[]]$Bytes)
    if ($Bytes.Length -ge 8 -and
        $Bytes[0] -eq 0x89 -and $Bytes[1] -eq 0x50 -and $Bytes[2] -eq 0x4E -and
        $Bytes[3] -eq 0x47 -and $Bytes[4] -eq 0x0D -and $Bytes[5] -eq 0x0A -and
        $Bytes[6] -eq 0x1A -and $Bytes[7] -eq 0x0A) {
        return ".png"
    }
    if ($Bytes.Length -ge 3 -and $Bytes[0] -eq 0xFF -and $Bytes[1] -eq 0xD8 -and $Bytes[2] -eq 0xFF) {
        return ".jpg"
    }
    if ($Bytes.Length -ge 12 -and
        [Text.Encoding]::ASCII.GetString($Bytes, 0, 4) -eq "RIFF" -and
        [Text.Encoding]::ASCII.GetString($Bytes, 8, 4) -eq "WEBP") {
        return ".webp"
    }
    throw "服务返回的文件不是可识别的 PNG、JPEG 或 WebP 图片。"
}

try {
    if ($Check -and $Execute) {
        throw "Check 和 Execute 不能同时使用。"
    }
    if (-not $Check -and -not $Execute) {
        $Check = $true
    }
    if ($Prompt -and $PromptFile) {
        throw "Prompt 和 PromptFile 只能使用一个。"
    }
    if (-not $Prompt -and -not $PromptFile) {
        throw "必须提供图片描述。"
    }
    if ($Name -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$') {
        throw "Name 只能包含字母、数字、点、下划线和短横线。"
    }

    if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
        if ([string]::IsNullOrWhiteSpace($env:APPDATA)) {
            throw "Windows APPDATA directory is unavailable."
        }
        $ConfigPath = Join-Path $env:APPDATA "WonderbellImagegen\.env"
    }
    $ConfigPath = [System.IO.Path]::GetFullPath($ConfigPath)
    $config = Read-ImagegenConfig -Path $ConfigPath
    $provider = Get-Setting -Config $config -Name "IMAGEGEN_PROVIDER" -Default "ark"
    $apiKey = Get-Setting -Config $config -Name "IMAGEGEN_API_KEY"
    $baseUrl = Get-Setting -Config $config -Name "IMAGEGEN_BASE_URL"
    $model = Get-Setting -Config $config -Name "IMAGEGEN_MODEL"
    $timeoutText = Get-Setting -Config $config -Name "IMAGEGEN_TIMEOUT_SECONDS" -Default "180"
    $generationsPath = Get-Setting -Config $config -Name "IMAGEGEN_GENERATIONS_PATH" -Default "/images/generations"

    if ($provider -ne "ark") {
        throw "Windows 零环境脚本目前只支持火山 Ark Seedream。"
    }
    if ([string]::IsNullOrWhiteSpace($apiKey) -or [string]::IsNullOrWhiteSpace($baseUrl) -or [string]::IsNullOrWhiteSpace($model)) {
        throw "火山 Seedream 配置不完整。请重新双击 setup-seedream.cmd。"
    }
    $timeoutSeconds = 0
    if (-not [int]::TryParse($timeoutText, [ref]$timeoutSeconds) -or $timeoutSeconds -lt 1) {
        throw "配置中的超时时间不正确。"
    }
    $baseUri = $null
    if (-not [Uri]::TryCreate($baseUrl, [UriKind]::Absolute, [ref]$baseUri)) {
        throw "配置中的 Base URL 必须是完整地址。"
    }
    $isLocalTest = $baseUri.Host -in @("localhost", "127.0.0.1", "::1")
    if ($baseUri.Scheme -ne "https" -and -not ($baseUri.Scheme -eq "http" -and $isLocalTest)) {
        throw "配置中的 Base URL 必须使用 HTTPS。"
    }
    if (-not $generationsPath.StartsWith("/")) {
        throw "配置中的生成路径不正确。"
    }

    if ($PromptFile) {
        $resolvedPrompt = (Resolve-Path -LiteralPath $PromptFile).Path
        $promptText = [System.IO.File]::ReadAllText($resolvedPrompt, [Text.Encoding]::UTF8).Trim()
    }
    else {
        $promptText = $Prompt.Trim()
    }
    if ([string]::IsNullOrWhiteSpace($promptText)) {
        throw "图片描述不能为空。"
    }

    $referencePaths = @()
    foreach ($referenceArgument in $Reference) {
        $referencePaths += @($referenceArgument.Split("|") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    }
    $referenceData = @()
    foreach ($referencePath in $referencePaths) {
        $referenceData += Get-ReferenceData -Path $referencePath
    }

    $payload = [ordered]@{
        model = $model
        prompt = $promptText
        response_format = "b64_json"
        output_format = "png"
        watermark = $false
    }
    if (-not [string]::IsNullOrWhiteSpace($Size)) {
        $payload["size"] = $Size
    }
    if ($referenceData.Count -gt 0) {
        $payload["image"] = @($referenceData | ForEach-Object { $_.DataUrl })
    }

    $endpoint = $baseUrl.TrimEnd("/") + $generationsPath
    if ($Check) {
        [ordered]@{
            status = "ok"
            action = "check-only"
            provider = "ark"
            endpoint = $endpoint
            model = $model
            references = $referenceData.Count
        } | ConvertTo-Json -Depth 5
        exit 0
    }

    $runRoot = [System.IO.Path]::GetFullPath($OutputDir)
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss-fff"
    $runDirectory = Join-Path (Join-Path $runRoot $Name) ($timestamp + "-" + [Guid]::NewGuid().ToString("N").Substring(0, 8))
    New-Item -ItemType Directory -Path $runDirectory -Force | Out-Null

    $referenceRecords = @()
    foreach ($item in $referenceData) {
        $referenceRecords += [ordered]@{
            path = $item.Path
            bytes = $item.Bytes.Length
            sha256 = (Get-FileHash -LiteralPath $item.Path -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    $recordPayload = [ordered]@{}
    foreach ($key in $payload.Keys) {
        if ($key -eq "image") {
            $recordPayload[$key] = @($referenceData | ForEach-Object { "<data-url omitted; see reference_images>" })
        }
        else {
            $recordPayload[$key] = $payload[$key]
        }
    }
    $idempotencyKey = "imagegen-" + [Guid]::NewGuid().ToString("N")
    Write-JsonFile -Path (Join-Path $runDirectory "request.json") -Value ([ordered]@{
        provider = "ark"
        endpoint = $endpoint
        mode = "generations"
        idempotency_key = $idempotencyKey
        payload = $recordPayload
        reference_images = $referenceRecords
    })

    $runRecord = [ordered]@{
        schema_version = 1
        status = "in_progress"
        started_at = [DateTimeOffset]::Now.ToString("o")
        provider = "ark"
        mode = "generations"
        endpoint = $endpoint
        outputs = @()
    }
    Write-JsonFile -Path (Join-Path $runDirectory "run.json") -Value $runRecord
    $stopwatch = [Diagnostics.Stopwatch]::StartNew()

    try {
        $headers = @{
            Authorization = "Bearer $apiKey"
            Accept = "application/json"
            "Idempotency-Key" = $idempotencyKey
        }
        $body = ConvertTo-Json -InputObject $payload -Depth 8 -Compress
        $bodyBytes = [Text.Encoding]::UTF8.GetBytes($body)
        $response = Invoke-RestMethod -Method Post -Uri $endpoint -Headers $headers -ContentType "application/json; charset=utf-8" -Body $bodyBytes -TimeoutSec $timeoutSeconds
        $items = @($response.data)
        if ($items.Count -eq 0) {
            throw "服务没有返回图片。"
        }

        $safeResponseItems = @()
        $index = 0
        foreach ($item in $items) {
            $index += 1
            if (-not [string]::IsNullOrWhiteSpace($item.b64_json)) {
                try {
                    $imageBytes = [Convert]::FromBase64String($item.b64_json)
                }
                catch {
                    throw "服务返回了无效的图片数据。"
                }
                $safeResponseItems += [ordered]@{ b64_json = "<omitted after local image save>" }
            }
            elseif (-not [string]::IsNullOrWhiteSpace($item.url)) {
                $imageUri = $null
                if (-not [Uri]::TryCreate($item.url, [UriKind]::Absolute, [ref]$imageUri) -or $imageUri.Scheme -notin @("http", "https")) {
                    throw "服务返回了无效的图片地址。"
                }
                $downloadPath = Join-Path $runDirectory (".download-" + [Guid]::NewGuid().ToString("N"))
                try {
                    Invoke-WebRequest -UseBasicParsing -Uri $imageUri -OutFile $downloadPath -TimeoutSec $timeoutSeconds
                    $imageBytes = [System.IO.File]::ReadAllBytes($downloadPath)
                }
                finally {
                    if (Test-Path -LiteralPath $downloadPath) {
                        Remove-Item -LiteralPath $downloadPath -Force
                    }
                }
                $safeResponseItems += [ordered]@{ url = $imageUri.GetLeftPart([UriPartial]::Path) }
            }
            else {
                throw "服务返回的图片条目缺少内容。"
            }

            $extension = Get-ImageExtension -Bytes $imageBytes
            $imagePath = Join-Path $runDirectory (("{0:D2}" -f $index) + $extension)
            [System.IO.File]::WriteAllBytes($imagePath, $imageBytes)
            $runRecord.outputs += [ordered]@{
                path = $imagePath
                bytes = $imageBytes.Length
                sha256 = (Get-FileHash -LiteralPath $imagePath -Algorithm SHA256).Hash.ToLowerInvariant()
            }
        }

        Write-JsonFile -Path (Join-Path $runDirectory "response.json") -Value ([ordered]@{ data = $safeResponseItems })
        $runRecord.status = "success"
    }
    catch {
        $runRecord.status = "failed_or_uncertain"
        Write-JsonFile -Path (Join-Path $runDirectory "error.json") -Value ([ordered]@{
            type = $_.Exception.GetType().Name
            message = $_.Exception.Message
        })
        throw
    }
    finally {
        $stopwatch.Stop()
        $runRecord.duration_seconds = [Math]::Round($stopwatch.Elapsed.TotalSeconds, 3)
        $runRecord.finished_at = [DateTimeOffset]::Now.ToString("o")
        Write-JsonFile -Path (Join-Path $runDirectory "run.json") -Value $runRecord
    }

    [ordered]@{
        status = "success"
        run_dir = $runDirectory
        outputs = $runRecord.outputs
    } | ConvertTo-Json -Depth 8
    exit 0
}
catch {
    [Console]::Error.WriteLine("error: $($_.Exception.Message)")
    exit 2
}
