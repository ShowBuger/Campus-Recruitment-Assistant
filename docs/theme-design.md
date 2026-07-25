# 校招看板主题系统设计方案

## 目标

实现大规模组件级风格切换，而非简单的亮/暗色切换。用户可在多套完整设计语言之间切换，每一套包含独立的配色、圆角、阴影、间距、字体等视觉变量。

## 架构：CSS 自定义属性 + 设计令牌层

```
┌─────────────────────────────────────────────┐
│  data-theme="forest-light"                  │  ← <html> 属性
├─────────────────────────────────────────────┤
│  设计令牌 (Design Tokens)                    │
│  --color-primary / --radius-card / ...      │  ← CSS 变量
├─────────────────────────────────────────────┤
│  组件层                                      │
│  .sidebar / .card / .btn / .modal / ...     │  ← 引用变量
└─────────────────────────────────────────────┘
```

核心思路：所有组件样式只引用 CSS 变量，不写死颜色/尺寸值。切换主题只需更换根节点的 `data-theme` 属性值。

## 主题定义（6 套）

| 主题 ID | 名称 | 主色调 | 风格定位 |
|---------|------|--------|----------|
| `forest` | 森绿 | #386a57 | 沉稳、自然，当前默认风格 |
| `ocean` | 海蓝 | #2563eb | 专业、理性，适合长时间阅读 |
| `ember` | 暖橙 | #d97706 | 温暖、活力，适合秋招季 |
| `plum` | 紫韵 | #7c3aed | 现代、科技感 |
| `midnight` | 深夜 | #6366f1 | 暗色优先，护眼模式 |
| `mono` | 素白 | #374151 | 极简灰阶，低视觉刺激 |

每套主题同时定义 `light` 和 `dark` 两个变体，总共 12 种组合。

## 设计令牌清单（每套主题约 40 个变量）

### 1. 色彩系统（~20 个变量）
```
--color-bg          页面背景
--color-surface     卡片/面板背景
--color-sidebar     侧边栏背景
--color-ink         主文字色
--color-muted       次要文字色
--color-sub         辅助文字色
--color-line        分割线
--color-line-strong 强调分割线
--color-primary     主色（按钮、链接、激活态）
--color-primary-hover  主色悬停
--color-primary-subtle 主色浅底
--color-success     成功/通过
--color-warning     警告/进行中
--color-danger      危险/拒绝
--color-info        信息/提示
--color-success-subtle ... (浅底变体)
```

### 2. 形状系统（~8 个变量）
```
--radius-sm     4px    小圆角（tag、badge）
--radius-md     8px    中圆角（按钮、输入框）
--radius-lg     12px   大圆角（卡片、面板）
--radius-xl     16px   超大圆角（模态框）
--radius-full   9999px 胶囊形
```

### 3. 阴影系统（~4 个变量）
```
--shadow-card      卡片投影
--shadow-modal     模态框投影
--shadow-dropdown  下拉菜单投影
--shadow-active    激活态光晕
```

### 4. 间距系统（~6 个变量）
```
--space-xs   4px
--space-sm   8px
--space-md   16px
--space-lg   24px
--space-xl   40px
--space-2xl  64px
```

### 5. 字体系统（~4 个变量）
```
--font-body    正文字体栈
--font-heading 标题字体栈
--font-mono    等宽字体栈
--font-size-base 基准字号（可整体缩放）
```

## 实施步骤

### 阶段一：建立令牌层（1 个 CSS 文件）

创建 `static/themes/tokens.css`，使用 `[data-theme^="forest"]` 等选择器定义所有变量。

```css
/* 默认主题：森绿-亮色 */
:root,
[data-theme="forest-light"] {
  --color-bg: #f5f7fb;
  --color-primary: #386a57;
  --radius-lg: 12px;
  /* ... 共约 40 个变量 */
}

/* 森绿-暗色 */
[data-theme="forest-dark"] {
  --color-bg: #0a0e17;
  --color-primary: #4a8c6f;
  /* 只覆盖变化的变量，其余继承 */
}

/* 海蓝-亮色 */
[data-theme="ocean-light"] {
  --color-primary: #2563eb;
  --color-primary-hover: #1d4ed8;
  /* ... */
}
```

### 阶段二：重构组件样式（逐个文件迁移）

将所有硬编码的颜色/尺寸替换为变量引用。影响范围：

| 文件 | 组件数 | 迁移要点 |
|------|--------|----------|
| `index.html` 内联 `<style>` | ~30 个规则 | sidebar、topbar、card、btn、modal、table、badge |
| `pixelium-theme.css` | ~200 个规则 | 表单、通知、弹窗、日历、看板、登录页 |
| `pixelium-vue.css` | ~50 个规则 | 辅助布局、动画 |
| `docs.html` | ~20 个规则 | 文档页独立样式 |

### 阶段三：主题切换器 UI

右上角工具栏增加主题按钮，点击弹出面板：

```
┌─────────────────────┐
│  ◉ 森绿  ○ 海蓝     │  ← 色块选择配色
│  ○ 暖橙  ○ 紫韵     │
│  ○ 深夜  ○ 素白     │
│─────────────────────│
│  ☐ 深色模式         │  ← 亮/暗切换
│─────────────────────│
│  字号：─○───┬───    │  ← 缩放滑块
└─────────────────────┘
```

- 配色：6 个色块按钮，选中态加边框环
- 深色模式：独立开关（对所有配色生效）
- 字号缩放：滑块，范围 12px–18px，修改 `--font-size-base`
- 偏好保存到 `localStorage`

### 阶段四：过渡动画

切换主题时添加平滑过渡：

```css
body {
  transition: background-color 0.4s ease,
              color 0.4s ease;
}
```

所有引用 `--color-*` 变量的属性自动获得过渡效果。

## 工作量估算

| 阶段 | 内容 | 预计时间 |
|------|------|----------|
| 一 | 建立令牌层，定义 6 套主题变量 | 0.5 天 |
| 二 | 重构组件样式（迁移 ~300 个规则） | 2 天 |
| 三 | 主题切换器 UI + 偏好持久化 | 0.5 天 |
| 四 | 过渡动画 + 测试 | 0.5 天 |
| **合计** | | **3.5 天** |

## 注意事项

1. **渐进迁移**：先建令牌层，再逐个文件替换，过程中新旧并存，不阻塞功能迭代
2. **变量命名**：统一 `--{category}-{name}` 格式，禁止 `--blue` / `--green` 等语义模糊的名称
3. **暗色优先设计**：每个主题同时定义亮/暗变体，确保暗色模式下对比度达标
4. **性能**：CSS 变量在根节点一次性切换，浏览器原生支持，无 JS 开销
5. **兼容性**：CSS 自定义属性支持率 >96%，无需 polyfill
