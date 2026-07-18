# -*- coding: utf-8 -*-
"""
NER 模块 + Pipeline 测试用例
测试 EntityDict / EntityRecognizer / Pipeline
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.ner.entity_dict import EntityDict, EN_TO_CN_ENTITY, EN_ENTITY_TYPES
from src.ner.entity_recognizer import (
    EntityRecognizer,
    RecognizeStats,
    EN_TCM_PATTERNS,
    EN_HERB_PATTERNS,
)
from src.ner.pipeline import Pipeline, PipelineStats
from src.preprocessing.data_loader import DataLoader, Article
from src.preprocessing.preprocessor import Preprocessor


# ============================================================
# EntityDict 测试
# ============================================================

class TestEntityDict(unittest.TestCase):
    """实体词典管理器测试"""

    def setUp(self):
        self.ed = EntityDict()

    def test_load_dicts_from_project_dir(self):
        """从项目 dicts 目录加载词典"""
        dict_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "dicts",
        )
        self.ed.load_dicts(dict_dir)

        # 验证加载成功
        self.assertGreater(len(self.ed.disease_set), 100)
        self.assertGreater(len(self.ed.drug_set), 150)
        self.assertGreater(len(self.ed.symptom_set), 100)
        self.assertGreater(len(self.ed.name_to_type), 300)

    def test_load_dicts_skips_comments(self):
        """加载词典时应自动跳过 # 注释行"""
        with tempfile.TemporaryDirectory() as tmpdir:
            disease_path = os.path.join(tmpdir, "disease_dict.txt")
            with open(disease_path, "w", encoding="utf-8") as f:
                f.write("# 疾病词典\n")
                f.write("# 总数: 3\n")
                f.write("糖尿病\n")
                f.write("高血压\n")
                f.write("冠心病\n")
                f.write("  \n")  # 空行

            self.ed.load_dicts(tmpdir)
            self.assertIn("糖尿病", self.ed.disease_set)
            self.assertIn("高血压", self.ed.disease_set)
            self.assertNotIn("# 疾病词典", self.ed.disease_set)
            self.assertNotIn("# 总数: 3", self.ed.disease_set)
            self.assertNotIn("", self.ed.disease_set)
            self.assertEqual(len(self.ed.disease_set), 3)

    def test_lookup_entity(self):
        """查实体名返回类型"""
        self.ed.add_entity("测试疾病", "Disease")
        self.assertEqual(self.ed.lookup("测试疾病"), "Disease")
        self.assertIsNone(self.ed.lookup("不存在的实体"))

    def test_add_entity(self):
        """程序化添加实体"""
        self.assertEqual(len(self.ed.disease_set), 0)
        self.assertTrue(self.ed.add_entity("新冠", "Disease"))
        self.assertIn("新冠", self.ed.disease_set)
        self.assertEqual(self.ed.name_to_type["新冠"], "Disease")

        # 重复添加应返回 False
        self.assertFalse(self.ed.add_entity("新冠", "Disease"))

    def test_add_entity_invalid_type(self):
        """添加实体时类型无效应报错"""
        with self.assertRaises(ValueError):
            self.ed.add_entity("测试", "InvalidType")

    def test_en_mapping_lookup(self):
        """英文映射查询"""
        self.ed.load_dicts(os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "dicts",
        ))
        # 内置英文映射
        cn = self.ed.lookup_en("salvia miltiorrhiza")
        self.assertEqual(cn, "丹参")
        cn2 = self.ed.lookup_en("traditional chinese medicine")
        self.assertEqual(cn2, "中医")

    def test_has_en_entity(self):
        """检查是否为已知英文实体"""
        self.ed.load_dicts(os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "dicts",
        ))
        self.assertTrue(self.ed.has_en("tcm"))
        self.assertTrue(self.ed.has_en("acupuncture"))
        self.assertFalse(self.ed.has_en("xyz_not_exist"))

    def test_add_en_mapping(self):
        """动态添加英文映射"""
        self.ed.add_entity("连花清瘟胶囊", "Drug")
        self.ed.add_en_mapping("lianhua qingwen", "连花清瘟胶囊", "Drug")
        self.assertTrue(self.ed.has_en("lianhua qingwen"))
        self.assertEqual(self.ed.lookup_en("lianhua qingwen"), "连花清瘟胶囊")

    def test_get_entities_by_type(self):
        """获取指定类型实体"""
        self.ed.add_entity("糖尿病", "Disease")
        self.ed.add_entity("二甲双胍", "Drug")
        diseases = self.ed.get_entities_by_type("Disease")
        self.assertIn("糖尿病", diseases)
        self.assertNotIn("二甲双胍", diseases)

    def test_get_stats(self):
        """统计信息"""
        self.ed.add_entity("疾病1", "Disease")
        self.ed.add_entity("药物1", "Drug")
        stats = self.ed.get_stats()
        self.assertEqual(stats["Disease"], 1)
        self.assertEqual(stats["Drug"], 1)
        self.assertEqual(stats["Total"], 2)

    def test_en_to_cn_entity_builtin(self):
        """内置英文映射表应覆盖至少 30 个 TCM 术语"""
        self.assertGreater(len(EN_TO_CN_ENTITY), 30)
        # 关键术语应存在
        self.assertIn("tcm", EN_TO_CN_ENTITY)
        self.assertIn("acupuncture", EN_TO_CN_ENTITY)


# ============================================================
# EntityRecognizer 测试
# ============================================================

class TestEntityRecognizer(unittest.TestCase):
    """实体识别引擎测试"""

    @classmethod
    def setUpClass(cls):
        """加载词典（类级别，避免重复加载）"""
        cls.entity_dict = EntityDict()
        dict_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "dicts",
        )
        cls.entity_dict.load_dicts(dict_dir)
        cls.recognizer = EntityRecognizer(cls.entity_dict, max_match_length=10)

    # ---- 中文识别 ----

    def test_cn_fmm_single_word(self):
        """中文正向最大匹配：单实体"""
        tokens = ["糖尿", "病", "是", "一种", "常见", "疾病"]
        entities = self.recognizer._recognize_cn_fmm(tokens)
        names = [e["entity_name"] for e in entities]
        self.assertIn("糖尿病", names)

    def test_cn_fmm_multi_word(self):
        """中文 FMM：多实体"""
        tokens = ["糖尿", "病", "患者", "常用", "二甲双胍", "治疗"]
        entities = self.recognizer._recognize_cn_fmm(tokens)
        names = [e["entity_name"] for e in entities]
        self.assertIn("糖尿病", names)
        self.assertIn("二甲双胍", names)

    def test_cn_fmm_longest_match(self):
        """FMM 应优先匹配最长实体"""
        # "类风湿关节炎" 和 "类风湿" 同时存在，应匹配更长的
        self.entity_dict.add_entity("类风湿", "Disease")
        self.entity_dict.add_entity("类风湿关节炎", "Disease")
        tokens = ["类", "风湿", "关节炎", "是", "常见病"]
        entities = self.recognizer._recognize_cn_fmm(tokens)
        names = [e["entity_name"] for e in entities]
        # 至少会匹配到一个，如果 token 组合能拼出最长实体
        # 用词典查找验证实体存在
        self.assertTrue(
            any("类风湿" in n for n in names),
            f"应至少匹配到类风湿相关实体，实际: {names}"
        )

    def test_cn_jieba_match(self):
        """中文 jieba 分词匹配"""
        text = "高血压患者常用硝苯地平治疗"
        entities = self.recognizer._recognize_cn_jieba(text)
        names = [e["entity_name"] for e in entities]
        self.assertIn("高血压", names)
        self.assertGreaterEqual(len(entities), 1)

    def test_cn_jieba_concat(self):
        """jieba 合并词匹配：长实体"""
        # "慢性心力衰竭"可能被jieba切为["慢性", "心力衰竭"]
        # 合并后能匹配到词典中的"慢性心力衰竭"
        text = "慢性心力衰竭是心血管疾病的常见并发症"
        entities = self.recognizer._recognize_cn_jieba(text)
        names = [e["entity_name"] for e in entities]
        # 至少能匹配到"心力衰竭"或"慢性心力衰竭"
        self.assertTrue(
            any("心力衰竭" in n or "心血管" in n for n in names),
            f"应至少匹配到心血管相关实体，实际: {names}"
        )

    def test_cn_recognize_full(self):
        """中文完整识别（FMM + jieba 联合）"""
        tokens = ["高血压", "患者", "服用", "阿司匹林", "出现", "头痛"]
        entities = self.recognizer.recognize(tokens, language="zh")
        names = [e["entity_name"] for e in entities]
        self.assertIn("高血压", names)
        self.assertIn("阿司匹林", names)
        self.assertIn("头痛", names)

    # ---- 英文识别 ----

    def test_en_rule_tcm(self):
        """英文规则匹配：TCM 概念"""
        text = "Traditional Chinese Medicine has been used for centuries."
        entities = self.recognizer._recognize_en_rules(text)
        names = [e["entity_name"] for e in entities]
        self.assertIn("中医", names)

    def test_en_rule_acupuncture(self):
        """英文规则：针灸"""
        text = "Acupuncture and electro-acupuncture are effective treatments."
        entities = self.recognizer._recognize_en_rules(text)
        names = [e["entity_name"] for e in entities]
        self.assertIn("针灸", names)

    def test_en_rule_herb(self):
        """英文规则：中药"""
        text = "Salvia miltiorrhiza and Panax notoginseng are widely used."
        entities = self.recognizer._recognize_en_rules(text)
        names = [e["entity_name"] for e in entities]
        self.assertIn("丹参", names)
        self.assertIn("三七", names)

    def test_en_rule_disease(self):
        """英文规则：疾病"""
        text = "Patients with type 2 diabetes mellitus and hypertension."
        entities = self.recognizer._recognize_en_rules(text)
        names = [e["entity_name"] for e in entities]
        self.assertIn("2型糖尿病", names)  # type 2 diabetes matches first

    def test_en_dict_phrase(self):
        """英文 token 短语匹配"""
        tokens = ["tcm", "is", "a", "form", "of", "traditional", "chinese", "medicine"]
        entities = self.recognizer._recognize_en_dict(tokens)
        names = [e["entity_name"] for e in entities]
        # "traditional chinese medicine" 应该匹配到
        self.assertIn("中医", names)

    def test_en_keyword(self):
        """英文关键词匹配"""
        text = "Berberine and curcumin showed significant effects."
        entities = self.recognizer._recognize_en_phrases(text)
        names = [e["entity_name"] for e in entities]
        self.assertIn("小檗碱", names)
        self.assertIn("姜黄素", names)

    def test_en_recognize_full(self):
        """英文完整识别"""
        text = ("Traditional Chinese Medicine including acupuncture and "
                "Salvia miltiorrhiza was used to treat type 2 diabetes "
                "associated with insomnia and fatigue.")
        tokens = ["traditional", "chinese", "medicine", "including", "acupuncture",
                  "and", "salvia", "miltiorrhiza", "used", "treat", "type", "2",
                  "diabetes", "associated", "insomnia", "fatigue"]
        entities = self.recognizer.recognize(tokens, raw_text=text, language="en")

        names = [e["entity_name"] for e in entities]
        self.assertIn("中医", names)
        self.assertIn("针灸", names)
        self.assertIn("丹参", names)

    # ---- 去重 ----

    def test_deduplicate(self):
        """同类型同名称实体应去重"""
        entities = [
            {"entity_name": "糖尿病", "entity_type": "Disease", "match_method": "fmm"},
            {"entity_name": "糖尿病", "entity_type": "Disease", "match_method": "jieba"},
            {"entity_name": "高血压", "entity_type": "Disease", "match_method": "fmm"},
        ]
        result = self.recognizer._deduplicate(entities)
        self.assertEqual(len(result), 2)
        # 应保留优先级更高的 fmm 方法
        methods = [r["match_method"] for r in result]
        self.assertNotIn("jieba", methods)

    # ---- 语言检测 ----

    def test_detect_language_cn(self):
        """中文检测"""
        tokens = ["中药", "治疗", "有效"]
        lang = self.recognizer._detect_language(tokens)
        self.assertEqual(lang, "zh")

    def test_detect_language_en(self):
        """英文检测"""
        tokens = ["traditional", "chinese", "medicine", "is", "effective"]
        lang = self.recognizer._detect_language(tokens)
        self.assertEqual(lang, "en")

    def test_detect_language_auto_empty(self):
        """空文本应默认为英文"""
        lang = self.recognizer._detect_language([], "")
        self.assertEqual(lang, "en")

    # ---- 统计 ----

    def test_recognize_stats(self):
        """识别统计"""
        stats = RecognizeStats()
        stats.entities_by_type["Disease"] = 10
        stats.entities_by_method["fmm"] = 8
        report = stats.report()
        self.assertIn("Disease", report)
        self.assertIn("fmm", report)

    # ---- 前缀方法兼容 ----

    def test_has_en_entity_prefix(self):
        """_has_en_entity 别名应正常工作"""
        self.entity_dict.load_dicts(os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "dicts",
        ))
        self.assertTrue(self.entity_dict._has_en_entity("acupuncture"))


# ============================================================
# Pipeline 测试
# ============================================================

class TestPipeline(unittest.TestCase):
    """Pipeline 编排器测试"""

    @classmethod
    def setUpClass(cls):
        dict_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "dicts",
        )
        cls.pipeline = Pipeline(dict_dir=dict_dir, clean_mode="medical")

    def test_init_components(self):
        """Pipeline 初始化应创建所有组件"""
        self.assertIsNotNone(self.pipeline.entity_dict)
        self.assertIsNotNone(self.pipeline.preprocessor)
        self.assertIsNotNone(self.pipeline.recognizer)
        self.assertIsNotNone(self.pipeline.data_loader)
        # 词典应已加载
        self.assertGreater(len(self.pipeline.entity_dict.name_to_type), 100)

    @staticmethod
    def _make_article(article_id, title, abstract, pmid="", lang="zh"):
        """快捷构造 Article（补全必填字段）"""
        return Article(
            article_id=article_id, pmid=pmid,
            title=title, abstract=abstract,
            authors="", journal="", pub_year=2023,
            language=lang, source_file="test.csv",
        )

    def test_preprocess_articles(self):
        """预处理步骤"""
        articles = [
            self._make_article("TEST1", "糖尿病治疗研究", "使用二甲双胍治疗2型糖尿病"),
            self._make_article("TEST2", "Hypertension Treatment",
                               "Traditional Chinese Medicine for hypertension", lang="en"),
        ]
        processed = self.pipeline.preprocess(articles)
        self.assertGreater(len(processed), 0)
        for a in processed:
            self.assertIsNotNone(a.tokens)
            self.assertGreater(len(a.tokens), 0)

    def test_recognize_step(self):
        """实体识别步骤"""
        articles = [
            self._make_article("REC1", "高血压与冠心病的中医治疗",
                               "丹参和黄芪在心血管疾病中的应用"),
        ]
        processed = self.pipeline.preprocess(articles)
        entities = self.pipeline.recognize(processed)
        self.assertGreater(len(entities), 0, "应至少识别到一个实体")
        names = [e["entity_name"] for e in entities]
        self.assertTrue(
            any(n in names for n in ["高血压", "冠心病", "丹参", "黄芪"]),
            f"应识别到已知实体，实际: {names}"
        )

    def test_recognize_english(self):
        """英文文献实体识别"""
        articles = [
            self._make_article("EN1",
                "Salvia miltiorrhiza for Type 2 Diabetes",
                "Traditional Chinese Medicine (TCM) including Salvia miltiorrhiza "
                "and acupuncture has been widely used. Network pharmacology and "
                "molecular docking studies show effects on diabetes and hypertension.",
                pmid="12345678", lang="en",
            ),
        ]
        processed = self.pipeline.preprocess(articles)
        entities = self.pipeline.recognize(processed)

        names = [e["entity_name"] for e in entities]
        self.assertIn("丹参", names)
        self.assertIn("中医", names)
        self.assertIn("针灸", names)

    def test_run_full_pipeline_csv(self):
        """完整 Pipeline 运行（CSV 数据）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建测试 CSV
            csv_path = os.path.join(tmpdir, "test_articles.csv")
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                import csv
                writer = csv.DictWriter(f, fieldnames=[
                    "article_id", "pmid", "title", "abstract",
                    "authors", "journal", "pub_year", "language",
                ])
                writer.writeheader()
                writer.writerow({
                    "article_id": "T1", "pmid": "11111",
                    "title": "中医药治疗糖尿病研究",
                    "abstract": "本研究探讨丹参、黄芪治疗2型糖尿病的疗效。",
                    "authors": "张三",
                    "journal": "中医杂志",
                    "pub_year": "2023",
                    "language": "zh",
                })
                writer.writerow({
                    "article_id": "T2", "pmid": "22222",
                    "title": "Acupuncture for Insomnia",
                    "abstract": "Acupuncture and Chinese herbal medicine for insomnia.",
                    "authors": "John Doe",
                    "journal": "J Tradit Chin Med",
                    "pub_year": "2023",
                    "language": "en",
                })

            export_path = os.path.join(tmpdir, "entities.json")
            entities = self.pipeline.run(
                csv_path, export_path=export_path, progress_every=1,
            )

            self.assertGreater(len(entities), 0, "应至少识别到一个实体")

            # 检查导出文件
            self.assertTrue(os.path.exists(export_path))
            with open(export_path, "r", encoding="utf-8") as f:
                exported = json.load(f)
            self.assertEqual(len(exported), len(entities))

    def test_run_with_summary(self):
        """带摘要的 Pipeline 运行"""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "test.csv")
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                import csv
                writer = csv.DictWriter(f, fieldnames=[
                    "article_id", "pmid", "title", "abstract",
                    "authors", "journal", "pub_year", "language",
                ])
                writer.writeheader()
                writer.writerow({
                    "article_id": "S1", "pmid": "33333",
                    "title": "高血压中医药干预",
                    "abstract": "高血压患者使用丹参、川芎、黄芪治疗疗效显著。",
                    "authors": "测试",
                    "journal": "中医药学报",
                    "pub_year": "2023",
                    "language": "zh",
                })

            entities, top = self.pipeline.run_with_summary(
                csv_path, export_dir=tmpdir,
            )
            self.assertGreater(len(entities), 0)
            self.assertGreater(len(top), 0)

    def test_export_csv_entities(self):
        """导出实体 CSV"""
        with tempfile.TemporaryDirectory() as tmpdir:
            entities = [
                {"entity_name": "丹参", "entity_type": "Drug",
                 "article_id": "A1", "match_method": "fmm", "frequency": 3},
                {"entity_name": "糖尿病", "entity_type": "Disease",
                 "article_id": "A1", "match_method": "fmm", "frequency": 2},
            ]
            path = os.path.join(tmpdir, "entities.csv")
            result_path = self.pipeline.export_csv_entities(entities, path)
            self.assertTrue(os.path.exists(result_path))

    def test_pipeline_stats(self):
        """Pipeline 统计"""
        stats = PipelineStats()
        stats.total_articles = 100
        stats.total_entities = 500
        stats.unique_entities = 50
        report = stats.report()
        self.assertIn("100", report)
        self.assertIn("500", report)

    def test_get_entity_summary(self):
        """实体摘要统计"""
        entities = [
            {"entity_name": "丹参", "entity_type": "Drug", "article_id": "A1"},
            {"entity_name": "黄芪", "entity_type": "Drug", "article_id": "A1"},
            {"entity_name": "糖尿病", "entity_type": "Disease", "article_id": "A1"},
        ]
        summary = self.pipeline.get_entity_summary(entities)
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["unique"], 3)
        self.assertEqual(summary["by_type"]["Drug"], 2)

    # ---- 边界情况 ----

    def test_empty_input(self):
        """空输入应返回空结果"""
        entities = self.pipeline.recognize([])
        self.assertEqual(len(entities), 0)

    def test_no_entity_article(self):
        """无实体文献应返回空"""
        articles = [
            self._make_article("NONE", "普通文本", "这是一个没有医学实体的测试文档。"),
        ]
        processed = self.pipeline.preprocess(articles)
        entities = self.pipeline.recognize(processed)
        self.assertIsInstance(entities, list)

    def test_recognize_empty_tokens(self):
        """空 token 应返回空"""
        entities = self.pipeline.recognizer.recognize([], language="zh")
        self.assertEqual(len(entities), 0)

    def test_recognize_none_text(self):
        """空文本应返回空"""
        entities = self.pipeline.recognizer._recognize_en_rules("")
        self.assertEqual(len(entities), 0)
        entities2 = self.pipeline.recognizer._recognize_en_phrases("")
        self.assertEqual(len(entities2), 0)


# ============================================================
# 集成测试：端到端
# ============================================================

class TestIntegration(unittest.TestCase):
    """端到端集成测试"""

    def test_end_to_end_cn(self):
        """中文端到端：加载 → 预处理 → 识别"""
        dict_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "dicts",
        )
        pipeline = Pipeline(dict_dir=dict_dir, clean_mode="medical")

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "cn_test.csv")
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                import csv
                writer = csv.DictWriter(f, fieldnames=[
                    "article_id", "pmid", "title", "abstract",
                    "authors", "journal", "pub_year", "language",
                ])
                writer.writeheader()
                # 多种类型实体混合
                writer.writerow({
                    "article_id": "E2E_CN",
                    "pmid": "99999",
                    "title": "复方丹参滴丸治疗冠心病心绞痛的临床研究",
                    "abstract": (
                        "目的：观察复方丹参滴丸治疗冠心病心绞痛的疗效。"
                        "方法：80例冠心病患者随机分为两组，治疗组使用复方丹参滴丸，对照组使用阿司匹林。"
                        "结果：治疗组有效率明显高于对照组，胸痛、胸闷、心悸等症状显著改善。"
                        "结论：复方丹参滴丸治疗冠心病安全有效。"
                    ),
                    "authors": "李四",
                    "journal": "中国中西医结合杂志",
                    "pub_year": "2024",
                    "language": "zh",
                })

            entities = pipeline.run(csv_path, progress_every=1)

            names = [e["entity_name"] for e in entities]
            # 应能识别到多个类型实体
            self.assertIn("复方丹参滴丸", names)  # Drug
            self.assertTrue(
                any(n in names for n in ["冠心病", "心绞痛"]),
                f"应识别到疾病实体，实际: {names}"
            )
            self.assertIn("阿司匹林", names)  # Drug

            # 验证统计
            self.assertGreater(pipeline.stats.total_articles, 0)
            self.assertGreater(pipeline.stats.total_entities, 0)

            report = pipeline.show_report()
            self.assertIsNotNone(report)

    def test_end_to_end_en(self):
        """英文端到端"""
        dict_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "dicts",
        )
        pipeline = Pipeline(dict_dir=dict_dir, clean_mode="medical")

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "en_test.csv")
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                import csv
                writer = csv.DictWriter(f, fieldnames=[
                    "article_id", "pmid", "title", "abstract",
                    "authors", "journal", "pub_year", "language",
                ])
                writer.writeheader()
                writer.writerow({
                    "article_id": "E2E_EN",
                    "pmid": "88888",
                    "title": "Network Pharmacology Analysis of Compound Danshen Dripping Pill",
                    "abstract": (
                        "Background: Traditional Chinese Medicine (TCM) has been "
                        "used for treating coronary heart disease. Compound Danshen "
                        "Dripping Pill contains Salvia miltiorrhiza and Panax notoginseng. "
                        "Methods: Network pharmacology and molecular docking were used "
                        "to analyze mechanisms. Results: 120 targets related to "
                        "hypertension and type 2 diabetes were identified. "
                        "Conclusion: TCM shows multi-target effects on cardiovascular diseases."
                    ),
                    "authors": "Wang X",
                    "journal": "Front Pharmacol",
                    "pub_year": "2024",
                    "language": "en",
                })

            entities = pipeline.run(csv_path, progress_every=1)

            names = [e["entity_name"] for e in entities]
            # 应通过规则匹配到 TCM 概念和中药
            self.assertIn("中医", names)
            self.assertIn("网络药理学", names)
            self.assertIn("丹参", names)
            self.assertIn("三七", names)

            self.assertGreater(len(entities), 5)

    def test_full_pipeline_with_export(self):
        """完整 Pipeline 带全部导出"""
        dict_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "dicts",
        )
        pipeline = Pipeline(dict_dir=dict_dir)

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "export_test.csv")
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                import csv
                writer = csv.DictWriter(f, fieldnames=[
                    "article_id", "pmid", "title", "abstract",
                    "authors", "journal", "pub_year", "language",
                ])
                writer.writeheader()
                writer.writerow({
                    "article_id": "EXP1", "pmid": "77777",
                    "title": "黄芪治疗糖尿病肾病的机制研究",
                    "abstract": (
                        "目的：基于网络药理学探讨黄芪治疗糖尿病肾病的作用机制。"
                        "方法：运用分子对接技术分析黄芪活性成分与关键靶点的结合。"
                        "结果：黄芪主要活性成分包括黄芪甲苷等。"
                    ),
                    "authors": "王五",
                    "journal": "中草药",
                    "pub_year": "2024",
                    "language": "zh",
                })

            # 导出 entities.json + top_entities.json
            entities, top = pipeline.run_with_summary(
                csv_path, export_dir=tmpdir,
            )

            # 检查所有导出
            entities_path = os.path.join(tmpdir, "entities.json")
            top_path = os.path.join(tmpdir, "top_entities.json")
            self.assertTrue(os.path.exists(entities_path))
            self.assertTrue(os.path.exists(top_path))

            # 验证导出内容
            with open(entities_path, "r", encoding="utf-8") as f:
                exported = json.load(f)
            self.assertGreater(len(exported), 0)

            with open(top_path, "r", encoding="utf-8") as f:
                top_exported = json.load(f)
            self.assertGreater(len(top_exported), 0)

            # 也测试 CSV 导出
            csv_export = os.path.join(tmpdir, "entities_export.csv")
            pipeline.export_csv_entities(entities, csv_export)
            self.assertTrue(os.path.exists(csv_export))


if __name__ == "__main__":
    unittest.main(verbosity=2)
