@echo off
chcp 65001 >nul
setlocal

echo 編譯 Electron 程式碼...
call pnpm run transpile:electron

echo 啟動 Vite 開發伺服器...
start /B pnpm run dev:react

echo 等待 Vite 伺服器啟動...
timeout /t 3 /nobreak >nul

echo 啟動 Electron...
electron .

echo 當 Electron 退出時，清理 Vite 進程...
taskkill /F /FI "WINDOWTITLE eq vite*" >nul 2>&1
taskkill /F /FI "IMAGENAME eq node.exe" /FI "WINDOWTITLE eq *vite*" >nul 2>&1

echo 開發伺服器已停止
endlocal