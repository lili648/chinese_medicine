# -*- coding: utf-8 -*-
"""
实体识别引擎（增强版）
- 中文：jieba 分词 + 词典正向最大匹配
- 英文：规则匹配 + 短语检测 + 词典映射
- 自动语种检测、频率统计、批量处理
对应需求: FR-04
"""
import json
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import jieba

from .entity_dict import EntityDict
from ..preprocessing.data_loader import Article

logger = logging.getLogger(__name__)


@dataclass
class RecognizeStats:
    """实体识别统计"""
    total_articles: int = 0
    articles_with_entities: int = 0
    total_entities: int = 0
    entities_by_type: Counter = field(default_factory=Counter)
    entities_by_method: Counter = field(default_factory=Counter)
    tokens_processed: int = 0

    def report(self) -> str:
        lines = [
            "=" * 50,
            "实体识别统计报告",
            "=" * 50,
            f"处理文献数:     {self.total_articles}",
            f"含实体文献数:   {self.articles_with_entities}",
            f"总实体提及数:   {self.total_entities}",
            f"处理Token数:    {self.tokens_processed}",
            "-" * 50,
        ]
        for etype in ["Disease", "Drug", "Symptom"]:
            lines.append(f"  {etype:10s}: {self.entities_by_type.get(etype, 0):5d}")
        lines.append("-" * 50)
        for method in sorted(self.entities_by_method.keys()):
            lines.append(f"  [{method:10s}]: {self.entities_by_method[method]:5d}")
        lines.append("=" * 50)
        return "\n".join(lines)


# ============================================================
# 英文 TCM 规则匹配模式
# ============================================================

# 多词短语匹配（大小写不敏感）
EN_TCM_PATTERNS: List[Tuple[str, str, str]] = [
    # (正则模式, 中文名, 实体类型)
    # 中医概念
    (r"traditional\s+chinese\s+medicine", "中医", "Drug"),
    (r"chinese\s+herbal\s+medicine", "中药", "Drug"),
    (r"chinese\s+medicine", "中医", "Drug"),
    (r"chinese\s+herb\s+formula", "中药方剂", "Drug"),
    (r"herbal\s+medicine", "草药", "Drug"),
    (r"herbal\s+extract", "草药提取物", "Drug"),
    # 针灸相关
    (r"acupuncture", "针灸", "Drug"),
    (r"electro[\s-]?acupuncture", "电针", "Drug"),
    (r"acupressure", "指压", "Drug"),
    (r"auricular\s+acupuncture", "耳针", "Drug"),
    (r"scalp\s+acupuncture", "头针", "Drug"),
    (r"moxibustion", "艾灸", "Drug"),
    (r"cupping\s+therapy", "拔罐", "Drug"),
    (r"cupping", "拔罐", "Drug"),
    (r"tuina", "推拿", "Drug"),
    (r"qigong", "气功", "Drug"),
    (r"tai\s*chi", "太极拳", "Drug"),
    (r"baduanjin", "八段锦", "Drug"),
    # 诊断
    (r"syndrome\s+differentiation", "辨证论治", "Drug"),
    (r"tongue\s+diagnosis", "舌诊", "Drug"),
    (r"pulse\s+diagnosis", "脉诊", "Drug"),
    # 药理学方法
    (r"network\s+pharmacology", "网络药理学", "Drug"),
    (r"molecular\s+docking", "分子对接", "Drug"),
    (r"systems\s+pharmacology", "系统药理学", "Drug"),
    (r"pharmacophore\s+model", "药效团模型", "Drug"),
    # 方剂
    (r"compound\s+danshen\s+.*pill", "复方丹参滴丸", "Drug"),
    (r"liuwei\s+dihuang", "六味地黄丸", "Drug"),
    (r"shexiang\s+baoxin", "麝香保心丸", "Drug"),
    (r"lianhua\s+qingwen", "连花清瘟胶囊", "Drug"),
    # 中成药注射剂
    (r"tcm\s+injection", "中药注射剂", "Drug"),
    (r"shenmai\s+injection", "参麦注射液", "Drug"),
    (r"shenfu\s+injection", "参附注射液", "Drug"),
    (r"danhong\s+injection", "丹红注射液", "Drug"),
    (r"xuebijing\s+injection", "血必净注射液", "Drug"),
    # 常见方剂
    (r"yinqiao\s+san", "银翘散", "Drug"),
    (r"buzhong\s+yiqi", "补中益气", "Drug"),
    (r"xiaoyao\s+san", "逍遥散", "Drug"),
    (r"xuefu\s+zhuyu", "血府逐瘀", "Drug"),
    (r"huoxiang\s+zhengqi", "藿香正气", "Drug"),
]

# 单味中药英文模式（植物学名或拼音）
EN_HERB_PATTERNS: List[Tuple[str, str]] = [
    (r"salvia\s+miltiorrhiza", "丹参"),
    (r"dan\s*shen", "丹参"),
    (r"panax\s+notoginseng", "三七"),
    (r"san\s*qi", "三七"),
    (r"panax\s+ginseng", "人参"),
    (r"astragalus\s+membranaceus", "黄芪"),
    (r"huang\s*qi", "黄芪"),
    (r"angelica\s+sinensis", "当归"),
    (r"dang\s*gui", "当归"),
    (r"glycyrrhiza\s+uralensis", "甘草"),
    (r"gan\s*cao", "甘草"),
    (r"ligusticum\s+chuanxiong", "川芎"),
    (r"chuan\s*xiong", "川芎"),
    (r"coptis\s+chinensis", "黄连"),
    (r"huang\s*lian", "黄连"),
    (r"scutellaria\s+baicalensis", "黄芩"),
    (r"huang\s*qin", "黄芩"),
    (r"rehmannia\s+glutinosa", "地黄"),
    (r"di\s*huang", "地黄"),
    (r"paeonia\s+lactiflora", "白芍"),
    (r"paeonia\s+veitchii", "赤芍"),
    (r"paeonia\s+suffruticosa", "牡丹皮"),
    (r"paeonia", "芍药"),
    (r"lycium\s+barbarum", "枸杞"),
    (r"chrysanthemum\s+morifolium", "菊花"),
    (r"gastrodia\s+elata", "天麻"),
    (r"uncaria\s+rhynchophylla", "钩藤"),
    (r"bupleurum\s+chinense", "柴胡"),
    (r"poria\s+cocos", "茯苓"),
    (r"alisma\s+orientale", "泽泻"),
    (r"epimedium\s+brevicornu", "淫羊藿"),
    (r"carthamus\s+tinctorius", "红花"),
    (r"prunus\s+persica", "桃仁"),
    (r"pinellia\s+ternata", "半夏"),
    (r"atractylodes\s+macrocephala", "白术"),
    (r"citrus\s+reticulata", "陈皮"),
    (r"polygonum\s+multiflorum", "何首乌"),
    (r"eucommia\s+ulmoides", "杜仲"),
    (r"achyranthes\s+bidentata", "牛膝"),
    (r"dioscorea\s+opposita", "山药"),
    (r"houttuynia\s+cordata", "鱼腥草"),
    (r"lonicera\s+japonica", "金银花"),
    (r"forsythia\s+suspensa", "连翘"),
    (r"pseudostellaria\s+heterophylla", "太子参"),
    (r"codonopsis\s+pilosula", "党参"),
    (r"ophiopogon\s+japonicus", "麦冬"),
    (r"schisandra\s+chinensis", "五味子"),
    (r"ziziphus\s+jujuba", "酸枣仁"),
    (r"zingiber\s+officinale", "生姜"),
    (r"cinnamomum\s+cassia", "肉桂"),
    (r"aconitum\s+carmichaelii", "附子"),
    (r"rheum\s+palmatum|rheum\s+officinale", "大黄"),
    (r"ephedra\s+sinica", "麻黄"),
    (r"curcuma\s+longa", "姜黄"),
    (r"ginkgo\s+biloba", "银杏叶"),
]

# 英文疾病模式
EN_DISEASE_PATTERNS: List[Tuple[str, str]] = [
    (r"type\s*2\s+diabetes\s+mellitus", "2型糖尿病"),
    (r"type\s*2\s+diabetes", "2型糖尿病"),
    (r"diabetes\s+mellitus", "糖尿病"),
    (r"coronary\s+(artery|heart)\s+disease", "冠心病"),
    (r"myocardial\s+infarction", "心肌梗死"),
    (r"heart\s+failure", "心力衰竭"),
    (r"acute\s+ischemic\s+stroke", "急性缺血性脑卒中"),
    (r"ischemic\s+stroke", "缺血性脑卒中"),
    (r"hemorrhagic\s+stroke", "出血性脑卒中"),
    (r"chronic\s+kidney\s+disease", "慢性肾病"),
    (r"chronic\s+obstructive\s+pulmonary\s+disease", "慢性阻塞性肺疾病"),
    (r"rheumatoid\s+arthritis", "类风湿关节炎"),
    (r"alzheimer\'?s?\s+disease", "阿尔茨海默病"),
    (r"parkinson\'?s?\s+disease", "帕金森病"),
    (r"nonalcoholic\s+fatty\s+liver\s+disease", "脂肪肝"),
    (r"metabolic\s+syndrome", "代谢综合征"),
    (r"hyperlipidemia", "高脂血症"),
    (r"hyperglycemia", "高血糖"),
    (r"non[-\s]?small\s+cell\s+lung\s+cancer", "非小细胞肺癌"),
    (r"hepatocellular\s+carcinoma", "肝细胞癌"),
]

# 英文症状模式
EN_SYMPTOM_PATTERNS: List[Tuple[str, str]] = [
    (r"chest\s+pain", "胸痛"),
    (r"chest\s+discomfort", "胸闷"),
    (r"abdominal\s+pain", "腹痛"),
    (r"abdominal\s+distention", "腹胀"),
    (r"shortness\s+of\s+breath", "气短"),
    (r"difficulty\s+breathing", "呼吸困难"),
    (r"palpitation", "心悸"),
    (r"dizziness", "头晕"),
    (r"fatigue", "乏力"),
    (r"nausea", "恶心"),
    (r"vomiting", "呕吐"),
    (r"diarrhea", "腹泻"),
    (r"constipation", "便秘"),
    (r"headache", "头痛"),
    (r"insomnia", "失眠"),
    (r"edema", "水肿"),
    (r"anorexia", "食欲减退"),
    (r"polyuria", "多尿"),
    (r"polydipsia", "烦渴"),
    (r"polyphagia", "多食"),
    (r"cough", "咳嗽"),
    (r"fever", "发热"),
]


class EntityRecognizer:
    """医学实体识别引擎（增强版）

    支持策略:
      - 中文模式: jieba 分词 + 词典正向最大匹配 + token 级词典查找
      - 英文模式: 正则规则匹配 + 短语检测 + 英文-中文映射
      - 混合模式: 自动检测语种，合并去重

    用法:
        from src.ner import EntityDict, EntityRecognizer

        ed = EntityDict()
        ed.load_dicts("dicts")

        recognizer = EntityRecognizer(ed)
        entities = recognizer.recognize(article.tokens, article.abstract)
    """

    def __init__(self, entity_dict: EntityDict, max_match_length: int = 12):
        """
        Args:
            entity_dict:      实体词典管理器
            max_match_length: 中文正向最大匹配的最长词长度（默认12）
        """
        self.entity_dict = entity_dict
        self.max_match_length = max_match_length
        self.stats = RecognizeStats()

        # 编译英文正则模式（预编译提升性能）
        self._en_tcm_re = [(re.compile(pat, re.IGNORECASE), cn, tp)
                           for pat, cn, tp in EN_TCM_PATTERNS]
        self._en_herb_re = [(re.compile(pat, re.IGNORECASE), cn)
                            for pat, cn in EN_HERB_PATTERNS]
        self._en_disease_re = [(re.compile(pat, re.IGNORECASE), cn)
                               for pat, cn in EN_DISEASE_PATTERNS]
        self._en_symptom_re = [(re.compile(pat, re.IGNORECASE), cn)
                               for pat, cn in EN_SYMPTOM_PATTERNS]

    # ========== 公开接口 ==========

    def recognize(
        self,
        tokens: List[str],
        raw_text: str = "",
        language: str = "auto",
    ) -> List[Dict]:
        """对单篇文献进行实体识别

        根据语种自动选择识别策略：中文→FMM+jieba，英文→规则+token匹配

        Args:
            tokens:   已分词的 token 列表
            raw_text: 原始文本（用于英文规则匹配，可选）
            language: 语种 ("zh" / "en" / "auto")

        Returns:
            [{"entity_name": str, "entity_type": str, "match_method": str}, ...]
        """
        if not tokens and not raw_text:
            return []

        # 自动检测语种
        if language == "auto":
            language = self._detect_language(tokens, raw_text)

        entities: List[Dict] = []

        if language == "zh":
            # 中文模式
            text = raw_text if raw_text else " ".join(tokens)
            entities.extend(self._recognize_cn_fmm(tokens))
            entities.extend(self._recognize_cn_jieba(text))
        else:
            # 英文模式
            text = raw_text if raw_text else " ".join(tokens)
            entities.extend(self._recognize_en_rules(text))
            entities.extend(self._recognize_en_dict(tokens))
            entities.extend(self._recognize_en_phrases(text))

        return self._deduplicate(entities)

    def recognize_article(self, article: Article) -> List[Dict]:
        """识别单篇 Article 中的实体

        Args:
            article: 预处理后的 Article 对象

        Returns:
            实体列表
        """
        # 构建原始文本（合并标题和摘要用于英文规则匹配）
        raw_parts = []
        if article.title:
            raw_parts.append(article.title)
        if article.abstract:
            raw_parts.append(article.abstract)
        raw_text = " ".join(raw_parts)

        language = article.language or self._detect_language(article.tokens, raw_text)

        result = self.recognize(article.tokens, raw_text, language)
        self.stats.tokens_processed += len(article.tokens) if article.tokens else 0
        return result

    def recognize_batch(
        self,
        articles: List[Article],
        progress_every: int = 100,
    ) -> List[Dict]:
        """批量识别，返回带文章关联的实体列表

        Args:
            articles:       Article 列表
            progress_every: 每处理 N 篇输出一次日志

        Returns:
            [{"entity_name": str, "entity_type": str, "article_id": str,
              "match_method": str, "frequency": int}, ...]
        """
        self.stats = RecognizeStats()
        self.stats.total_articles = len(articles)

        all_results: List[Dict] = []

        for idx, article in enumerate(articles):
            if (idx + 1) % progress_every == 0:
                logger.info("实体识别进度: %d/%d 篇", idx + 1, len(articles))

            try:
                entities = self.recognize_article(article)
            except Exception:
                logger.warning("实体识别失败: %s (跳过)", getattr(article, "article_id", "unknown"))
                continue

            if entities:
                self.stats.articles_with_entities += 1

            for ent in entities:
                self.stats.total_entities += 1
                self.stats.entities_by_type[ent["entity_type"]] += 1
                self.stats.entities_by_method[ent["match_method"]] += 1

                all_results.append({
                    "entity_name": ent["entity_name"],
                    "entity_type": ent["entity_type"],
                    "article_id": article.article_id,
                    "match_method": ent["match_method"],
                    "frequency": 1,
                })

        logger.info("批量识别完成: %d 篇中 %d 篇含实体, 共 %d 次实体提及",
                    self.stats.total_articles,
                    self.stats.articles_with_entities,
                    self.stats.total_entities)

        return all_results

    def get_top_entities(self, entities: List[Dict], top_n: int = 20) -> List[Dict]:
        """获取最高频实体"""
        counter = Counter()
        for e in entities:
            key = (e["entity_name"], e["entity_type"])
            counter[key] += 1

        result = []
        for (name, etype), count in counter.most_common(top_n):
            result.append({
                "entity_name": name,
                "entity_type": etype,
                "frequency": count,
            })
        return result

    def export_json(self, entities: List[Dict], output_path: str) -> str:
        """导出为 entities.json"""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(entities, f, ensure_ascii=False, indent=2)
        logger.info("已导出 %d 条实体记录到 %s", len(entities), output_path)
        return output_path

    # ========== 中文识别方法 ==========

    def _recognize_cn_fmm(self, tokens: List[str]) -> List[Dict]:
        """中文：正向最大匹配（在已分词 token 序列上滑动组合匹配）

        对 token 序列做窗口滑动，尝试用不同长度组合去词典中匹配。
        匹配到最长实体后跳过已用 token。
        """
        entities = []
        n = len(tokens)
        i = 0
        while i < n:
            matched = False
            max_len = min(self.max_match_length, n - i)
            for length in range(max_len, 0, -1):
                phrase = "".join(tokens[i:i + length])
                entity_type = self.entity_dict.lookup(phrase)
                if entity_type:
                    entities.append({
                        "entity_name": phrase,
                        "entity_type": entity_type,
                        "match_method": "fmm",
                    })
                    i += length
                    matched = True
                    break
            if not matched:
                i += 1
        return entities

    def _recognize_cn_jieba(self, text: str) -> List[Dict]:
        """中文：jieba 分词后逐词匹配词典

        对原始文本做 jieba 分词，然后用每个词去词典中查找。
        同时尝试合并连续 token 做更长匹配。
        """
        entities = []
        words = jieba.lcut(text)

        # 逐词匹配
        for word in words:
            word = word.strip()
            if len(word) < 2:
                continue
            entity_type = self.entity_dict.lookup(word)
            if entity_type:
                entities.append({
                    "entity_name": word,
                    "entity_type": entity_type,
                    "match_method": "jieba_dict",
                })

        # 尝试合并连续 2-3 个词做匹配
        for i in range(len(words) - 1):
            for span in (2, 3):
                if i + span <= len(words):
                    phrase = "".join(words[i:i + span])
                    if len(phrase) >= 4:  # 合并后至少4字符
                        entity_type = self.entity_dict.lookup(phrase)
                        if entity_type:
                            entities.append({
                                "entity_name": phrase,
                                "entity_type": entity_type,
                                "match_method": "jieba_concat",
                            })

        return entities

    # ========== 英文识别方法 ==========

    def _recognize_en_rules(self, text: str) -> List[Dict]:
        """英文：正则规则匹配（多词中医概念、方剂名、中成药等）

        依次用三类正则匹配：TCM概念 → 中药 → 疾病 → 症状
        """
        if not text:
            return []

        entities = []
        text_lower = text.lower()

        for regex, cn_name, entity_type in self._en_tcm_re:
            for m in regex.finditer(text):
                entities.append({
                    "entity_name": cn_name,
                    "entity_type": entity_type,
                    "match_method": "en_rule_tcm",
                })

        for regex, cn_name in self._en_herb_re:
            if regex.search(text_lower):
                # 去重检查（同一中药只计一次）
                entities.append({
                    "entity_name": cn_name,
                    "entity_type": "Drug",
                    "match_method": "en_rule_herb",
                })

        for regex, cn_name in self._en_disease_re:
            if regex.search(text_lower):
                entities.append({
                    "entity_name": cn_name,
                    "entity_type": "Disease",
                    "match_method": "en_rule_disease",
                })

        for regex, cn_name in self._en_symptom_re:
            if regex.search(text_lower):
                entities.append({
                    "entity_name": cn_name,
                    "entity_type": "Symptom",
                    "match_method": "en_rule_symptom",
                })

        return entities

    def _recognize_en_dict(self, tokens: List[str]) -> List[Dict]:
        """英文：token 级词典查找 + 滑动短语匹配

        - 单个 token 去英文映射表查找
        - token 合并（2-4词）去英文映射表查找
        """
        entities = []
        tokens_lower = [t.lower() for t in tokens if len(t) >= 2]

        # 滑动窗口短语匹配
        for win_size in (4, 3, 2, 1):
            for i in range(len(tokens_lower) - win_size + 1):
                phrase = " ".join(tokens_lower[i:i + win_size])
                cn_name = self.entity_dict.lookup_en(phrase)
                if cn_name:
                    etype = (self.entity_dict.lookup_en_type(phrase)
                             or self.entity_dict.lookup(cn_name)
                             or "Drug")
                    entities.append({
                        "entity_name": cn_name,
                        "entity_type": etype,
                        "match_method": "en_dict_phrase",
                    })

        return entities

    def _recognize_en_phrases(self, text: str) -> List[Dict]:
        """英文：常见医学实体短语检测（单次计数）

        在原始文本中检测常见疾病/症状英文短语。
        """
        if not text:
            return []

        entities = []
        text_lower = text.lower()

        # 简单关键词匹配（不依赖正则，速度快）
        simple_drug_keywords = [
            ("ginseng", "人参"), ("astragalus", "黄芪"), ("ginkgo", "银杏叶"),
            ("curcumin", "姜黄素"), ("resveratrol", "白藜芦醇"),
            ("berberine", "小檗碱"), ("tanshinone", "丹参酮"),
            ("salvianolic acid", "丹酚酸"), ("baicalin", "黄芩苷"),
            ("glycyrrhizin", "甘草酸"), ("paeoniflorin", "芍药苷"),
            ("matrine", "苦参碱"), ("ligustrazine", "川芎嗪"),
            ("ferulic acid", "阿魏酸"), ("rhein", "大黄酸"),
        ]

        for en_term, cn_name in simple_drug_keywords:
            if en_term in text_lower:
                entities.append({
                    "entity_name": cn_name,
                    "entity_type": "Drug",
                    "match_method": "en_keyword",
                })

        return entities

    # ========== 通用方法 ==========

    @staticmethod
    def _deduplicate(entities: List[Dict]) -> List[Dict]:
        """同篇文章内实体去重（按名称+类型去重，保留优先方法标记）"""
        seen = {}
        result = []
        # 方法优先级：fmm > jieba_dict > en_rule > en_dict_phrase > en_keyword
        priority = {"fmm": 1, "jieba_dict": 2, "jieba_concat": 2,
                    "en_rule_tcm": 3, "en_rule_herb": 3,
                    "en_rule_disease": 3, "en_rule_symptom": 3,
                    "en_dict_phrase": 4, "en_keyword": 5}

        for ent in entities:
            key = (ent["entity_name"], ent["entity_type"])
            if key not in seen:
                seen[key] = ent
                result.append(ent)
            else:
                # 保留优先级更高的方法
                existing = seen[key]
                cur_pri = priority.get(ent["match_method"], 99)
                ex_pri = priority.get(existing["match_method"], 99)
                if cur_pri < ex_pri:
                    seen[key] = ent
                    result[result.index(existing)] = ent

        return result

    @staticmethod
    def _detect_language(tokens: List[str], raw_text: str = "") -> str:
        """自动检测语种"""
        text = raw_text if raw_text else " ".join(tokens) if tokens else ""
        if not text:
            return "en"

        # 统计中文字符比例
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        total_chars = len(text.replace(" ", ""))
        if total_chars > 0 and chinese_chars / max(total_chars, 1) > 0.15:
            return "zh"
        return "en"

    def reset_stats(self) -> None:
        """重置统计"""
        self.stats = RecognizeStats()
