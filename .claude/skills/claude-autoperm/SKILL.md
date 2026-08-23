---
name: claude-autoperm
description: 一键配置 Claude Code 权限白名单（常用指令自动通过）：自动检测操作系统（macOS/Linux/WSL/Windows Git Bash），定位并备份 ~/.claude/settings.json，合并注入安全命令白名单，可选为 shell 添加自动接受编辑模式的启动别名。用户提到"配置自动通过 / 权限白名单 / 减少确认弹窗 / 配置 alias"时使用。
---

# Claude 自动通过配置

## 用法

```bash
bash .claude/skills/claude-autoperm/scripts/setup_autoperm.sh                # 仅配置白名单
bash .claude/skills/claude-autoperm/scripts/setup_autoperm.sh --alias ccauto # 同时添加启动别名
```

## 脚本做什么

1. **检测系统**：macOS / Linux / WSL / Windows Git Bash，输出环境信息
2. **定位配置**：`~/.claude/settings.json`（各平台路径一致；先备份，带时间戳）
3. **合并白名单**：向 `permissions.allow` 注入推荐的安全命令规则 ——
   只读检索（ls/cat/grep/find）、文件整理（mkdir/cp/mv，**不含 rm**）、
   git 闭环（status/log/diff/add/commit/push/pull）、开发工具（python3/node/npm run）、
   音视频（ffmpeg/ffprobe）。已有的自定义规则原样保留，不覆盖
4. **可选别名**（`--alias 名称`）：按检测到的 shell（zsh→.zshrc / bash→.bashrc）
   添加 `alias <名称>='claude --permission-mode acceptEdits'`，用该别名启动即自动接受文件编辑

## 安全边界

- 白名单刻意排除 `rm`、`sudo`、`curl/wget` 外发等高危命令 —— 这些仍会正常弹确认
- 修改配置前自动备份；如需回滚，恢复最近的 `.bak.*` 文件即可
- 配置完成后需重启 Claude Code 生效
