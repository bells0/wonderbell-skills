param(
    [Parameter(Mandatory = $true)]
    [string]$SkillDir
)

$ErrorActionPreference = "Stop"
$temporaryRoot = Join-Path ([IO.Path]::GetTempPath()) ("wonderbell-imagegen-" + [Guid]::NewGuid().ToString("N"))
$serverJob = $null

try {
    New-Item -ItemType Directory -Path $temporaryRoot -Force | Out-Null
    $portProbe = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
    $portProbe.Start()
    $port = ([Net.IPEndPoint]$portProbe.LocalEndpoint).Port
    $portProbe.Stop()

    $pngBase64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    $serverJob = Start-Job -ArgumentList $port, $pngBase64 -ScriptBlock {
        param($Port, $PngBase64)
        $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $Port)
        try {
            $listener.Start()
            $client = $listener.AcceptTcpClient()
            try {
                $stream = $client.GetStream()
                $reader = New-Object IO.StreamReader($stream, [Text.Encoding]::ASCII, $false, 1024, $true)
                $requestLine = $reader.ReadLine()
                $headers = @{}
                while ($true) {
                    $line = $reader.ReadLine()
                    if ([string]::IsNullOrEmpty($line)) {
                        break
                    }
                    $separator = $line.IndexOf(":")
                    if ($separator -gt 0) {
                        $headers[$line.Substring(0, $separator).Trim().ToLowerInvariant()] = $line.Substring($separator + 1).Trim()
                    }
                }
                $contentLength = [int]$headers["content-length"]
                $buffer = New-Object char[] $contentLength
                $total = 0
                while ($total -lt $contentLength) {
                    $read = $reader.Read($buffer, $total, $contentLength - $total)
                    if ($read -le 0) {
                        break
                    }
                    $total += $read
                }
                $body = New-Object string($buffer, 0, $total)
                $responseBody = '{"data":[{"b64_json":"' + $PngBase64 + '"}]}'
                $responseBytes = [Text.Encoding]::UTF8.GetBytes($responseBody)
                $responseHeader = "HTTP/1.1 200 OK`r`nContent-Type: application/json`r`nContent-Length: $($responseBytes.Length)`r`nConnection: close`r`n`r`n"
                $headerBytes = [Text.Encoding]::ASCII.GetBytes($responseHeader)
                $stream.Write($headerBytes, 0, $headerBytes.Length)
                $stream.Write($responseBytes, 0, $responseBytes.Length)
                $stream.Flush()
                [pscustomobject]@{
                    RequestLine = $requestLine
                    Authorization = $headers["authorization"]
                    IdempotencyKey = $headers["idempotency-key"]
                    Body = $body
                }
            }
            finally {
                $client.Dispose()
            }
        }
        finally {
            $listener.Stop()
        }
    }

    Start-Sleep -Seconds 1
    $env:IMAGEGEN_PROVIDER = "ark"
    $env:IMAGEGEN_API_KEY = "fake-windows-key"
    $env:IMAGEGEN_BASE_URL = "http://127.0.0.1:$port/api/v3"
    $env:IMAGEGEN_MODEL = "seedream-test"
    $generator = Join-Path $SkillDir "scripts/generate-image.ps1"
    $config = Join-Path $SkillDir ".env.example"
    $outputDirectory = Join-Path $temporaryRoot "output"
    $generatorOutput = & pwsh -NoLogo -NoProfile -File $generator `
        -Execute -Prompt "test image" -Name "windows-test" `
        -OutputDir $outputDirectory -ConfigPath $config 2>&1
    $generatorExitCode = $LASTEXITCODE

    $completed = Wait-Job -Job $serverJob -Timeout 20
    if (-not $completed) {
        throw "Local fake API did not finish."
    }
    $request = Receive-Job -Job $serverJob
    if ($generatorExitCode -ne 0) {
        throw "Windows generator failed: $($generatorOutput -join [Environment]::NewLine)"
    }
    if ($request.RequestLine -ne "POST /api/v3/images/generations HTTP/1.1") {
        throw "Unexpected request path: $($request.RequestLine)"
    }
    if ($request.Authorization -ne "Bearer fake-windows-key") {
        throw "Bearer authentication was not sent."
    }
    if ([string]::IsNullOrWhiteSpace($request.IdempotencyKey)) {
        throw "Idempotency-Key was not sent."
    }
    $requestBody = $request.Body | ConvertFrom-Json
    if ($requestBody.model -ne "seedream-test" -or $requestBody.output_format -ne "png") {
        throw "Unexpected Ark request body."
    }

    $image = Get-ChildItem -Path $outputDirectory -Filter "*.png" -File -Recurse | Select-Object -First 1
    if (-not $image) {
        throw "Generated PNG was not saved."
    }
    $records = Get-ChildItem -Path $outputDirectory -Filter "*.json" -File -Recurse |
        ForEach-Object { [IO.File]::ReadAllText($_.FullName) }
    $recordText = $records -join "`n"
    if ($recordText.Contains("fake-windows-key") -or $recordText.Contains($pngBase64)) {
        throw "A secret or base64 image leaked into trace files."
    }
    Write-Host "PASS: native PowerShell generation request and output handling"
}
finally {
    if ($serverJob) {
        Stop-Job -Job $serverJob -ErrorAction SilentlyContinue
        Remove-Job -Job $serverJob -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -Path $temporaryRoot -Recurse -Force -ErrorAction SilentlyContinue
}
