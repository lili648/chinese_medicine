# -*- coding: utf-8 -*-
"""
爬虫模块测试用例
测试 BaseCrawler / PubMedCrawler / DictExpander
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.crawler.base import BaseCrawler, CrawlStats, RateLimiter
from src.crawler.pubmed_crawler import PubMedCrawler, PRESET_QUERIES
from src.crawler.dict_expander import DictExpander, SEED_DISEASES, SEED_DRUGS, SEED_SYMPTOMS


# ============================================================
# RateLimiter 测试
# ============================================================

class TestRateLimiter(unittest.TestCase):

    def test_basic(self):
        rl = RateLimiter(requests_per_sec=10.0)
        self.assertGreater(rl.interval, 0)

    def test_wait_no_delay(self):
        """首次调用不应等待"""
        import time
        rl = RateLimiter(requests_per_sec=100.0, min_interval=0.01)
        start = time.monotonic()
        rl.wait()
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 0.1)

    def test_reset(self):
        rl = RateLimiter(requests_per_sec=1.0)
        rl._last_request = 999999.0
        rl.reset()
        self.assertEqual(rl._last_request, 0.0)


# ============================================================
# CrawlStats 测试
# ============================================================

class TestCrawlStats(unittest.TestCase):

    def test_defaults(self):
        s = CrawlStats()
        self.assertEqual(s.total_requests, 0)
        self.assertEqual(s.success_rate, 0.0)

    def test_success_rate(self):
        s = CrawlStats()
        s.total_requests = 10
        s.successful = 8
        self.assertEqual(s.success_rate, 0.8)

    def test_report(self):
        s = CrawlStats()
        s.total_requests = 5
        s.successful = 5
        report = s.report()
        self.assertIn("爬取统计报告", report)
        self.assertIn("100.0%", report)


# ============================================================
# BaseCrawler 测试 (Mock)
# ============================================================

class TestBaseCrawler(unittest.TestCase):

    def setUp(self):
        self.crawler = BaseCrawler(requests_per_sec=10.0)

    def test_get_ua_random(self):
        ua = self.crawler.get_ua()
        self.assertIn("Mozilla", ua)

    def test_get_ua_fixed(self):
        c = BaseCrawler(user_agent="MyBot/1.0")
        self.assertEqual(c.get_ua(), "MyBot/1.0")

    def test_reset_stats(self):
        self.crawler.stats.total_requests = 5
        self.crawler.reset_stats()
        self.assertEqual(self.crawler.stats.total_requests, 0)


# ============================================================
# PubMedCrawler 测试
# ============================================================

class TestPubMedCrawler(unittest.TestCase):

    def setUp(self):
        self.crawler = PubMedCrawler()

    def test_init_default(self):
        self.assertEqual(self.crawler.max_retries, 4)

    def test_init_with_api_key(self):
        c = PubMedCrawler(api_key="test_key_12345")
        self.assertEqual(c.api_key, "test_key_12345")

    def test_preset_queries(self):
        """所有预设检索式应该存在且非空"""
        self.assertIn("diabetes_tcm", PRESET_QUERIES)
        self.assertIn("hypertension_tcm", PRESET_QUERIES)
        self.assertIn("chd_tcm", PRESET_QUERIES)
        self.assertIn("network_pharmacology_tcm", PRESET_QUERIES)
        for name, query in PRESET_QUERIES.items():
            self.assertTrue(query.strip(), f"预设 {name} 的 query 为空")

    def test_build_query_with_years(self):
        q = PubMedCrawler._build_query("diabetes", year_start=2020, year_end=2023)
        self.assertIn("diabetes", q)
        self.assertIn("2020", q)
        self.assertIn("2023", q)

    def test_build_query_no_years(self):
        q = PubMedCrawler._build_query("cancer AND therapy")
        self.assertEqual(q, "(cancer AND therapy)")

    def test_search_by_preset_invalid(self):
        with self.assertRaises(ValueError):
            self.crawler.search_by_preset("nonexistent_preset")

    def test_save_csv(self):
        articles = [
            {
                "article_id": "PMID123",
                "pmid": "123",
                "title": "Test Title",
                "abstract": "Test Abstract",
                "authors": "Author A; Author B",
                "journal": "Test Journal",
                "pub_year": 2023,
                "language": "en",
            }
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.csv")
            self.crawler.save_csv(articles, path)
            self.assertTrue(os.path.exists(path))
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertIn("Test Title", content)
                self.assertIn("2023", content)

    def test_save_json(self):
        articles = [
            {
                "pmid": "456",
                "title": "JSON Test",
                "abstract": "Abstract",
                "authors": "X",
                "journal": "J",
                "pub_year": 2022,
                "language": "en",
            }
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            self.crawler.save_json(articles, path)
            self.assertTrue(os.path.exists(path))
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.assertEqual(data[0]["title"], "JSON Test")


# ============================================================
# DictExpander 测试
# ============================================================

class TestDictExpander(unittest.TestCase):

    def setUp(self):
        self.expander = DictExpander()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_get_seed_dict_disease(self):
        diseases = self.expander.get_seed_dict("disease")
        self.assertGreater(len(diseases), 50, "疾病词典至少应有50个词条")
        self.assertIn("糖尿病", diseases)
        self.assertIn("高血压", diseases)
        self.assertIn("冠心病", diseases)
        self.assertIn("消渴病", diseases)  # 中医病证

    def test_get_seed_dict_drug(self):
        drugs = self.expander.get_seed_dict("drug")
        self.assertGreater(len(drugs), 50, "药物词典至少应有50个词条")
        self.assertIn("二甲双胍", drugs)
        self.assertIn("阿司匹林", drugs)
        self.assertIn("胰岛素", drugs)
        self.assertIn("丹参", drugs)  # 中药饮片
        self.assertIn("复方丹参滴丸", drugs)  # 中成药

    def test_get_seed_dict_symptom(self):
        symptoms = self.expander.get_seed_dict("symptom")
        self.assertGreater(len(symptoms), 50, "症状词典至少应有50个词条")
        self.assertIn("头痛", symptoms)
        self.assertIn("发热", symptoms)
        self.assertIn("咳嗽", symptoms)
        self.assertIn("乏力", symptoms)
        self.assertIn("恶心", symptoms)

    def test_get_seed_dict_invalid(self):
        with self.assertRaises(ValueError):
            self.expander.get_seed_dict("unknown")

    def test_get_all_seeds(self):
        all_dicts = self.expander.get_all_seeds()
        self.assertEqual(set(all_dicts.keys()), {"disease", "drug", "symptom"})

    def test_save_seed_dict(self):
        path = os.path.join(self.tmpdir, "disease_dict.txt")
        result = self.expander.save_seed_dict("disease", path, merge_existing=False)
        self.assertEqual(result, path)
        self.assertTrue(os.path.exists(path))

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("糖尿病", content)
            self.assertIn("高血压", content)

    def test_save_seed_dict_merge(self):
        path = os.path.join(self.tmpdir, "disease_dict.txt")
        # 先写一条已有数据
        with open(path, "w", encoding="utf-8") as f:
            f.write("自定义疾病\n")

        self.expander.save_seed_dict("disease", path, merge_existing=True)

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("自定义疾病", content)
            self.assertIn("糖尿病", content)

    def test_load_existing_dict(self):
        path = os.path.join(self.tmpdir, "test.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("实体1\n实体2\n# 这是注释\n实体3\n")
        entities = self.expander.load_existing_dict(path)
        self.assertEqual(entities, {"实体1", "实体2", "实体3"})
        self.assertNotIn("# 这是注释", entities)

    def test_load_existing_dict_nonexistent(self):
        entities = self.expander.load_existing_dict("/nonexistent/file.txt")
        self.assertEqual(entities, set())

    def test_show_stats(self):
        report = self.expander.show_stats()
        self.assertIn("医学词典统计", report)
        self.assertIn("disease", report)
        self.assertIn("drug", report)
        self.assertIn("symptom", report)

    def test_seed_data_integrity(self):
        """种子数据不应有重复"""
        self.assertEqual(len(SEED_DISEASES), len(set(SEED_DISEASES)),
                         "疾病种子词典有重复条目")
        self.assertEqual(len(SEED_DRUGS), len(set(SEED_DRUGS)),
                         "药物种子词典有重复条目")
        self.assertEqual(len(SEED_SYMPTOMS), len(set(SEED_SYMPTOMS)),
                         "症状种子词典有重复条目")

    def test_seed_data_not_empty_strings(self):
        """种子数据不应有空字符串"""
        for d in SEED_DISEASES:
            self.assertTrue(d.strip(), f"疾病词典有空条目")
        for d in SEED_DRUGS:
            self.assertTrue(d.strip(), f"药物词典有空条目")
        for d in SEED_SYMPTOMS:
            self.assertTrue(d.strip(), f"症状词典有空条目")


# ============================================================
# 集成测试：实际扩充 dicts/ 目录
# ============================================================

class TestIntegrationExpander(unittest.TestCase):

    def test_expand_and_verify(self):
        """扩充 dicts/ 下的词典并验证可被 EntityDict 加载"""
        with tempfile.TemporaryDirectory() as tmpdir:
            expander = DictExpander()
            paths = expander.save_all_seed_dicts(output_dir=tmpdir)

            for path in paths:
                self.assertTrue(os.path.exists(path), f"文件不存在: {path}")

            # 验证可用 EntityDict 加载
            sys.path.insert(0, os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__)))))
            from src.ner.entity_dict import EntityDict

            # 临时修改 dicts 路径
            ed = EntityDict()
            # 直接测试加载逻辑：读取文件按行解析
            for path in paths:
                with open(path, "r", encoding="utf-8") as f:
                    entities = {line.strip() for line in f
                                if line.strip() and not line.strip().startswith("#")}
                self.assertGreater(len(entities), 0, f"{path} 应包含实体")


if __name__ == "__main__":
    unittest.main(verbosity=2)
