#!/usr/bin/env python3
"""批量音频转写调度器：任意规模输入，自动并行调度，不崩溃、可续跑。

设计（实测结论，详见 SKILL.md「批量处理」）：
  - 文件级并行默认 8（GLM API 加速饱和点，更高并发为负优化）
  - 每个文件内部串行链式转写（workers=1，质量优先：段边界衔接、人名一致）
  - 进程级隔离：每个文件独立子进程，单文件失败不影响整批
  - 断点续跑：输出已存在即跳过，重跑安全（幂等）
  - 结束打印汇总；有失败时退出码 1，重跑本命令即只补失败的

用法：
  python3 batch.py <音频文件或目录...> [-o dump/transcripts] [--workers 8]
"""

import argparse
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SCRIPT = Path(__file__).parent / "transcribe.py"
DEFAULT_WORKERS = 8
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}


def clean_name(stem: str) -> str:
    """清洗输出名：去掉中括号后缀（如「[售后：VX：xxx]」），编号后补连字符。"""
    name = re.sub(r"\[.*?\]", "", stem).strip() or stem
    return re.sub(r"^(\d+)\s*", r"\1-", name)


def collect_inputs(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        if p.is_dir():
            files += sorted(f for f in p.iterdir() if f.suffix.lower() in AUDIO_EXTS)
        elif p.is_file():
            files.append(p)
        else:
            print(f"警告：跳过不存在的路径 {p}", file=sys.stderr)
    return files


def transcribe_one(audio: Path, out_dir: Path) -> tuple[Path, bool, str]:
    """转写单个文件；不抛异常，失败以 (file, False, 原因) 返回。"""
    out = out_dir / f"{clean_name(audio.stem)}.txt"
    if out.exists() and out.stat().st_size > 0:
        return audio, True, "已存在，跳过"
    try:
        r = subprocess.run(
            [sys.executable, str(SCRIPT), str(audio), "-o", str(out)],
            capture_output=True, text=True)
        if r.returncode == 0:
            return audio, True, "完成"
        detail = (r.stderr or r.stdout or "未知错误").strip().splitlines()[-1]
        return audio, False, detail
    except Exception as e:  # 任何意外都不让整批中断
        return audio, False, f"调度异常: {e}"


def main() -> None:
    parser = argparse.ArgumentParser(description="批量音频转写调度器")
    parser.add_argument("inputs", nargs="+", type=Path,
                        help="音频文件或目录（可多个）")
    parser.add_argument("-o", "--out-dir", type=Path, default=Path("dump/transcripts"),
                        help="转写稿输出目录（默认 dump/transcripts）")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                        help=f"文件级并行数（默认 {DEFAULT_WORKERS}，实测饱和点）")
    args = parser.parse_args()

    files = collect_inputs(args.inputs)
    if not files:
        sys.exit("错误：未找到任何音频文件（支持 mp3/wav）")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    print(f"批量转写：{len(files)} 个文件，并行 {min(args.workers, len(files))}",
          file=sys.stderr)

    results: list[tuple[Path, bool, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(transcribe_one, f, args.out_dir) for f in files]
        for i, fut in enumerate(as_completed(futures), 1):
            audio, ok, detail = fut.result()
            print(f"[{i}/{len(files)}] {'✓' if ok else '✗'} {audio.name} — {detail}",
                  file=sys.stderr)
            results.append((audio, ok, detail))

    ok_count = sum(1 for _, ok, _ in results if ok)
    failed = [(a, d) for a, ok, d in results if not ok]
    print(f"\n汇总：{ok_count}/{len(files)} 成功"
          + ("（全部完成）" if not failed else "，失败如下，重跑本命令即续补："),
          file=sys.stderr)
    for a, d in failed:
        print(f"  ✗ {a.name} — {d}", file=sys.stderr)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
