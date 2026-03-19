@echo off
echo 安装 PyInstaller...
pip install pyinstaller

echo 开始打包...
pyinstaller --onefile --name "PDF盖章工具" main.py

echo.
echo 打包完成！exe 在 dist 目录下
pause
