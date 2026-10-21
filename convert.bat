@echo off
chcp 65001 >nul
title hesab - attendance to Excel
rem Drag a PDF onto this file: the Excel is written next to the PDF.
cd /d "%~dp0"
call windows\setup.bat || goto end

if "%~1"=="" (
    echo Drag a scanned PDF onto convert.bat to convert it.
    goto end
)
echo Converting "%~nx1" ... this takes a few minutes.
uv run hesab "%~1"
if errorlevel 1 goto end
echo.
echo Done: "%~dpn1.xlsx"
start "" "%~dpn1.xlsx"

:end
echo.
pause
