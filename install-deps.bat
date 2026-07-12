@echo off
chcp 65001 >nul
title 校招信息看板 v0.3 - 安装依赖
cd /d "%~dp0"

echo.
echo ========================================
echo   校招信息看板 v0.3 - 一键安装依赖
echo ========================================
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo [错误] 没有找到 Python 启动器 py。
  echo 请先安装 Python 3.11+，并勾选 Add Python to PATH。
  echo.
  pause
  exit /b 1
)

echo [1/4] 检查 Python 版本...
py --version
if errorlevel 1 goto :fail

echo.
echo [2/4] 安装 requirements.txt 中的全部依赖...
py -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo.
echo [3/4] 验证全部运行依赖...
py -c "import fastapi, uvicorn, requests, dotenv, multipart, docx, pypdf, markdown, bleach"
if errorlevel 1 (
  echo [错误] 运行依赖验证失败。
  goto :fail
)
echo [完成] 全部运行依赖可正常导入。

echo.
echo [4/4] 验证内置简历分析 Skill...
if not exist "app\prompts\interview_analysis.md" (
  echo [错误] 缺少 app\prompts\interview_analysis.md
  echo 请重新克隆或下载完整项目后再安装。
  goto :fail
)
echo [完成] 简历分析 Skill 已随项目安装。

echo.
echo ========================================
echo   依赖安装完成！
echo ========================================
echo 下一步：双击 start-dashboard.bat 启动看板。
echo 第一次打开网页时，会弹窗引导你填写飞书配置。
echo.
pause
exit /b 0

:fail
echo.
echo ========================================
echo   安装失败，请把上面的错误信息截图发给我
echo ========================================
echo.
pause
exit /b 1
