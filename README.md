# SunToolbox

一个 Claude Code 技能（Skills）工具箱：`git clone` 下来即可使用，无需安装任何依赖。

## 快速开始

```bash
git clone https://github.com/yunboer/SunToolbox.git
cd SunToolbox
claude
```

首次在此目录启动 Claude Code 时，按提示信任该项目配置即可（项目技能位于 `.claude/skills/`）。

使用方式：

- 输入 `/技能名` 手动调用，例如 `/mp3-to-article`
- 或直接用自然语言描述需求，Claude 会自动匹配合适的技能

## 依赖说明

基础使用零依赖；个别技能有前置要求：

- `mp3-to-article`：需系统安装 [ffmpeg](https://ffmpeg.org/)（含 ffprobe），并在仓库根 `.env` 配置 `GLM_API_KEY`（参考 `.env.example`，key 在[智谱开放平台](https://open.bigmodel.cn/)获取）

## 技能列表

| 技能 | 说明 |
| --- | --- |
| [`mp3-to-article`](./.claude/skills/mp3-to-article/SKILL.md) | MP3 转文章：GLM-ASR 并行转写 + subagent 润色成文（需 `.env` 配置 `GLM_API_KEY`） |
| [`podcast-to-twitter`](./.claude/skills/podcast-to-twitter/SKILL.md) | 播客文档转推特稿：中英双语、单推+thread、双口吻，支持单篇提炼与跨篇主题聚合 |
| [`claude-autoperm`](./.claude/skills/claude-autoperm/SKILL.md) | 一键配置 Claude Code 权限白名单：自动检测系统、备份配置、注入安全命令白名单，可选 shell 启动别名 |

## 如何添加新技能

1. 在 `.claude/skills/` 下新建目录，目录名即技能名（kebab-case，如 `my-tool`）
2. 目录中创建 `SKILL.md`，包含 frontmatter（`name`、`description`）和指令正文
3. 如有辅助脚本、参考文档，一并放在该目录中，在 `SKILL.md` 里引用
4. 更新上方技能列表，提交推送

技能格式可参考 [`mp3-to-article`](./.claude/skills/mp3-to-article/SKILL.md)（含脚本引用）或 [`claude-autoperm`](./.claude/skills/claude-autoperm/SKILL.md)（最简结构）。

## License

[MIT](./LICENSE)
