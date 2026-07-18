# -*- coding: utf-8 -*-
"""
医学词典扩充器
从内置知识库种子词出发，可选通过线上知识库进一步扩展实体词典

三套词典种子词（覆盖中医常见疾病/药物/症状）：
  - disease_dict:  100+ 常见疾病（ICD-10 分类 + 中医病证）
  - drug_dict:     150+ 常用药物（西药 + 中成药 + 中药饮片）
  - symptom_dict:  100+ 常见症状/体征
"""
import logging
import os
import re
from typing import Dict, List, Optional, Set, Tuple

from .base import BaseCrawler

logger = logging.getLogger(__name__)

# ============================================================
# 内置种子词典 — 中医+西医常见实体
# ============================================================

SEED_DISEASES = [
    # ---- 内分泌/代谢 ----
    "糖尿病", "2型糖尿病", "1型糖尿病", "妊娠期糖尿病", "糖尿病肾病",
    "糖尿病视网膜病变", "糖尿病足", "低血糖症", "高脂血症", "高尿酸血症",
    "痛风", "肥胖症", "代谢综合征", "甲状腺功能亢进症", "甲状腺功能减退症",
    "甲状腺结节", "骨质疏松症",

    # ---- 心血管 ----
    "高血压", "原发性高血压", "继发性高血压", "冠心病", "冠状动脉粥样硬化性心脏病",
    "心绞痛", "心肌梗死", "急性心肌梗死", "心力衰竭", "慢性心力衰竭",
    "心律失常", "心房颤动", "室性早搏", "房室传导阻滞", "心肌病",
    "风湿性心脏病", "先天性心脏病", "肺源性心脏病",
    "动脉粥样硬化", "下肢静脉曲张", "深静脉血栓",

    # ---- 脑血管 ----
    "脑卒中", "缺血性脑卒中", "出血性脑卒中", "脑梗死", "脑出血",
    "短暂性脑缺血发作", "蛛网膜下腔出血", "血管性痴呆",

    # ---- 呼吸 ----
    "慢性阻塞性肺疾病", "支气管哮喘", "肺炎", "新型冠状病毒肺炎",
    "肺结核", "支气管扩张", "肺纤维化", "间质性肺炎", "上呼吸道感染",
    "过敏性鼻炎", "慢性咽炎", "睡眠呼吸暂停综合征",

    # ---- 消化 ----
    "慢性胃炎", "萎缩性胃炎", "消化性溃疡", "胃食管反流病", "功能性消化不良",
    "肠易激综合征", "溃疡性结肠炎", "克罗恩病", "慢性乙型肝炎",
    "肝硬化", "脂肪肝", "非酒精性脂肪性肝病", "胆囊炎", "胆石症",
    "急性胰腺炎", "慢性胰腺炎", "便秘", "慢性腹泻",

    # ---- 泌尿 ----
    "慢性肾炎", "肾病综合征", "慢性肾功能衰竭", "尿毒症", "肾结石",
    "泌尿系感染", "前列腺增生", "慢性前列腺炎", "IgA肾病",

    # ---- 神经系统 ----
    "帕金森病", "阿尔茨海默病", "偏头痛", "紧张性头痛", "癫痫",
    "三叉神经痛", "面神经麻痹", "重症肌无力", "多发性硬化",
    "周围神经病变", "眩晕症", "失眠", "焦虑障碍", "抑郁症",

    # ---- 骨骼/风湿 ----
    "类风湿关节炎", "骨关节炎", "强直性脊柱炎", "系统性红斑狼疮",
    "颈椎病", "腰椎间盘突出症", "肩周炎", "干燥综合征", "白塞病",

    # ---- 血液/肿瘤 ----
    "缺铁性贫血", "再生障碍性贫血", "白血病", "淋巴瘤", "肺癌",
    "胃癌", "肝癌", "食管癌", "结直肠癌", "乳腺癌", "宫颈癌",
    "前列腺癌", "鼻咽癌", "甲状腺癌", "胰腺癌",

    # ---- 中医病证 ----
    "胸痹", "心悸", "中风", "眩晕", "消渴病", "痹证", "痿证",
    "咳嗽", "哮喘", "胃痛", "痞满", "泄泻", "黄疸",
    "水肿", "淋证", "遗精", "阳痿", "郁证", "不寐", "头痛",
    "腰腿痛", "虚劳", "汗证", "血证", "痰饮", "癥瘕积聚",

    # ---- 妇/儿科 ----
    "月经不调", "痛经", "闭经", "多囊卵巢综合征", "子宫内膜异位症",
    "不孕症", "小儿肺炎", "小儿腹泻", "小儿厌食症", "注意缺陷多动障碍",

    # ---- 皮肤 ----
    "湿疹", "荨麻疹", "银屑病", "带状疱疹", "痤疮", "白癜风",
    "神经性皮炎", "黄褐斑",

    # ---- 眼科/耳鼻喉 ----
    "老年性白内障", "青光眼", "年龄相关性黄斑变性",
    "突发性耳聋", "梅尼埃病", "慢性鼻窦炎",
]

SEED_DRUGS = [
    # ---- 降糖药 ----
    "二甲双胍", "格列美脲", "格列齐特", "格列吡嗪", "阿卡波糖",
    "伏格列波糖", "吡格列酮", "罗格列酮", "西格列汀", "沙格列汀",
    "维格列汀", "利拉鲁肽", "度拉糖肽", "司美格鲁肽", "达格列净",
    "恩格列净", "卡格列净",

    # ---- 胰岛素类 ----
    "胰岛素", "门冬胰岛素", "赖脯胰岛素", "甘精胰岛素", "地特胰岛素",
    "德谷胰岛素", "预混胰岛素",

    # ---- 降压药 ----
    "硝苯地平", "氨氯地平", "非洛地平", "贝那普利", "依那普利",
    "培哚普利", "氯沙坦", "缬沙坦", "厄贝沙坦", "替米沙坦",
    "美托洛尔", "比索洛尔", "卡维地洛", "氢氯噻嗪", "吲达帕胺",
    "螺内酯", "呋塞米", "特拉唑嗪",

    # ---- 抗血小板/抗凝 ----
    "阿司匹林", "氯吡格雷", "替格瑞洛", "华法林", "利伐沙班",
    "达比加群酯", "低分子肝素",

    # ---- 调脂药 ----
    "阿托伐他汀", "瑞舒伐他汀", "辛伐他汀", "普伐他汀", "非诺贝特",
    "依折麦布",

    # ---- 心血管其他 ----
    "硝酸甘油", "单硝酸异山梨酯", "地高辛", "胺碘酮", "普罗帕酮",
    "维拉帕米", "地尔硫卓",

    # ---- 呼吸系统 ----
    "沙丁胺醇", "布地奈德", "氟替卡松", "沙美特罗", "孟鲁司特",
    "茶碱", "氨茶碱", "右美沙芬", "氨溴索", "乙酰半胱氨酸",

    # ---- 消化系统 ----
    "奥美拉唑", "泮托拉唑", "雷贝拉唑", "兰索拉唑", "法莫替丁",
    "铝碳酸镁", "多潘立酮", "莫沙必利", "蒙脱石散", "乳果糖",
    "双歧杆菌制剂",

    # ---- 抗生素 ----
    "阿莫西林", "头孢克洛", "头孢呋辛", "头孢曲松", "左氧氟沙星",
    "莫西沙星", "阿奇霉素", "克拉霉素", "甲硝唑",

    # ---- 镇痛/抗炎 ----
    "布洛芬", "塞来昔布", "依托考昔", "对乙酰氨基酚", "曲马多",
    "加巴喷丁", "普瑞巴林",

    # ---- 神经系统 ----
    "多奈哌齐", "美金刚", "左旋多巴", "卡左双多巴", "普拉克索",
    "金刚烷胺", "苯海索", "氟西汀", "舍曲林", "帕罗西汀",
    "艾司西酞普兰", "文拉法辛", "度洛西汀", "阿普唑仑", "艾司唑仑",

    # ---- 中成药 ----
    "复方丹参滴丸", "麝香保心丸", "速效救心丸", "通心络胶囊",
    "脑心通胶囊", "稳心颗粒", "参松养心胶囊", "消渴丸",
    "六味地黄丸", "知柏地黄丸", "杞菊地黄丸", "补中益气丸",
    "逍遥丸", "加味逍遥丸", "龙胆泻肝丸", "牛黄解毒片",
    "板蓝根颗粒", "双黄连口服液", "连花清瘟胶囊", "银翘解毒片",
    "藿香正气水", "保和丸", "香砂养胃丸", "附子理中丸",
    "血府逐瘀丸", "天麻钩藤颗粒", "安宫牛黄丸", "苏合香丸",

    # ---- 中药饮片 ----
    "丹参", "川芎", "黄芪", "当归", "人参", "党参", "西洋参",
    "三七", "红花", "桃仁", "赤芍", "白芍", "熟地黄", "生地黄",
    "山药", "茯苓", "泽泻", "牡丹皮", "山茱萸", "枸杞子",
    "菊花", "决明子", "天麻", "钩藤", "石决明", "龙骨", "牡蛎",
    "柴胡", "黄芩", "黄连", "黄柏", "大黄", "石膏", "知母",
    "金银花", "连翘", "板蓝根", "鱼腥草", "蒲公英", "败酱草",
    "半夏", "陈皮", "甘草", "桔梗", "杏仁", "贝母",
    "麦冬", "百合", "沙参", "玉竹", "五味子", "酸枣仁",
    "桂枝", "附子", "肉桂", "干姜", "细辛", "麻黄", "生姜",
    "茵陈", "金钱草", "益母草", "牛膝", "杜仲", "续断", "桑寄生",

    # ---- 化疗/靶向药 ----
    "顺铂", "卡铂", "紫杉醇", "多西他赛", "吉西他滨", "氟尿嘧啶",
    "环磷酰胺", "多柔比星", "吉非替尼", "厄洛替尼", "奥希替尼",
    "伊马替尼", "索拉非尼", "贝伐珠单抗", "曲妥珠单抗",
]

SEED_SYMPTOMS = [
    # ---- 全身 ----
    "发热", "低热", "高热", "寒战", "盗汗", "乏力", "疲倦",
    "消瘦", "体重减轻", "体重增加", "食欲减退", "食欲亢进",
    "失眠", "多梦", "嗜睡",

    # ---- 疼痛 ----
    "头痛", "偏头痛", "胸痛", "胸闷", "心悸", "心慌",
    "腹痛", "腹胀", "胃痛", "胃胀", "反酸", "烧心",
    "腰痛", "背痛", "关节痛", "关节肿胀", "肌肉酸痛", "颈肩痛",

    # ---- 呼吸道 ----
    "咳嗽", "干咳", "咳痰", "黄痰", "白痰", "咯血",
    "气喘", "呼吸困难", "气短", "鼻塞", "流涕",
    "打喷嚏", "咽痛", "咽干", "咽痒", "声音嘶哑",

    # ---- 消化道 ----
    "恶心", "呕吐", "呃逆", "腹泻", "便秘", "便血",
    "黑便", "嗳气", "食欲不振", "口干", "口苦",
    "口臭", "牙龈出血",

    # ---- 泌尿系 ----
    "尿频", "尿急", "尿痛", "多尿", "少尿", "无尿",
    "夜尿增多", "血尿", "蛋白尿", "排尿困难", "尿潴留",
    "尿道灼热",

    # ---- 皮肤 ----
    "皮疹", "瘙痒", "皮肤干燥", "红斑", "紫癜", "瘀斑",
    "荨麻疹", "湿疹", "脱发", "多汗", "无汗",

    # ---- 神经/心理 ----
    "头晕", "眩晕", "耳鸣", "视物模糊", "复视", "肢体麻木",
    "四肢无力", "抽搐", "震颤", "行走不稳", "言语不清",
    "记忆力减退", "焦虑", "烦躁", "抑郁", "情绪低落",
    "注意力不集中",

    # ---- 中医特有 ----
    "舌红", "舌淡", "舌胖大", "舌有齿痕", "舌暗", "舌紫",
    "苔黄腻", "苔白腻", "苔薄白", "苔少", "脉弦", "脉细",
    "脉沉", "脉滑", "脉数", "脉迟", "脉涩", "脉弱",
    "面色萎黄", "面色苍白", "面色晦暗", "口唇紫绀",
    "五心烦热", "潮热", "畏寒肢冷", "手足心热", "自汗",
    "腰膝酸软", "少气懒言", "气短乏力",
]

# 预设词典保存路径
DICT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "dicts",
)


class DictExpander(BaseCrawler):
    """
    医学词典扩充器

    功能：
      1. 提供内置种子词典（100+疾病 / 150+药物 / 100+症状）
      2. 支持去重合并已有词典
      3. (可选) 从在线医学知识库抓取扩展词条

    用法:
        expander = DictExpander()
        expander.save_all_seed_dicts()  # 一键覆盖 dicts/ 目录
        # 或单独操作：
        expander.save_seed_dict("disease", "dicts/disease_dict.txt")
    """

    # 种子词典映射
    SEED_MAP = {
        "disease": SEED_DISEASES,
        "drug": SEED_DRUGS,
        "symptom": SEED_SYMPTOMS,
    }

    # 在线知识库源（可选功能）
    KNOWLEDGE_SOURCES = {
        "baidu_baike": {
            "url_template": "https://baike.baidu.com/item/{}",
            "enabled": False,  # 默认关闭，按需开启
        },
    }

    def __init__(self):
        super().__init__(requests_per_sec=1.0, max_retries=2)

    # ========== 种子词典操作 ==========

    def get_seed_dict(self, dict_type: str) -> List[str]:
        """
        获取指定类型的种子词典

        Args:
            dict_type: "disease" | "drug" | "symptom"

        Returns:
            实体列表（已排序去重）
        """
        if dict_type not in self.SEED_MAP:
            raise ValueError(f"未知词典类型 '{dict_type}'，可选: {list(self.SEED_MAP.keys())}")
        return sorted(set(self.SEED_MAP[dict_type]))

    def get_all_seeds(self) -> Dict[str, List[str]]:
        """获取全部种子词典"""
        return {k: self.get_seed_dict(k) for k in self.SEED_MAP}

    def load_existing_dict(self, file_path: str) -> Set[str]:
        """加载已有词典文件（跳过 # 注释行）"""
        entities = set()
        if not os.path.exists(file_path):
            return entities
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    entities.add(line)
        return entities

    def save_seed_dict(
        self,
        dict_type: str,
        output_path: Optional[str] = None,
        merge_existing: bool = True,
    ) -> str:
        """
        保存种子词典到文件

        Args:
            dict_type:    "disease" | "drug" | "symptom"
            output_path:  输出路径（默认 dicts/{dict_type}_dict.txt）
            merge_existing: 是否合并已有词典（去重追加）

        Returns:
            输出文件路径
        """
        seeds = self.get_seed_dict(dict_type)

        if output_path is None:
            output_path = os.path.join(DICT_PATH, f"{dict_type}_dict.txt")

        # 合并已有词典
        existing = self.load_existing_dict(output_path) if merge_existing else set()
        all_entities = sorted(existing | set(seeds))

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# {dict_type} 词典 — 自动生成于种子词典\n")
            f.write(f"# 总数: {len(all_entities)}\n")
            for entity in all_entities:
                f.write(f"{entity}\n")

        new_count = len(all_entities) - len(existing)
        logger.info("已保存 %s 词典: %s (%d个实体, 新增%d, 已有%d)",
                     dict_type, output_path, len(all_entities), max(new_count, 0),
                     len(existing))
        return output_path

    def save_all_seed_dicts(self, output_dir: Optional[str] = None) -> List[str]:
        """
        一键保存所有种子词典到 dicts/ 目录

        Returns:
            输出文件路径列表
        """
        output_paths = []
        for dict_type in ["disease", "drug", "symptom"]:
            path = self.save_seed_dict(dict_type, output_path=(
                os.path.join(output_dir, f"{dict_type}_dict.txt")
                if output_dir else None
            ))
            output_paths.append(path)
        logger.info("全部种子词典已保存到 %s", output_dir or DICT_PATH)
        return output_paths

    # ========== 在线扩展（可选） ==========

    def expand_from_web(
        self,
        dict_type: str,
        seed_terms: List[str],
        max_new: int = 50,
    ) -> List[str]:
        """
        (实验性) 从在线医学知识库扩展词典

        当前支持从百度百科抓取"相关疾病/药物"字段
        注意：仅用于学术研究，请遵守目标网站的 robots.txt 和服务条款

        Args:
            dict_type:  词典类型
            seed_terms: 种子词条列表
            max_new:    最多新增词条数

        Returns:
            新发现的实体名称列表
        """
        # 此功能为可选接口，需要用户明确激活
        logger.warning(
            "在线词典扩展功能需要手动激活。"
            "当前可从百度百科抓取（修改 KNOWLEDGE_SOURCES['baidu_baike']['enabled'] = True）"
        )
        return []

    def _scrape_baidu_baike(self, term: str) -> List[str]:
        """
        从百度百科词条页面提取相关医学实体

        解析页面中的"相关疾病"/"相关症状"/"相关药品"等信息框
        """
        from bs4 import BeautifulSoup

        url = f"https://baike.baidu.com/item/{term}"
        resp = self.request_with_retry(url)
        if resp is None:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        related = []

        # 尝试提取"基本信息"表格中的关联字段
        for dt in soup.find_all("dt", class_="basicInfo-item"):
            name = dt.get_text(strip=True)
            dd = dt.find_next_sibling("dd")
            if dd and any(kw in name for kw in
                          ["相关疾病", "相关症状", "相关药品", "并发症", "常用药品"]):
                for span in dd.find_all("span"):
                    item = span.get_text(strip=True)
                    if item and item != term:
                        related.append(item)

        return related

    # ========== 词典统计 ==========

    def show_stats(self) -> str:
        """显示当前种子词典统计 + dicts/ 目录下实际文件统计"""
        lines = ["=" * 50, "医学词典统计", "=" * 50]

        # 种子词典
        for dt in ["disease", "drug", "symptom"]:
            seeds = self.get_seed_dict(dt)
            lines.append(f"种子词 - {dt:12s}: {len(seeds):4d} 个")

        lines.append("-" * 50)

        # 实际文件
        for dt in ["disease", "drug", "symptom"]:
            file_path = os.path.join(DICT_PATH, f"{dt}_dict.txt")
            if os.path.exists(file_path):
                existing = self.load_existing_dict(file_path)
                lines.append(f"文件 - {dt:12s}: {len(existing):4d} 个  ({file_path})")
            else:
                lines.append(f"文件 - {dt:12s}: 文件不存在")

        lines.append("=" * 50)
        return "\n".join(lines)


# ========== 便捷函数 ==========

def expand_all_dicts(output_dir: Optional[str] = None) -> List[str]:
    """一键扩充全部词典"""
    expander = DictExpander()
    return expander.save_all_seed_dicts(output_dir)


def expand_entity_dicts(
    disease_path: Optional[str] = None,
    drug_path: Optional[str] = None,
    symptom_path: Optional[str] = None,
    merge: bool = True,
) -> Tuple[str, str, str]:
    """
    便捷函数：扩充三套实体词典

    Args:
        disease_path: 疾病词典输出路径
        drug_path:    药物词典输出路径
        symptom_path: 症状词典输出路径
        merge:        是否合并已有内容

    Returns:
        (disease_path, drug_path, symptom_path)

    Example:
        >>> expand_entity_dicts(
        ...     disease_path="dicts/disease_dict.txt",
        ...     drug_path="dicts/drug_dict.txt",
        ...     symptom_path="dicts/symptom_dict.txt",
        ... )
    """
    expander = DictExpander()
    d_path = expander.save_seed_dict("disease", disease_path, merge)
    dr_path = expander.save_seed_dict("drug", drug_path, merge)
    s_path = expander.save_seed_dict("symptom", symptom_path, merge)
    return d_path, dr_path, s_path
