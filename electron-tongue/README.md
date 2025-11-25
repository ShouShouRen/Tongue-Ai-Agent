# Electron Toung

## 相關技術

- **前端框架**: Electron 39.2.2 + React 19.2.0 + TypeScript
- **構建工具**: Vite (rolldown-vite 7.2.2)
- **套件管理**: pnpm
- **打包工具**: electron-builder 26.0.12

## 系統需求

- Node.js >= 18.0.0
- pnpm >= 8.0.0

## 快速開始

```bash

# 2. 安裝依賴
pnpm install

# 3. 啟動開發環境
pnpm run dev
```

## 開發指令

### 開發模式

| 指令                    | 說明                                 | 使用時機                                                   |
| ----------------------- | ------------------------------------ | ---------------------------------------------------------- |
| `pnpm run dev`          | 啟動完整開發環境（Electron + React） | **主要開發指令(拿到專案直接跑就能看到 electron 開發畫面)** |
| `pnpm run dev:react`    | 僅啟動 Vite 開發伺服器               | 只需測試前端功能                                           |
| `pnpm run dev:electron` | 僅啟動 Electron（需先編譯）          | 單獨測試 Electron 功能                                     |

> **注意**: 使用 `dev:electron` 前需先執行 `pnpm run transpile:electron`

### 編譯構建

| 指令                          | 說明                                                                                      | 輸出目錄         |
| ----------------------------- | ----------------------------------------------------------------------------------------- | ---------------- |
| `pnpm run build`              | 構建 React 前端                                                                           | `dist-react/`    |
| `pnpm run transpile:electron` | 編譯 Electron TypeScript 程式碼後需要重新編譯，編譯完成後才能執行 `pnpm run dev:electron` | `dist-electron/` |

### 打包發佈

| 指令                  | 平台           | 輸出檔案                          |
| --------------------- | -------------- | --------------------------------- |
| `pnpm run dist:mac`   | macOS (ARM64)  | `.dmg` 安裝檔                     |
| `pnpm run dist:win`   | Windows (x64)  | `.exe` (可攜版) + `.msi` (安裝版) |
| `pnpm run dist:linux` | Linux (ARMv7l) | `.AppImage`                       |

## 開發流程

### 日常開發

```bash
# 啟動開發環境（自動熱重載）
pnpm run dev
```

- **React 開發**: 編輯 `src/ui/` 下的檔案，自動熱重載
- **Electron 開發**: 編輯 `src/electron/` 下的檔案後，重新執行 `pnpm run dev`

### 應用程式打包

```bash
# 1. 構建前端
pnpm run build

# 2. 編譯 Electron
pnpm run transpile:electron

# 3. 打包（選擇目標平台）
pnpm run dist:mac     # macOS
pnpm run dist:win     # Windows
pnpm run dist:linux   # Linux
```
