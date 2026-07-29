# 校招信息看板 · 桌面应用

基于 Electron 的 Windows 桌面客户端，加载 [toudimianban.cloud](https://toudimianban.cloud)。

## 在 Windows 上开发

```bash
# 安装依赖
npm install

# 启动开发模式
npm run dev
```

## 在 Windows 上打包

```bash
# 构建 Windows 安装包 (NSIS + Portable)
npm run build:win
```

输出在 `dist-electron/`：
- `校招信息看板 Setup 1.0.0.exe` — NSIS 安装程序
- `校招信息看板-1.0.0-portable.exe` — 便携版（无需安装）

## 从 Linux 交叉编译到 Windows

```bash
# 需要 wine
sudo apt install wine64
npm run build:win
```

## 功能

| 功能 | 说明 |
|---|---|
| 独立窗口 | 1280×800，最小 900×600 |
| 系统托盘 | 关闭窗口 → 隐藏到托盘，右键退出 |
| 单实例 | 同一时间只允许一个应用 |
| 外部链接 | 在系统浏览器打开 |
| 开机自启 | 可在系统设置中启用 |
