# CLAUDE.md

本仓库是 Claude Code 技能（Skills）工具箱：其他电脑 `git clone` 后在目录内启动 Claude Code 即可直接使用所有技能，无需安装依赖。

## 添加新技能

1. 在 `.claude/skills/` 下新建目录，目录名即技能名（kebab-case，如 `my-tool`）
2. 创建 `SKILL.md`：frontmatter 必须含 `name`、`description`，正文为执行指令（可参考 `.claude/skills/hello/SKILL.md`）
3. 辅助脚本、参考文档放在同一技能目录中，在 `SKILL.md` 里引用相对路径
4. 更新 `README.md` 中的技能列表表格
5. 提交并推送

## 私密配置（.env）

技能需要新的 API key 时的流程：

1. 在 `.env.example` 登记变量名和用途注释（此文件随仓库提交，其他电脑可见）
2. 在 `.env` 中写入变量名 + 明显占位符（如 `GLM_API_KEY=<在此粘贴你的智谱APIKey>`），并附 key 获取地址注释
3. 执行 `code .env` 打开编辑器，请用户自行填写真实值；Claude 不读取、不回显真实 key 内容
4. 用户确认填好后，再继续依赖该 key 的后续流程

## 测试文件（dump/）

- 所有 skill 本地开发/测试产生的中间文件（测试音频、转写文本、临时输出等）统一放入仓库根目录的 `dump/`
- `dump/` 的内容已被 .gitignore 忽略（仅保留目录本身），防止测试数据被提交
- 开发测试时不要把临时文件写到 dump/ 以外的位置

## 工作流

- 每次修改代码后必须 commit + push：多电脑共享仓库，改动推送后其他电脑才能拉取，无需逐次询问用户
- commit message 用英文祈使句，简洁描述改动（如 `Add image-resize skill`）
- 提交粒度按一次任务/一轮连贯改动，避免碎片化提交
- 与用户交流使用中文
