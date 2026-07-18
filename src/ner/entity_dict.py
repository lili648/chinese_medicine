# -*- coding: utf-8 -*-
"""
实体词典管理器
类: EntityDict - 疾病/药物/症状词典管理
对应需求: FR-03
"""
from typing import Set, Dict, Optional
import os


class EntityDict:
    """实体词典管理器"""

    def __init__(self):
        self.disease_set: Set[str] = set()
        self.drug_set: Set[str] = set()
        self.symptom_set: Set[str] = set()
        self.name_to_type: Dict[str, str] = {}

    def load_dicts(self, dict_dir: str) -> None:
        """从目录加载三类词典文件"""
        dict_map = {
            "disease_dict.txt": ("Disease", "disease_set"),
            "drug_dict.txt": ("Drug", "drug_set"),
            "symptom_dict.txt": ("Symptom", "symptom_set"),
        }
        for filename, (entity_type, attr_name) in dict_map.items():
            file_path = os.path.join(dict_dir, filename)
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    names = {line.strip() for line in f if line.strip()}
                    getattr(self, attr_name).update(names)
                    for name in names:
                        self.name_to_type[name] = entity_type

    def lookup(self, name: str) -> Optional[str]:
        """查实体名返回类型"""
        return self.name_to_type.get(name)

    def get_stats(self) -> Dict:
        """返回词典统计信息"""
        return {
            "Disease": len(self.disease_set),
            "Drug": len(self.drug_set),
            "Symptom": len(self.symptom_set),
            "Total": len(self.name_to_type),
        }
