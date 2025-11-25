#!/bin/bash

echo "編譯 Electron 程式碼..."
pnpm run transpile:electron

echo "啟動 Vite 開發伺服器..."
pnpm run dev:react &
VITE_PID=$!

echo "等待 Vite 伺服器啟動..."
sleep 3

echo "啟動 Electron..."
electron .

echo "當 Electron 退出時，清理 Vite 進程..."
trap "kill $VITE_PID" EXIT

