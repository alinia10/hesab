@echo off
chcp 65001 >nul
title hesab - attendance to Excel
cd /d "%~dp0"
call windows\setup.bat || goto fail

echo.
echo Starting... the first run downloads Python and libraries and can take a few minutes.
echo The page opens in your browser.
echo Keep this window open while you use the page. Close it to stop.
echo.
uv run hesab-web
if errorlevel 1 goto fail
exit /b 0

:fail
echo.
echo Something went wrong. See the messages above.
pause
