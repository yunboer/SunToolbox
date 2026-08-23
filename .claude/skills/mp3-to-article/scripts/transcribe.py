#!/usr/bin/env python3
"""音频转文本工具（多后端可插拔）。

后端：
  glm   GLM-ASR-2512 API（智谱开放平台，默认）。需在仓库根 .env 配置 GLM_API_KEY。
        API 单次限制 ≤30 秒/25MB，脚本自动 ffmpeg 切片并链式传递上文（prompt），
        调用方无感知。
  mlx   本地 mlx-whisper（Apple Silicon，免费无 key）——预留接口，尚未实现。

用法：
  python3 transcribe.py <音频文件> [-o 输出.txt] [--backend glm] [--keep-temp]

单个音频内部切片串行转写（保证上下文连贯）；多个音频之间由调用方并行调度。
仅依赖 Python 标准库 + ffmpeg/ffprobe。
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

# .claude/skills/mp3-to-article/scripts/ → 上溯 4 级到仓库根
REPO_ROOT = Path(__file__).resolve().parents[4]

GLM_API_URL = "https://open.bigmodel.cn/api/paas/v4/audio/transcriptions"
GLM_MODEL = "glm-asr-2512"
SEGMENT_SECONDS = 25      # API 上限 30s，留安全余量
PROMPT_TAIL_CHARS = 3000  # 每段传给 API 的上文长度（文档建议全文 <8000 字）
MAX_RETRIES = 3


def load_env() -> None:
    """从仓库根 .env 读取键值到环境变量（不覆盖已有值）。"""
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def probe_duration(path: Path) -> float:
    """ffprobe 读取音频总时长（秒）。"""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def slice_audio(path: Path, tmpdir: Path) -> list[Path]:
    """把音频切成 ≤SEGMENT_SECONDS 的 mp3 片段，返回片段列表。"""
    cmd = ["ffmpeg", "-v", "error", "-i", str(path),
           "-f", "segment", "-segment_time", str(SEGMENT_SECONDS)]
    if path.suffix.lower() == ".mp3":
        cmd += ["-c", "copy"]                        # mp3 → mp3 流复制，快且无损
    else:
        cmd += ["-c:a", "libmp3lame", "-q:a", "5"]   # 其他格式重编码为 mp3
    cmd.append(str(tmpdir / "seg_%04d.mp3"))
    subprocess.run(cmd, check=True)
    return sorted(tmpdir.glob("seg_*.mp3"))


def transcribe_segment_glm(seg: Path, api_key: str, prompt: str) -> str:
    """调用 GLM-ASR 转写单个片段（multipart 上传），返回文本。"""
    boundary = uuid.uuid4().hex
    parts: list[bytes] = []

    def field(name: str, value: str) -> None:
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode("utf-8"))

    field("model", GLM_MODEL)
    if prompt:
        field("prompt", prompt)
    parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{seg.name}"\r\n'
        f"Content-Type: audio/mpeg\r\n\r\n".encode("utf-8"))
    parts.append(seg.read_bytes())
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        GLM_API_URL, data=b"".join(parts), method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        })
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("text", "")


FATAL_HTTP_CODES = {400, 401, 403, 404}  # 认证/参数类错误，重试无意义


def transcribe_segment_with_retry(seg: Path, api_key: str, prompt: str) -> str:
    """带指数退避重试的片段转写；4xx 客户端错误（认证/参数）立即失败。"""
    delay = 2.0
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return transcribe_segment_glm(seg, api_key, prompt)
        except urllib.error.HTTPError as e:
            if e.code in FATAL_HTTP_CODES:
                raise RuntimeError(
                    f"请求被拒（HTTP {e.code}），请检查 GLM_API_KEY 是否正确") from e
            last_err = e
        except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
            last_err = e
        if attempt < MAX_RETRIES:
            print(f"  片段 {seg.name} 第 {attempt} 次失败（{last_err}），{delay:.0f}s 后重试",
                  file=sys.stderr)
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"片段 {seg.name} 转写失败（已重试 {MAX_RETRIES} 次）: {last_err}")


def transcribe_glm(path: Path, keep_temp: bool = False) -> str:
    api_key = os.environ.get("GLM_API_KEY", "").strip()
    if not api_key:
        sys.exit("错误：未配置 GLM_API_KEY。请在仓库根 .env 中填写（参考 .env.example）。")

    duration = probe_duration(path)
    n_estimate = max(1, int(duration // SEGMENT_SECONDS) + 1)
    print(f"  时长 {duration:.0f}s，预计 {n_estimate} 段", file=sys.stderr)

    tmpdir = Path(tempfile.mkdtemp(prefix="stb_segs_"))
    try:
        segments = slice_audio(path, tmpdir)
        texts: list[str] = []
        for i, seg in enumerate(segments, 1):
            prompt = "".join(texts)[-PROMPT_TAIL_CHARS:]
            text = transcribe_segment_with_retry(seg, api_key, prompt)
            texts.append(text)
            print(f"  [{i}/{len(segments)}] {seg.name} ✓（{len(text)} 字）", file=sys.stderr)
        return "".join(texts)
    finally:
        if keep_temp:
            print(f"  切片保留于：{tmpdir}", file=sys.stderr)
        else:
            shutil.rmtree(tmpdir, ignore_errors=True)


def transcribe_mlx(path: Path, keep_temp: bool = False) -> str:
    sys.exit("mlx 后端尚未实现（计划：pip install mlx-whisper 后本地转写，免费无需 key）。"
             "当前请使用 --backend glm。")


BACKENDS = {
    "glm": transcribe_glm,
    "mlx": transcribe_mlx,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="音频转文本（多后端）")
    parser.add_argument("audio", type=Path, help="音频文件（mp3/wav）")
    parser.add_argument("-o", "--output", type=Path,
                        help="输出文本路径（默认：音频同目录 <名>.transcript.txt）")
    parser.add_argument("--backend", choices=sorted(BACKENDS), default="glm",
                        help="转写后端（默认 glm）")
    parser.add_argument("--keep-temp", action="store_true",
                        help="保留切片临时目录（调试用）")
    args = parser.parse_args()

    if not args.audio.exists():
        sys.exit(f"错误：文件不存在 {args.audio}")

    load_env()
    print(f"[{args.backend}] 转写 {args.audio.name} ...", file=sys.stderr)
    try:
        text = BACKENDS[args.backend](args.audio, keep_temp=args.keep_temp)
    except RuntimeError as e:
        sys.exit(f"错误：{e}")

    output = args.output or args.audio.with_suffix(".transcript.txt")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    print(f"完成：{output}（{len(text)} 字）", file=sys.stderr)


if __name__ == "__main__":
    main()
