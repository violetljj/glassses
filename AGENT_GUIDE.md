# Agent 行为准则与技能手册

此文档旨在为 Agent 提供行为规范与可用能力速查，每次任务开始前请务必检视。

## 🔴 核心指令 (Core Directives)

1.  **全中文交互 (Mandatory Chinese)**：
    *   **思考过程 (Thinking Process)**：必须严厉执行使用**中文**进行逻辑推演和规划。
    *   **最终回复 (Response)**：必须使用**中文**回答用户指令。
    *   **文档与注释**：除非特定代码保留字，生成的文档内容、代码注释应优先使用中文。

## 🛠️ 可用技能 (Available Skills)

系统目前已加载以下技能，遇到相关任务时应主动查阅 (`view_file SKILL.md`) 并使用：

### 🎨 设计与创意 (Design & Creativity)
*   **frontend-design**: 核心技能。构建高质量、具有“高级感”和设计美学的前端界面（如网站、仪表盘）。拒绝平庸的 AI 生成感。
*   **algorithmic-art**: 使用 p5.js 代码创建生成艺术、流场或粒子系统。
*   **canvas-design**: 设计排版精美的静态海报或文档（输出 .png/.pdf）。
*   **slack-gif-creator**: 制作专用于 Slack 的高质量动画表情包 (GIF)。
*   **theme-factory**: 为各类产出物（文档、网页、幻灯片）生成配套的主题配色与字体方案。
*   **brand-guidelines**: 严格遵循 Anthropic 官方品牌设计规范（颜色、排版）。

### 💻 技术与构建 (Technology & Build)
*   **web-artifacts-builder**: 构建功能复杂、多组件交互的网页应用（基于 React, Tailwind, shadcn/ui）。
*   **webapp-testing**: 使用 Playwright 对本地 Web 应用进行自动化端到端测试、调试及截图。
*   **mcp-builder**: 构建 MCP (Model Context Protocol) 服务器，用于连接外部 API 或数据源。
*   **skill-creator**: 元技能。用于创建新技能或更新现有技能的指南。

### 📄 文档与办公 (Office Productivity)
*   **docx**: 专业级 Word 文档处理（支持修订模式、批注、格式保持）。
*   **xlsx**: 强大的 Excel 电子表格处理（支持复杂公式、图表分析）。
*   **pptx**: PowerPoint 演示文稿制作与编辑（布局设计、演讲者备注）。
*   **pdf**: PDF 文档处理工具箱（提取文本/表格、合并拆分、表单填写）。
*   **doc-coauthoring**: 引导用户进行结构化文档共创的工作流（如技术白皮书、提案）。
*   **internal-comms**: 撰写符合企业标准的内部通讯稿（周报、FAQ、公告）。

---
*建议：在遇到复杂任务时，优先匹配上述技能以获取最佳实践。*
