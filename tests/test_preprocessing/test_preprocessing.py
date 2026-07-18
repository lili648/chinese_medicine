# -*- coding: utf-8 -*-
"""
预处理模块测试用例
测试 DataLoader 和 Preprocessor 的所有功能
"""
import os
import sys
import tempfile
import unittest

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.preprocessing import Article, DataLoader, LoadStats
from src.preprocessing import Preprocessor, PreprocessStats, StopWords


# ============================================================
# Article 数据类测试
# ============================================================

class TestArticle(unittest.TestCase):
    """测试 Article 数据类"""

    def test_create_article_default(self):
        a = Article(
            article_id="A001",
            pmid="12345",
            title="测试文献",
            abstract="测试摘要",
            authors="张三",
            journal="测试杂志",
            pub_year=2023,
            language="zh",
            source_file="test.csv",
        )
        self.assertEqual(a.article_id, "A001")
        self.assertEqual(a.pmid, "12345")
        self.assertEqual(a.title, "测试文献")
        self.assertEqual(a.language, "zh")
        self.assertEqual(a.tokens, [])  # 默认空列表

    def test_create_article_minimal(self):
        """最小字段创建"""
        a = Article(
            article_id="A002",
            pmid=None,
            title="最小",
            abstract=None,
            authors=None,
            journal=None,
            pub_year=None,
            language="zh",
            source_file="",
        )
        self.assertEqual(a.article_id, "A002")
        self.assertIsNone(a.abstract)

    def test_article_tokens_mutable(self):
        a = Article(
            article_id="A003", pmid="", title="X",
            abstract="", authors="", journal="",
            pub_year=None, language="en", source_file="",
        )
        a.tokens = ["token1", "token2"]
        self.assertEqual(len(a.tokens), 2)


# ============================================================
# DataLoader 测试
# ============================================================

class TestDataLoaderCSV(unittest.TestCase):
    """测试 CSV 文件加载"""

    def setUp(self):
        self.loader = DataLoader()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_csv(self, filename, content):
        path = os.path.join(self.tmpdir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_load_basic_csv(self):
        path = self._write_csv("test.csv", (
            "article_id,title,abstract,language,pub_year\n"
            "1,糖尿病研究,关于糖尿病的中医治疗,zh,2022\n"
            "2,Hypertension Study,A study on hypertension,en,2021\n"
        ))
        articles = self.loader.load_csv(path)
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0].article_id, "1")
        self.assertEqual(articles[0].title, "糖尿病研究")
        self.assertEqual(articles[1].language, "en")

    def test_load_csv_missing_title_skipped(self):
        """缺失 title 的记录应被跳过"""
        path = self._write_csv("test.csv", (
            "article_id,title,abstract,language\n"
            "1,有效标题,摘要,zh\n"
            ",,无标题,zh\n"
            "2,另一个标题,摘要2,zh\n"
        ))
        articles = self.loader.load_csv(path)
        self.assertEqual(len(articles), 2)
        titles = [a.title for a in articles]
        self.assertIn("有效标题", titles)
        self.assertIn("另一个标题", titles)

    def test_load_csv_empty_file(self):
        path = self._write_csv("empty.csv", "article_id,title,abstract\n")
        articles = self.loader.load_csv(path)
        self.assertEqual(len(articles), 0)

    def test_load_csv_file_not_found(self):
        articles = self.loader.load_csv("/nonexistent/file.csv")
        self.assertEqual(len(articles), 0)
        self.assertTrue(len(self.loader.stats.errors) > 0)

    def test_load_csv_auto_infer_language(self):
        """自动推断语种"""
        path = self._write_csv("test.csv", (
            "article_id,title,abstract\n"
            "1,中医辨证论治研究,摘要内容\n"
            "2,Diabetes Research,abstract content\n"
        ))
        articles = self.loader.load_csv(path)
        self.assertEqual(articles[0].language, "zh")
        self.assertEqual(articles[1].language, "en")

    def test_load_csv_pub_year_parsing(self):
        """测试年份解析的各种格式"""
        path = self._write_csv("test.csv", (
            "article_id,title,pub_year\n"
            "1,标题1,2023\n"
            "2,标题2,2023.0\n"
            "3,标题3,\n"
            "4,标题4,invalid\n"
            "5,标题5,2023年\n"
        ))
        articles = self.loader.load_csv(path)
        self.assertEqual(articles[0].pub_year, 2023)
        self.assertEqual(articles[1].pub_year, 2023)
        self.assertIsNone(articles[2].pub_year)
        self.assertIsNone(articles[3].pub_year)
        self.assertEqual(articles[4].pub_year, 2023)

    def test_load_csv_gbk_encoding(self):
        """测试 GBK 编码降级"""
        path = self._write_csv("test.csv", (
            "article_id,title,abstract\n"
            "1,中医中药研究,关于中医的临床研究\n"
        ))
        # 将文件转为 GBK
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        with open(path, "w", encoding="gbk") as f:
            f.write(content)
        articles = self.loader.load_csv(path)
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].title, "中医中药研究")

    def test_stats_after_load(self):
        path = self._write_csv("test.csv", (
            "article_id,title,abstract,language,pub_year\n"
            "1,糖尿病研究,摘要1,zh,2022\n"
            "2,Heart Study,,en,\n"
        ))
        self.loader.load_csv(path)
        stats = self.loader.stats
        self.assertEqual(stats.total_loaded, 2)
        self.assertEqual(stats.total_missing_abstract, 1)
        self.assertEqual(stats.total_missing_pub_year, 1)
        self.assertEqual(stats.lang_distribution.get("zh"), 1)
        self.assertEqual(stats.lang_distribution.get("en"), 1)


class TestDataLoaderJSON(unittest.TestCase):
    """测试 JSON 文件加载"""

    def setUp(self):
        self.loader = DataLoader()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_json(self, filename, data):
        import json
        path = os.path.join(self.tmpdir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return path

    def test_load_json_array(self):
        path = self._write_json("test.json", [
            {"title": "文献1", "abstract": "摘要1"},
            {"title": "文献2", "abstract": "摘要2"},
        ])
        articles = self.loader.load_json(path)
        self.assertEqual(len(articles), 2)

    def test_load_json_single_object(self):
        path = self._write_json("test.json",
            {"title": "单篇文献", "abstract": "单个对象"})
        articles = self.loader.load_json(path)
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].title, "单篇文献")

    def test_load_json_invalid(self):
        path = os.path.join(self.tmpdir, "bad.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("not valid json{{{")
        articles = self.loader.load_json(path)
        self.assertEqual(len(articles), 0)


class TestDataLoaderTXT(unittest.TestCase):
    """测试 TXT 文件加载"""

    def setUp(self):
        self.loader = DataLoader()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_txt(self, filename, content):
        path = os.path.join(self.tmpdir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_load_txt_plain(self):
        path = self._write_txt("test.txt", "中医疗效研究\n冠心病临床分析\n")
        articles = self.loader.load_txt(path)
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0].title, "中医疗效研究")
        self.assertEqual(articles[1].title, "冠心病临床分析")

    def test_load_txt_kv_format(self):
        content = (
            "标题: 中药治疗糖尿病研究\n"
            "摘要: 探讨中药在糖尿病治疗中的应用\n"
            "年份: 2022\n"
            "\n"
            "title: Hypertension Review\n"
            "abstract: A review of hypertension treatment\n"
            "pub_year: 2021\n"
        )
        path = self._write_txt("test.txt", content)
        articles = self.loader.load_txt(path)
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0].title, "中药治疗糖尿病研究")
        self.assertEqual(articles[1].title, "Hypertension Review")

    def test_load_txt_tsv_format(self):
        content = (
            "title\tabstract\tpub_year\n"
            "糖尿病研究\t关于糖尿病的研究\t2022\n"
            "高血压分析\t高血压临床分析\t2021\n"
        )
        path = self._write_txt("test.txt", content)
        articles = self.loader.load_txt(path)
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0].title, "糖尿病研究")


class TestDataLoaderDirectory(unittest.TestCase):
    """测试目录批量加载"""

    def setUp(self):
        self.loader = DataLoader()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_load_directory_mixed(self):
        import json
        # CSV
        csv_path = os.path.join(self.tmpdir, "a.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("article_id,title,abstract\n1,糖尿病研究,摘要1\n2,高血压研究,摘要2\n")
        # JSON
        json_path = os.path.join(self.tmpdir, "b.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump([{"title": "冠心病分析", "abstract": "摘要3"}], f, ensure_ascii=False)
        # TXT
        txt_path = os.path.join(self.tmpdir, "c.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("中药药理研究\n")
        # 应被忽略的文件
        with open(os.path.join(self.tmpdir, "readme.md"), "w") as f:
            f.write("# Readme")

        articles = self.loader.load_directory(self.tmpdir)
        self.assertEqual(len(articles), 4)  # 2 CSV + 1 JSON + 1 TXT

    def test_load_directory_not_exists(self):
        articles = self.loader.load_directory("/nonexistent/dir")
        self.assertEqual(len(articles), 0)


class TestDataLoaderValidation(unittest.TestCase):
    """测试数据验证功能"""

    def test_validate_articles_valid(self):
        articles = [
            Article("1", None, "标题1", "摘要1", "", "", None, "zh", ""),
            Article("2", None, "标题2", "摘要2", "", "", None, "zh", ""),
        ]
        valid, warnings = DataLoader.validate_articles(articles)
        self.assertEqual(len(valid), 2)
        self.assertEqual(len(warnings), 0)

    def test_validate_articles_empty_title(self):
        articles = [
            Article("1", None, "", "", "", "", None, "zh", ""),
            Article("2", None, "有效", "", "", "", None, "zh", ""),
        ]
        valid, warnings = DataLoader.validate_articles(articles)
        self.assertEqual(len(valid), 1)

    def test_get_summary(self):
        articles = [
            Article("1", "111", "标题1", "有摘要", "作者", "期刊", 2022, "zh", ""),
            Article("2", None, "标题2", None, None, None, None, "en", ""),
        ]
        summary = DataLoader.get_summary(articles)
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["has_abstract"], 1)
        self.assertEqual(summary["has_pmid"], 1)

    def test_reset_stats(self):
        loader = DataLoader()
        loader.stats.total_loaded = 10
        loader.reset_stats()
        self.assertEqual(loader.stats.total_loaded, 0)


# ============================================================
# StopWords 测试
# ============================================================

class TestStopWords(unittest.TestCase):
    """测试停用词管理器"""

    def setUp(self):
        self.sw = StopWords()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_stopwords(self, words):
        path = os.path.join(self.tmpdir, "stopwords.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(words))
        return path

    def test_load_stopwords(self):
        path = self._write_stopwords(["的", "了", "在", "是"])
        self.sw.load(path)
        self.assertEqual(len(self.sw), 4)
        self.assertTrue(self.sw.is_stopword("的"))
        self.assertFalse(self.sw.is_stopword("糖尿病"))

    def test_remove_stopwords(self):
        path = self._write_stopwords(["的", "了", "the", "is"])
        self.sw.load(path)
        tokens = ["糖尿病", "的", "治疗", "了", "the", "patient", "is", "sick"]
        result = self.sw.remove(tokens)
        self.assertEqual(result, ["糖尿病", "治疗", "patient", "sick"])

    def test_add_stopwords(self):
        self.sw.add(["新增停用词"])
        self.assertTrue(self.sw.is_stopword("新增停用词"))

    def test_empty_stopwords(self):
        tokens = ["词1", "词2", "词3"]
        result = self.sw.remove(tokens)
        self.assertEqual(result, tokens)  # 无停用词，全部保留

    def test_contains_operator(self):
        path = self._write_stopwords(["的", "是"])
        self.sw.load(path)
        self.assertIn("的", self.sw)
        self.assertNotIn("糖尿病", self.sw)


# ============================================================
# Preprocessor 测试
# ============================================================

class TestPreprocessorCleanText(unittest.TestCase):
    """测试文本清洗"""

    def setUp(self):
        self.preprocessor = Preprocessor(mode="medical")

    def test_clean_html_tags(self):
        text = "<p>糖尿病是一种<strong>慢性</strong>代谢疾病</p>"
        result = self.preprocessor.clean_text(text)
        self.assertNotIn("<p>", result)
        self.assertNotIn("<strong>", result)
        self.assertIn("糖尿病", result)
        self.assertIn("慢性", result)

    def test_clean_special_chars_strict(self):
        p = Preprocessor(mode="strict")
        result = p.clean_text("血糖值：7.8 mmol/L，体温：38.5℃")
        self.assertIn("血糖值", result)
        self.assertNotIn("7.8", result)  # 数字被移除
        self.assertNotIn("38.5", result)

    def test_clean_keep_numbers_medical(self):
        """medical 模式保留医学相关数字"""
        result = self.preprocessor.clean_text("血糖值：7.8 mmol/L，体温：38.5℃")
        self.assertIn("7.8", result)
        self.assertIn("38.5", result)

    def test_clean_empty_text(self):
        self.assertEqual(self.preprocessor.clean_text(""), "")
        self.assertEqual(self.preprocessor.clean_text(None), "")

    def test_clean_preserve_percentage(self):
        result = self.preprocessor.clean_text("有效率：91.7%")
        self.assertIn("91.7", result)

    def test_clean_normalize_whitespace(self):
        result = self.preprocessor.clean_text("  糖尿病   治疗  研究  ")
        self.assertEqual(result, "糖尿病 治疗 研究")


class TestPreprocessorSegment(unittest.TestCase):
    """测试分词"""

    def setUp(self):
        self.preprocessor = Preprocessor()

    def test_segment_zh(self):
        tokens = self.preprocessor.segment("糖尿病的中医辨证论治研究", "zh")
        self.assertIn("糖尿病", tokens)
        self.assertIn("中医", tokens)
        self.assertIn("辨证论治", tokens)

    def test_segment_en(self):
        tokens = self.preprocessor.segment(
            "Metformin treatment for type 2 diabetes patients", "en")
        self.assertIn("metformin", tokens)
        self.assertIn("treatment", tokens)
        self.assertIn("diabetes", tokens)

    def test_segment_en_filter_short(self):
        """英文过滤长度<=1的词（但保留医学术语短词）"""
        tokens = self.preprocessor.segment("I am a patient with T2DM", "en")
        self.assertNotIn("i", tokens)
        self.assertNotIn("a", tokens)

    def test_segment_empty_text(self):
        self.assertEqual(self.preprocessor.segment("", "zh"), [])
        self.assertEqual(self.preprocessor.segment("   ", "en"), [])

    def test_segment_zh_filter_numbers_only(self):
        """中文分词过滤纯数字 token"""
        tokens = self.preprocessor.segment("123 糖尿病 456 mg", "zh")
        self.assertIn("糖尿病", tokens)
        # 纯数字/单位应被过滤
        self.assertNotIn("123", tokens)
        self.assertNotIn("456", tokens)


class TestPreprocessorProcessArticle(unittest.TestCase):
    """测试单篇文献处理"""

    def setUp(self):
        sw = StopWords()
        self.preprocessor = Preprocessor(stopwords=sw)

    def test_process_basic_zh(self):
        article = Article(
            article_id="T1", pmid=None,
            title="糖尿病的中医治疗研究",
            abstract="探讨中医治疗糖尿病的临床效果",
            authors="", journal="", pub_year=None,
            language="zh", source_file="test",
        )
        result = self.preprocessor.process_article(article)
        self.assertGreater(len(result.tokens), 0)
        self.assertIn("糖尿病", result.tokens)
        self.assertIn("中医", result.tokens)

    def test_process_basic_en(self):
        article = Article(
            article_id="T2", pmid=None,
            title="Metformin and Diabetes Treatment",
            abstract="This study evaluates metformin efficacy",
            authors="", journal="", pub_year=None,
            language="en", source_file="test",
        )
        result = self.preprocessor.process_article(article)
        self.assertGreater(len(result.tokens), 0)
        self.assertIn("metformin", result.tokens)
        self.assertIn("diabetes", result.tokens)

    def test_process_empty_title_and_abstract(self):
        article = Article(
            article_id="T3", pmid=None,
            title="", abstract="",
            authors="", journal="", pub_year=None,
            language="zh", source_file="test",
        )
        result = self.preprocessor.process_article(article)
        self.assertEqual(result.tokens, [])
        self.assertEqual(self.preprocessor.stats.empty_text_count, 1)

    def test_process_with_stopwords(self):
        sw = StopWords()
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False,
                                          encoding="utf-8") as f:
            f.write("的\n了\n在\nthe\nis\nfor\n")
            sw_path = f.name
        sw.load(sw_path)
        os.unlink(sw_path)

        p = Preprocessor(stopwords=sw)
        article = Article(
            article_id="T4", pmid=None,
            title="糖尿病的中医治疗研究",
            abstract="",
            authors="", journal="", pub_year=None,
            language="zh", source_file="test",
        )
        result = p.process_article(article)
        self.assertNotIn("的", result.tokens)

    def test_process_stats_tracking(self):
        article = Article(
            article_id="T5", pmid=None,
            title="标题", abstract=None,
            authors="", journal="", pub_year=None,
            language="zh", source_file="test",
        )
        self.preprocessor.process_article(article)
        self.assertEqual(self.preprocessor.stats.total_articles, 1)
        self.assertEqual(self.preprocessor.stats.empty_abstract_count, 1)
        self.assertEqual(self.preprocessor.stats.zh_count, 1)


class TestPreprocessorProcessBatch(unittest.TestCase):
    """测试批量处理"""

    def setUp(self):
        self.preprocessor = Preprocessor()

    def test_process_batch_empty(self):
        result = self.preprocessor.process_batch([])
        self.assertEqual(result, [])

    def test_process_batch_multiple(self):
        articles = [
            Article(str(i), None, f"标题{i}", f"摘要{i}", "", "",
                    None, "zh", "test") for i in range(5)
        ]
        result = self.preprocessor.process_batch(articles, show_progress=False)
        self.assertEqual(len(result), 5)
        self.assertEqual(self.preprocessor.stats.total_articles, 5)

    def test_process_batch_with_error(self):
        """某篇处理出错不影响其他"""
        articles = [
            Article("1", None, "正常", "文献", "", "", None, "zh", "test"),
            # 故意触发异常的情况（language 为未知会走 else -> _segment_zh）
            Article("2", None, "Still OK", "still ok", "", "", None, "xx", "test"),
        ]
        result = self.preprocessor.process_batch(articles, show_progress=False)
        self.assertEqual(len(result), 2)


class TestPreprocessorUtils(unittest.TestCase):
    """测试工具方法"""

    def setUp(self):
        self.preprocessor = Preprocessor()

    def test_extract_keywords(self):
        article = Article("K1", None, "糖尿病的中医辨证论治",
                          "探讨中医辨证论治在糖尿病治疗中的应用",
                          "", "", None, "zh", "test")
        article = self.preprocessor.process_article(article)
        keywords = self.preprocessor.extract_keywords(article, top_n=5)
        self.assertGreater(len(keywords), 0)
        self.assertIsInstance(keywords[0], tuple)
        self.assertIsInstance(keywords[0][0], str)
        self.assertIsInstance(keywords[0][1], int)

    def test_extract_keywords_empty(self):
        article = Article("K2", None, "", "", "", "", None, "zh", "test")
        article = self.preprocessor.process_article(article)
        keywords = self.preprocessor.extract_keywords(article)
        self.assertEqual(keywords, [])

    def test_get_tokens_summary(self):
        articles = [
            Article("1", None, "标题1", "摘要1", "", "", None, "zh", "test"),
            Article("2", None, "标题2", "摘要2", "", "", None, "zh", "test"),
        ]
        articles = self.preprocessor.process_batch(articles, show_progress=False)
        summary = Preprocessor.get_tokens_summary(articles)
        self.assertEqual(summary["total_articles"], 2)
        self.assertIn("avg_tokens", summary)
        self.assertIn("min_tokens", summary)
        self.assertIn("max_tokens", summary)

    def test_get_tokens_summary_empty(self):
        summary = Preprocessor.get_tokens_summary([])
        self.assertEqual(summary, {"total_articles": 0})


class TestPreprocessStats(unittest.TestCase):
    """测试预处理统计信息"""

    def test_stats_defaults(self):
        stats = PreprocessStats()
        self.assertEqual(stats.total_articles, 0)
        self.assertEqual(stats.avg_tokens, 0.0)
        self.assertEqual(stats.stopword_removal_rate, 0.0)

    def test_stats_calculation(self):
        stats = PreprocessStats()
        stats.total_articles = 2
        stats.total_tokens_before = 100
        stats.total_tokens_after = 80
        self.assertEqual(stats.avg_tokens, 40.0)
        self.assertAlmostEqual(stats.stopword_removal_rate, 0.2, places=7)

    def test_stats_to_dict(self):
        stats = PreprocessStats()
        d = stats.to_dict()
        self.assertIn("total_articles", d)
        self.assertIn("avg_tokens_per_article", d)

    def test_stats_report(self):
        stats = PreprocessStats()
        report = stats.report()
        self.assertIn("文本预处理统计报告", report)


# ============================================================
# 集成测试 - 完整管道
# ============================================================

class TestIntegrationPipeline(unittest.TestCase):
    """集成测试：数据加载 -> 文本预处理"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_full_pipeline_csv(self):
        """完整流程：CSV 加载 -> 预处理 -> 验证"""
        # 1. 创建测试 CSV
        csv_path = os.path.join(self.tmpdir, "articles.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write(
                "article_id,title,abstract,pub_year,language\n"
                "1,糖尿病中医辨证论治研究,探讨中医辨证论治在2型糖尿病治疗中的临床效果,2022,zh\n"
                "2,冠心病用药规律分析,分析中药治疗冠心病的用药规律,2023,zh\n"
                "3,无效文献,\"\",2020,zh\n"  # 空标题->应被加载（标题存在）
            )

        # 2. 加载
        loader = DataLoader()
        articles = loader.load_csv(csv_path)
        self.assertEqual(len(articles), 3)

        # 3. 加载停用词
        sw_path = os.path.join(self.tmpdir, "stopwords.txt")
        with open(sw_path, "w", encoding="utf-8") as f:
            f.write("的\n了\n在\n和\n是\nthe\nof\nin\nfor\n")

        sw = StopWords()
        sw.load(sw_path)

        # 4. 预处理
        preprocessor = Preprocessor(stopwords=sw, mode="medical")
        articles = preprocessor.process_batch(articles, show_progress=False)

        # 5. 验证结果
        self.assertTrue(len(articles[0].tokens) > 0, "第一篇应有 tokens")
        self.assertIn("糖尿病", articles[0].tokens)
        self.assertIn("辨证论治", articles[0].tokens)

        self.assertTrue(len(articles[1].tokens) > 0, "第二篇应有 tokens")
        self.assertIn("冠心病", articles[1].tokens)

        # 第3篇摘要为空但标题存在，应有tokens
        self.assertEqual(articles[2].title, "无效文献")
        self.assertTrue(len(articles[2].tokens) > 0)

        # 6. 验证统计
        self.assertGreater(preprocessor.stats.total_tokens_after, 0)
        self.assertGreater(preprocessor.stats.avg_tokens, 0)

    def test_full_pipeline_with_real_test_data(self):
        """使用实际测试数据文件运行完整管道"""
        # 找到测试数据目录
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        chinese_dir = os.path.join(project_root, "data", "chinese")
        pubmed_dir = os.path.join(project_root, "data", "pubmed")
        stopwords_file = os.path.join(project_root, "data", "stopwords.txt")

        loader = DataLoader()

        # 加载中文数据
        if os.path.isdir(chinese_dir):
            zh_articles = loader.load_directory(chinese_dir)
            self.assertGreater(len(zh_articles), 0,
                               f"中文目录应有数据: {chinese_dir}")

            # 验证中文文献
            zh_titles = [a.title for a in zh_articles]
            self.assertTrue(any("糖尿病" in t for t in zh_titles),
                            "应包含糖尿病相关文献")

        # 加载 PubMed 数据
        if os.path.isdir(pubmed_dir):
            en_articles = loader.load_directory(pubmed_dir)
            self.assertGreater(len(en_articles), 0,
                               f"PubMed目录应有数据: {pubmed_dir}")

            # 验证英文文献
            en_titles = [a.title for a in en_articles]
            self.assertTrue(any("Diabetes" in t or "diabetes" in t.lower()
                               for t in en_titles),
                            "应包含糖尿病英文文献")

        # 预处理中文数据
        sw = StopWords()
        if os.path.exists(stopwords_file):
            sw.load(stopwords_file)

        preprocessor = Preprocessor(stopwords=sw, mode="medical")

        if os.path.isdir(chinese_dir):
            zh_articles = loader.load_directory(chinese_dir)
            processed = preprocessor.process_batch(zh_articles, show_progress=False)
            self.assertEqual(len(processed), len(zh_articles))
            # 所有文献都应有 tokens
            for a in processed:
                self.assertIsInstance(a.tokens, list)
                self.assertGreater(len(a.tokens), 0,
                                   f"文献 '{a.title}' 应有 token")

            # 验证关键词提取
            if processed:
                kw = preprocessor.extract_keywords(processed[0], top_n=5)
                self.assertGreater(len(kw), 0)

        # 打印统计报告
        if os.path.isdir(chinese_dir):
            print("\n" + loader.stats.report())
            print(preprocessor.stats.report())


# ============================================================
# 主测试入口
# ============================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
