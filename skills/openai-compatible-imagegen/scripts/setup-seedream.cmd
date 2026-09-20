@echo off
setlocal
chcp 65001 >nul
title 火山 Seedream 一键配置

echo 火山 Seedream 一键配置
echo.
echo 接下来只需要粘贴一次 API Key。
echo 粘贴时屏幕不会显示字符，这是正常的。
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-seedream.ps1"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
  echo 现在可以关闭这个窗口，然后直接告诉你的 AI 助手想生成什么图片。
) else (
  echo 配置没有完成。请把上面的错误提示发给你的 AI 助手。
)
echo 按任意键关闭窗口。
pause >nul
exit /b %EXIT_CODE%
