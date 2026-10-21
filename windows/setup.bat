@echo off
rem One-time setup shared by start-web.bat and convert.bat:
rem installs uv (which brings Python and all libraries) and asks for the Gemini key.
set PYTHONUTF8=1

where uv >nul 2>nul
if not errorlevel 1 goto have_uv
if exist "%USERPROFILE%\.local\bin\uv.exe" goto add_path
echo Installing uv (one time only, needs internet) ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
:add_path
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
where uv >nul 2>nul
if errorlevel 1 (
    echo Could not install uv. Check your internet connection and try again.
    exit /b 1
)
:have_uv

if exist .env goto done
echo.
echo Paste your Gemini API key (from https://aistudio.google.com/apikey) and press Enter:
set /p GKEY=
if "%GKEY%"=="" (
    echo No key entered.
    exit /b 1
)
> .env echo GEMINI_API_KEY=%GKEY%
>> .env echo GEMINI_MODEL=gemini-3.8-flash
echo Key saved in .env
:done
exit /b 0
