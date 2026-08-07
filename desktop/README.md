# 校招信息看板 · 桌面应用

基于 Electron 的 Windows 桌面客户端，安全加载
[www.toudimianban.cloud](https://www.toudimianban.cloud)，因此与网页端共享同一套功能和数据。

## 在 Windows 上开发

```bash
# 安装依赖
npm install

# 启动开发模式
npm run dev
```

## 在 Windows 上打包

```bash
# 构建 Windows NSIS 安装包
npm run build:win
```

输出在 `dist-electron/`：

- `CampusBoard-<版本号>.exe` — Windows x64 安装程序
- `CampusBoard-<版本号>.exe.blockmap` — 增量更新块映射
- `latest.yml` — 桌面端自动更新元数据

安装器采用当前用户单击安装模式，安装到 Windows 标准应用目录，不要求管理员权限，
也不显示会在多阶段之间重置的辅助安装进度页。

## 发布新版本

1. 修改 `desktop/package.json` 的 `version`。
2. 执行 `npm run build:win`。
3. 使用发布脚本先上传安装包与 blockmap，最后原子切换 `latest.yml`，避免客户端读取到尚未复制完整的版本。

每个版本号对应的安装包和 blockmap 都是不可变文件；发布脚本会拒绝覆盖已存在的同版本产物，
需要重新发布时必须先提升版本号。

```bash
npm run build:win
./publish-local.sh
```

网页的“下载桌面端”和客户端自动更新均使用站内更新服务。已安装客户端启动 10 秒后检查更新，
之后每 6 小时检查一次。Windows 客户端会优先使用 blockmap 增量下载，差分不可用时自动回退完整安装包。
更新下载完毕后可立即重启升级，或在退出时自动安装。

如需消除 Windows SmartScreen 的“未知发布者”提示，在仓库 Secrets 中配置：

- `WINDOWS_CSC_LINK`：PFX 证书的 Base64 或下载地址
- `WINDOWS_CSC_KEY_PASSWORD`：证书密码

## 功能

| 功能 | 说明 |
|---|---|
| 独立窗口 | 1280×800，最小 900×600 |
| 系统托盘 | 关闭窗口 → 隐藏到托盘，右键退出 |
| 单实例 | 同一时间只允许一个应用 |
| 外部链接 | 在系统浏览器打开 |
| 自动更新 | 后台下载，重启安装；托盘支持手动检查 |
| 网络异常 | 提供重试或退出，不显示空白窗口 |
