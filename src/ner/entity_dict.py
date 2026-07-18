# -*- coding: utf-8 -*-
"""
实体词典管理器（增强版）
- 疾病/药物/症状词典加载与管理
- 中西双语实体映射
- 注释行过滤、去重统计
对应需求: FR-03
"""
import os
import logging
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ============================================================
# 英文 TCM 术语 → 中文实体映射表
# 用于在英文 PubMed 文献中识别中医相关实体
# ============================================================

EN_TO_CN_ENTITY: Dict[str, str] = {
    # ---- 中医概念 ----
    "traditional chinese medicine": "中医",
    "tcm": "中医",
    "chinese medicine": "中医",
    "chinese herbal medicine": "中药",
    "acupuncture": "针灸",
    "moxibustion": "艾灸",
    "cupping": "拔罐",
    "tuina": "推拿",
    "qigong": "气功",
    "tai chi": "太极拳",
    "baduanjin": "八段锦",
    "meridian": "经络",
    "acupoint": "穴位",
    "acupoints": "穴位",
    "syndrome differentiation": "辨证论治",
    "tongue diagnosis": "舌诊",
    "pulse diagnosis": "脉诊",

    # ---- 网络药理学 ----
    "network pharmacology": "网络药理学",
    "molecular docking": "分子对接",
    "systems pharmacology": "系统药理学",

    # ---- 中药饮片（植物学名）----
    "salvia miltiorrhiza": "丹参",
    "dan shen": "丹参",
    "panax ginseng": "人参",
    "panax notoginseng": "三七",
    "san qi": "三七",
    "astragalus membranaceus": "黄芪",
    "huang qi": "黄芪",
    "angelica sinensis": "当归",
    "dang gui": "当归",
    "glycyrrhiza uralensis": "甘草",
    "gan cao": "甘草",
    "ligusticum chuanxiong": "川芎",
    "chuan xiong": "川芎",
    "coptis chinensis": "黄连",
    "huang lian": "黄连",
    "scutellaria baicalensis": "黄芩",
    "huang qin": "黄芩",
    "phellodendron chinense": "黄柏",
    "huang bai": "黄柏",
    "rehmannia glutinosa": "地黄",
    "di huang": "地黄",
    "paeonia lactiflora": "白芍",
    "bai shao": "白芍",
    "paeonia veitchii": "赤芍",
    "chi shao": "赤芍",
    "dioscorea opposita": "山药",
    "shan yao": "山药",
    "lycium barbarum": "枸杞",
    "goji": "枸杞",
    "gou qi": "枸杞",
    "chrysanthemum morifolium": "菊花",
    "ju hua": "菊花",
    "gastrodia elata": "天麻",
    "tian ma": "天麻",
    "uncaria rhynchophylla": "钩藤",
    "gou teng": "钩藤",
    "bupleurum chinense": "柴胡",
    "chai hu": "柴胡",
    "poria cocos": "茯苓",
    "fu ling": "茯苓",
    "alisma orientale": "泽泻",
    "ze xie": "泽泻",
    "epimedium brevicornu": "淫羊藿",
    "carthamus tinctorius": "红花",
    "hong hua": "红花",
    "prunus persica": "桃仁",
    "tao ren": "桃仁",
    "pinellia ternata": "半夏",
    "ban xia": "半夏",
    "citrus reticulata": "陈皮",
    "chen pi": "陈皮",
    "atractylodes macrocephala": "白术",
    "bai zhu": "白术",
    "polygonum multiflorum": "何首乌",
    "he shou wu": "何首乌",
    "eucommia ulmoides": "杜仲",
    "du zhong": "杜仲",
    "achyranthes bidentata": "牛膝",
    "niu xi": "牛膝",
    "alpinia oxyphylla": "益智仁",
    "notopterygium incisum": "羌活",
    "houttuynia cordata": "鱼腥草",
    "lonicera japonica": "金银花",
    "forsythia suspensa": "连翘",
    "isatis indigotica": "板蓝根",
    "taraxacum officinale": "蒲公英",
    "pseudostellaria heterophylla": "太子参",
    "codonopsis pilosula": "党参",
    "ophiopogon japonicus": "麦冬",
    "schisandra chinensis": "五味子",
    "ziziphus jujuba": "酸枣仁",
    "zingiber officinale": "生姜",
    "cinnamomum cassia": "肉桂",
    "aconitum carmichaelii": "附子",
    "rheum palmatum": "大黄",
    "ephedra sinica": "麻黄",

    # ---- 中成药 ----
    "compound danshen dripping pill": "复方丹参滴丸",
    "shexiang baoxin pill": "麝香保心丸",
    "liuwei dihuang pill": "六味地黄丸",
    "lianhua qingwen capsule": "连花清瘟胶囊",
    "shenqi fuzheng injection": "参芪扶正注射液",
    "tcm injection": "中药注射剂",

    # ---- 常见疾病英文 → 中文 ----
    "diabetes": "糖尿病",
    "diabetes mellitus": "糖尿病",
    "type 2 diabetes": "2型糖尿病",
    "hypertension": "高血压",
    "coronary heart disease": "冠心病",
    "coronary artery disease": "冠心病",
    "myocardial infarction": "心肌梗死",
    "heart failure": "心力衰竭",
    "stroke": "脑卒中",
    "ischemic stroke": "缺血性脑卒中",
    "alzheimer": "阿尔茨海默病",
    "parkinson": "帕金森病",
    "chronic kidney disease": "慢性肾病",
    "liver cirrhosis": "肝硬化",
    "hepatitis b": "乙型肝炎",
    "rheumatoid arthritis": "类风湿关节炎",
    "osteoarthritis": "骨关节炎",
    "copd": "慢性阻塞性肺疾病",
    "chronic obstructive pulmonary disease": "慢性阻塞性肺疾病",
    "asthma": "哮喘",
    "depression": "抑郁症",
    "anxiety": "焦虑",
    "insomnia": "失眠",
    "cancer": "肿瘤",
    "breast cancer": "乳腺癌",
    "lung cancer": "肺癌",
    "liver cancer": "肝癌",
    "colorectal cancer": "结直肠癌",
    "gastric cancer": "胃癌",
    "obesity": "肥胖",
    "metabolic syndrome": "代谢综合征",
    "hyperlipidemia": "高脂血症",
    "nonalcoholic fatty liver disease": "脂肪肝",
    "nafld": "脂肪肝",
}

# 英文实体按类型分组（用于后续类型推断）
EN_ENTITY_TYPES: Dict[str, str] = {
    "traditional chinese medicine": "Drug",
    "tcm": "Drug",
    "chinese medicine": "Drug",
    "chinese herbal medicine": "Drug",
    "acupuncture": "Drug",
    "moxibustion": "Drug",
    "cupping": "Drug",
    "tuina": "Drug",
    "qigong": "Drug",
    "tai chi": "Drug",
    "baduanjin": "Drug",
    "network pharmacology": "Drug",
    "molecular docking": "Drug",
    "compound danshen dripping pill": "Drug",
    "shexiang baoxin pill": "Drug",
    "liuwei dihuang pill": "Drug",
    "lianhua qingwen capsule": "Drug",
    "shenqi fuzheng injection": "Drug",
    "tcm injection": "Drug",
}


class EntityDict:
    """实体词典管理器（增强版）

    功能:
      - 加载疾病/药物/症状三类词典
      - 支持英文 TCM 术语到中文实体的映射
      - 注释行过滤、去重统计
      - 按类型/名称查询

    用法:
        ed = EntityDict()
        ed.load_dicts("dicts")
        print(ed.lookup("糖尿病"))        # → "Disease"
        print(ed.lookup_en("salvia"))   # → "丹参"
    """

    def __init__(self):
        self.disease_set: Set[str] = set()
        self.drug_set: Set[str] = set()
        self.symptom_set: Set[str] = set()

        # name → type 正向映射
        self.name_to_type: Dict[str, str] = {}

        # 英文实体映射: 英文名 → (中文名, 类型)
        self.en_to_cn: Dict[str, str] = dict(EN_TO_CN_ENTITY)
        self.en_type_map: Dict[str, str] = dict(EN_ENTITY_TYPES)

        # 反向查找: 英文关键词 → 实体类型 (用于规则匹配)
        self._en_set: Set[str] = set(self.en_to_cn.keys())

    # ========== 词典加载 ==========

    def load_dicts(self, dict_dir: str) -> None:
        """从目录加载三类词典文件（自动过滤注释行）

        Args:
            dict_dir: 包含 disease_dict.txt / drug_dict.txt / symptom_dict.txt 的目录
        """
        dict_map = {
            "disease_dict.txt": ("Disease", "disease_set"),
            "drug_dict.txt": ("Drug", "drug_set"),
            "symptom_dict.txt": ("Symptom", "symptom_set"),
        }

        total_loaded = 0
        for filename, (entity_type, attr_name) in dict_map.items():
            file_path = os.path.join(dict_dir, filename)
            if not os.path.exists(file_path):
                logger.warning("词典文件不存在: %s", file_path)
                continue

            names = set()
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    # 跳过空行和注释行（以 # 开头）
                    if not stripped or stripped.startswith("#"):
                        continue
                    names.add(stripped)

            getattr(self, attr_name).update(names)
            for name in names:
                # 已存在的不覆盖（一个实体只能属于一种类型）
                if name not in self.name_to_type:
                    self.name_to_type[name] = entity_type

            logger.info("加载 %s 词典: %s (%d 个实体)", entity_type, filename, len(names))
            total_loaded += len(names)

        logger.info("词典加载完成，共 %d 个实体", total_loaded)

    def add_entity(self, name: str, entity_type: str) -> bool:
        """程序化添加单个实体

        Args:
            name:        实体名称
            entity_type: Disease / Drug / Symptom

        Returns:
            是否成功添加（已存在的返回 False）
        """
        entity_type = entity_type.capitalize()
        if entity_type not in ("Disease", "Drug", "Symptom"):
            raise ValueError(f"未知实体类型: {entity_type}")

        target_set = {
            "Disease": self.disease_set,
            "Drug": self.drug_set,
            "Symptom": self.symptom_set,
        }[entity_type]

        if name in target_set:
            return False

        target_set.add(name)
        self.name_to_type[name] = entity_type
        return True

    def add_en_mapping(self, en_term: str, cn_name: str, entity_type: str = "") -> None:
        """添加英文术语到中文实体的映射

        Args:
            en_term:    英文术语（小写）
            cn_name:    对应的中文实体名
            entity_type: 实体类型（可选，留空则从已有词典推断）
        """
        en_term = en_term.lower().strip()
        self.en_to_cn[en_term] = cn_name
        self._en_set.add(en_term)
        if entity_type:
            self.en_type_map[en_term] = entity_type

    # ========== 查询 ==========

    def lookup(self, name: str) -> Optional[str]:
        """查中文实体名 → 返回类型 (Disease/Drug/Symptom)"""
        return self.name_to_type.get(name)

    def lookup_en(self, en_term: str) -> Optional[str]:
        """查英文术语 → 返回对应的中文实体名"""
        return self.en_to_cn.get(en_term.lower().strip())

    def lookup_en_type(self, en_term: str) -> Optional[str]:
        """查英文术语 → 返回实体类型"""
        term = en_term.lower().strip()
        cn_name = self.en_to_cn.get(term)
        if cn_name and cn_name in self.name_to_type:
            return self.name_to_type[cn_name]
        return self.en_type_map.get(term)

    def has_en(self, en_term: str) -> bool:
        """检查是否为已知的英文实体"""
        return en_term.lower().strip() in self._en_set

    def _has_en_entity(self, en_term: str) -> bool:
        """别名（兼容旧接口）"""
        return self.has_en(en_term)

    def get_entities_by_type(self, entity_type: str) -> Set[str]:
        """获取指定类型的所有实体名"""
        entity_type = entity_type.capitalize()
        mapping = {
            "Disease": self.disease_set,
            "Drug": self.drug_set,
            "Symptom": self.symptom_set,
        }
        return mapping.get(entity_type, set())

    def get_all_entities(self) -> Dict[str, Set[str]]:
        """获取全部实体"""
        return {
            "Disease": self.disease_set,
            "Drug": self.drug_set,
            "Symptom": self.symptom_set,
        }

    # ========== 统计 ==========

    def get_stats(self) -> Dict:
        """返回词典统计信息"""
        return {
            "Disease": len(self.disease_set),
            "Drug": len(self.drug_set),
            "Symptom": len(self.symptom_set),
            "Total": len(self.name_to_type),
            "EN_Mappings": len(self.en_to_cn),
        }

    def __repr__(self) -> str:
        s = self.get_stats()
        return (f"EntityDict(disease={s['Disease']}, drug={s['Drug']}, "
                f"symptom={s['Symptom']}, en_map={s['EN_Mappings']})")
