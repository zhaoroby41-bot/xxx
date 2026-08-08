# Tech Stack

## 数据输入

- Excel (.xlsx) 文件 — 包含小红书矩阵账号的周度运营数据
- 字段包括：作者昵称、笔记发布时间、累计阅读数、累计评论数、累计收藏数、点赞数、分享数、新增粉丝数等

## 输出格式

- HTML 单文件报告（自包含样式和脚本）
- 深色主题，渐变背景，响应式布局
- 中文内容，面向品牌方阅读

## 前端库

- **Chart.js 4.4.0** — 图表渲染（折线图、饼图、雷达图、柱状图等）
- **chartjs-plugin-datalabels 2.2.0** — 图表数据标签
- 均通过 CDN (jsdelivr) 引入

## 分析引擎

- AI 提示词驱动的分析流程
- 提示词模板定义在 `矩阵笔记内容分析-提示词模板.md`
- 输入 Excel 数据 → AI 分析 → 输出 HTML 报告

## 样式规范

- CSS-in-HTML（无外部样式表）
- 字体：-apple-system, BlinkMacSystemFont, SF Pro Display, PingFang SC
- 配色：深色背景 (#0f0c29 → #1a1a2e → #16213e)，小红书品牌红 (#ff2442) 为主色调
- 响应式断点：1024px, 768px

## 常用操作

- **生成报告**：将 Excel 数据填入提示词模板，通过 AI 生成 HTML 报告
- **预览报告**：直接在浏览器中打开 HTML 文件
- **更新数据**：替换或新增 Excel 文件（命名格式：`YYYYMMDD笔记.xlsx`）
