#!/usr/bin/env bash
# Claude Code 自动通过（权限白名单）一键配置工具
# 用法:
#   bash setup_autoperm.sh                # 仅配置白名单
#   bash setup_autoperm.sh --alias NAME   # 额外添加 shell 启动别名（自动接受编辑模式）
set -euo pipefail

# ── 1. 检测系统 ──────────────────────────────────────────────
OS="$(uname -s)"
case "$OS" in
  Darwin)                              OS_NAME="macOS" ;;
  Linux)
    if grep -qi microsoft /proc/version 2>/dev/null; then OS_NAME="Linux (WSL)"; else OS_NAME="Linux"; fi ;;
  MINGW*|MSYS*|CYGWIN*)                OS_NAME="Windows (Git Bash)" ;;
  *)                                   OS_NAME="未知 ($OS)" ;;
esac
echo "[1/4] 系统: $OS_NAME"

# ── 2. 定位并备份 settings.json ─────────────────────────────
SETTINGS_DIR="${HOME}/.claude"
SETTINGS="${SETTINGS_DIR}/settings.json"
mkdir -p "$SETTINGS_DIR"
echo "[2/4] 配置文件: ${SETTINGS}"
if [ -f "$SETTINGS" ]; then
  BAK="${SETTINGS}.bak.$(date +%Y%m%d%H%M%S)"
  cp "$SETTINGS" "$BAK"
  echo "      已备份 -> ${BAK}"
fi

# ── 3. 合并注入白名单规则（保留用户已有配置）──────────────────
python3 - "$SETTINGS" <<'PYEOF'
import json, sys

path = sys.argv[1]
try:
    cfg = json.load(open(path, encoding="utf-8"))
except Exception:
    cfg = {}

# 推荐白名单：只读/低破坏性命令；刻意不含 rm、sudo、curl/wget 外发等高危项。
# 已知取舍（详见 SKILL.md「安全边界」）：cp/mv 可覆盖工作区外文件；git push 自动通过。
RECOMMENDED = [
    # 文件查看与检索
    "Bash(ls:*)", "Bash(cat:*)", "Bash(head:*)", "Bash(tail:*)",
    "Bash(grep:*)", "Bash(find:*)", "Bash(wc:*)", "Bash(which:*)",
    "Bash(uname:*)", "Bash(pwd)",
    # 文件整理（不含删除）
    "Bash(mkdir:*)", "Bash(cp:*)", "Bash(mv:*)", "Bash(touch:*)",
    # git 常用闭环（push 属对外动作，自动通过适合个人机；敏感环境请自行移除）
    "Bash(git status)", "Bash(git log:*)", "Bash(git diff:*)",
    "Bash(git add:*)", "Bash(git commit:*)", "Bash(git push:*)", "Bash(git pull:*)",
    # 本仓库技能脚本：python3 仅放行 .claude/skills/ 下的调用，不放行任意代码执行
    "Bash(python3 .claude/skills/:*)", "Bash(pip3 list)",
    # 音视频处理（SunToolbox 常用）
    "Bash(ffmpeg:*)", "Bash(ffprobe:*)",
]

# 默认不注入的高风险项（等效放行任意代码执行，确认需要时手动加入 allow 列表）：
#   "Bash(python3:*)"   任意 Python 脚本/代码
#   "Bash(node:*)"      任意 Node 脚本
#   "Bash(npm run:*)"   任意 package.json 脚本

perms = cfg.setdefault("permissions", {})
allow = perms.setdefault("allow", [])
added = [r for r in RECOMMENDED if r not in allow]
perms["allow"] = allow + added

json.dump(cfg, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"[3/4] 新增 {len(added)} 条白名单规则（累计 {len(perms['allow'])} 条）")
PYEOF

# ── 4. 可选：添加 shell 启动别名 ─────────────────────────────
ALIAS_NAME=""
if [ "${1:-}" = "--alias" ]; then ALIAS_NAME="${2:-ccauto}"; fi
if [ -n "$ALIAS_NAME" ]; then
  SHELL_NAME="$(basename "${SHELL:-/bin/bash}")"
  case "$SHELL_NAME" in
    zsh)  RC="${HOME}/.zshrc" ;;
    bash) RC="${HOME}/.bashrc" ;;
    *)    RC=""; echo "[4/4] shell ${SHELL_NAME} 暂不支持自动配置别名（可手动添加）" ;;
  esac
  if [ -n "${RC:-}" ]; then
    LINE="alias ${ALIAS_NAME}='claude --permission-mode acceptEdits'"
    if grep -qF "$LINE" "$RC" 2>/dev/null; then
      echo "[4/4] 别名已存在: ${RC}"
    else
      printf '\n# claude auto-accept edits mode (by claude-autoperm)\n%s\n' "$LINE" >> "$RC"
      echo "[4/4] 已添加别名 ${ALIAS_NAME} -> ${RC}（执行 source ${RC} 生效）"
    fi
  fi
else
  echo "[4/4] 未指定 --alias，跳过别名配置"
fi

echo "完成：重启 Claude Code 后白名单生效。"
