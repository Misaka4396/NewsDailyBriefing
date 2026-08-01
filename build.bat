@echo off
chcp 65001 >nul
echo ============================================
echo   全球每日新闻日报推送器 - 打包脚本
echo   Daily Global News Briefing - Build Script
echo ============================================
echo.

REM 检查 Python 3
py -3 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python 3，请先安装 Python 3.9+
    pause
    exit /b 1
)

REM 安装依赖
echo [1/4] 安装依赖...
py -3 -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)

REM 生成图标
echo [2/4] 生成应用图标...
py -3 generate_icon.py
if %errorlevel% neq 0 (
    echo [警告] 图标生成失败，将使用默认图标
)

REM 清理旧的构建
echo [3/4] 清理旧的构建文件...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

REM PyInstaller 打包
echo [4/4] 开始打包为 EXE...
py -3 -m PyInstaller ^
    --name="NewsDailyBriefing" ^
    --windowed ^
    --onefile ^
    --add-data="assets;assets" ^
    --hidden-import=ttkbootstrap ^
    --hidden-import=pystray ^
    --hidden-import=PIL ^
    --hidden-import=PIL.Image ^
    --hidden-import=PIL.ImageDraw ^
    --hidden-import=cryptography ^
    --hidden-import=cryptography.fernet ^
    --hidden-import=bs4 ^
    --hidden-import=schedule ^
    --hidden-import=requests ^
    --hidden-import=xml.etree.ElementTree ^
    --hidden-import=email.mime.text ^
    --hidden-import=email.mime.multipart ^
    --icon=assets/icon.ico ^
    --clean ^
    main.py

if %errorlevel% equ 0 (
    echo.
    echo ============================================
    echo   打包成功!
    echo   输出文件: dist\NewsDailyBriefing.exe
    echo ============================================
) else (
    echo.
    echo [错误] 打包失败，请检查错误信息
)

pause
