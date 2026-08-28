#!/usr/bin/env python3
"""batch.py 单元测试（纯逻辑 + 子进程失败分支，不联网，仅标准库）。

运行：
  python3 .claude/skills/mp3-to-article/scripts/test_batch.py
  python3 .claude/skills/mp3-to-article/scripts/test_batch.py -v
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import batch


class CleanNameTest(unittest.TestCase):
    """输出文件名清洗规则。"""

    def test_paired_bracket_suffix_removed(self):
        # 站点后缀「[售后：VX：xxx]」整段去掉
        self.assertEqual(batch.clean_name("001 播客标题[售后：VX：123]"), "001-播客标题")

    def test_stray_bracket_removed(self):
        # 源文件名落单的半角 ]（曾产出「085-…不稳定]」这类脏名）
        self.assertEqual(
            batch.clean_name("085-【不确定性】稳定就是最大的不稳定]"),
            "085-【不确定性】稳定就是最大的不稳定")

    def test_number_plus_space_gets_hyphen(self):
        self.assertEqual(batch.clean_name("016 财富自由从未如此容易过"),
                         "016-财富自由从未如此容易过")

    def test_number_without_space_gets_hyphen(self):
        self.assertEqual(batch.clean_name("016财富自由"), "016-财富自由")

    def test_existing_hyphen_not_doubled(self):
        self.assertEqual(batch.clean_name("016-财富自由"), "016-财富自由")
        self.assertEqual(batch.clean_name("016 - 财富自由"), "016-财富自由")

    def test_pure_number_no_dangling_hyphen(self):
        # 曾产出「079-.txt」：编号后为空时不应补连字符
        self.assertEqual(batch.clean_name("079"), "079")
        self.assertEqual(batch.clean_name("079 "), "079")
        self.assertEqual(batch.clean_name("079-"), "079")

    def test_all_bracket_name_falls_back(self):
        # 整名都是括号内容时回退原名，避免产出空文件名
        self.assertEqual(batch.clean_name("[广告]"), "[广告]")

    def test_plain_name_unchanged(self):
        self.assertEqual(batch.clean_name("test-audio"), "test-audio")


class CollectInputsTest(unittest.TestCase):
    def test_dir_filters_and_sorts_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for name in ("b.mp3", "a.MP3", "c.txt", "d.m4a"):
                (tmp / name).touch()
            files = batch.collect_inputs([tmp])
            self.assertEqual([f.name for f in files], ["a.MP3", "b.mp3", "d.m4a"])

    def test_missing_path_skipped(self):
        self.assertEqual(batch.collect_inputs([Path("/nonexistent-xyz")]), [])

    def test_direct_file_accepted_regardless_of_ext(self):
        # 显式给出的单文件不过滤扩展名
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            f = tmp / "weird.ogg"
            f.touch()
            self.assertEqual(batch.collect_inputs([f]), [f])


class TranscribeOneTest(unittest.TestCase):
    def test_existing_output_skipped(self):
        # 幂等：输出已存在且非空时直接跳过，不调起转写
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            audio = tmp / "a.mp3"
            audio.touch()
            (tmp / "a.txt").write_text("旧转写稿", encoding="utf-8")
            _, ok, detail = batch.transcribe_one(audio, tmp)
            self.assertTrue(ok)
            self.assertIn("跳过", detail)

    def test_bad_audio_reports_failure_without_raising(self):
        # 坏文件走失败分支（进程隔离：不抛异常，返回 False + 原因，整批不受影响）
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            audio = tmp / "bad.mp3"
            audio.write_bytes(b"this is not audio data")
            _, ok, detail = batch.transcribe_one(audio, tmp)
            self.assertFalse(ok)
            self.assertTrue(detail)


if __name__ == "__main__":
    unittest.main(verbosity=2)
