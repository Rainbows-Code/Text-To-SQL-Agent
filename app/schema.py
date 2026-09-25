"""
Schema 元数据提取与管理模块：读取 schema_meta.json 并动态渲染 Schema 描述
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# 自动将项目根目录加入 sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.config import settings

class SchemaManager:
    """管理数据库 DDL、列注释、外键及业务口径元数据"""

    def __init__(self, meta_path: Optional[Path] = None):
        self.meta_path = meta_path or (settings.abs_db_path.parent / "schema_meta.json")
        self.data: Dict[str, Any] = self._load_meta()

    def _load_meta(self) -> Dict[str, Any]:
        """加载元数据文件"""
        if not self.meta_path.exists():
            raise FileNotFoundError(f"Schema 元数据文件不存在: {self.meta_path}")
        with open(self.meta_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_tables(self) -> List[Dict[str, Any]]:
        """获取所有表元数据"""
        return self.data.get("tables", [])

    def get_metrics(self) -> List[Dict[str, Any]]:
        """获取业务指标口径列表"""
        return self.data.get("metrics", [])

    def get_table_by_name(self, table_name: str) -> Optional[Dict[str, Any]]:
        """根据表名查找表描述"""
        for t in self.get_tables():
            if t["table_name"].lower() == table_name.lower():
                return t
        return None

    def format_full_schema_prompt(self) -> str:
        """格式化输出完整的 Schema Prompt 字符串（调试与对比用）"""
        lines = ["### 数据库 Schema 元数据：\n"]
        for t in self.get_tables():
            lines.append(f"表名: {t['table_name']} ({t['description']})")
            lines.append("字段列表:")
            for col in t["columns"]:
                pk_flag = " [主键]" if col.get("primary_key") else ""
                lines.append(f"  - {col['name']} ({col['type']}){pk_flag}: {col['description']}")
            if t.get("foreign_keys"):
                lines.append("外键关系:")
                for fk in t["foreign_keys"]:
                    lines.append(f"  - {fk['column']} -> {fk['referenced_table']}.{fk['referenced_column']}")
            lines.append("")

        lines.append("### 常见业务指标计算口径：")
        for m in self.get_metrics():
            lines.append(f"- 【{m['metric_name']}】: {m['definition']}")
            lines.append(f"  计算规则: {m['calculation_rule']}")

        return "\n".join(lines)

schema_manager = SchemaManager()
