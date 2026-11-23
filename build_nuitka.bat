@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python 3 was not found on PATH.
    exit /b 1
)

python -m nuitka --version >nul 2>nul
if errorlevel 1 (
    echo Nuitka is not installed. Install it with:
    echo     python -m pip install nuitka
    exit /b 1
)

python -m nuitka ^
    main.py ^
    --standalone ^
    --enable-plugin=tk-inter ^
    --windows-console-mode=disable ^
    --assume-yes-for-downloads ^
    --zig ^
    --output-dir=dist ^
    --output-filename=PascalBox.exe ^
    --company-name="Pascal Box" ^
    --product-name="Pascal Box" ^
    --file-description="Pascal Box IDE" ^
    --file-version=1.1.0.0 ^
    --product-version=1.1.0.0 ^
    --include-data-dir=samples=samples ^
    --include-data-files=README.md=README.md
if errorlevel 1 (
    echo.
    echo Nuitka build failed.
    exit /b 1
)

echo.
echo Build finished:
echo     dist\main.dist\PascalBox.exe
echo Copy the whole dist\main.dist folder to deploy the IDE.
