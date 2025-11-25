#!/usr/bin/env node

const path = require('path');
const fs = require('fs');

const findElectronInstall = () => {
  const nodeModulesPath = path.join(process.cwd(), 'node_modules');
  
  const pnpmElectronPath = path.join(nodeModulesPath, '.pnpm');
  if (fs.existsSync(pnpmElectronPath)) {
    const entries = fs.readdirSync(pnpmElectronPath);
    for (const entry of entries) {
      if (entry.startsWith('electron@')) {
        const installPath = path.join(pnpmElectronPath, entry, 'node_modules', 'electron', 'install.js');
        if (fs.existsSync(installPath)) {
          return installPath;
        }
      }
    }
  }
  
  const standardPath = path.join(nodeModulesPath, 'electron', 'install.js');
  if (fs.existsSync(standardPath)) {
    return standardPath;
  }
  
  return null;
};

const installPath = findElectronInstall();
if (installPath) {
  console.log('正在安裝 Electron 二進制文件...');
  try {
    require(installPath);
    console.log('Electron 安裝完成！');
  } catch (error) {
    console.error('Electron 安裝失敗:', error.message);
    process.exit(1);
  }
} else {
  console.log('未找到 Electron，跳過安裝步驟。');
}

