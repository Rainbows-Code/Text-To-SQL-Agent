"""
SQL 安全校验与 AST 语法树工具层 (SQL Guard)
基于 sqlglot 实现 SQL 白名单拦截、自动 LIMIT 补全与高风险查询风险预警
"""
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# 自动加入系统路径
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import sqlglot
import sqlglot.expressions as exp

# 允许的默认最大行限制
DEFAULT_LIMIT = 100

# 不允许出现的 AST 禁用节点类型
FORBIDDEN_EXPRESSION_TYPES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.Command,
)

class SQLGuard:
    """SQL AST 安全防护网"""

    def validate_and_sanitize(
        self,
        sql: str,
        default_limit: int = DEFAULT_LIMIT
    ) -> Dict[str, Any]:
        """
        校验 SQL 安全性，拦截非 SELECT 语句，自动补全 LIMIT，识别高风险逻辑

        :param sql: 待校验的原始 SQL
        :param default_limit: 缺省 LIMIT 限制行数
        :return: {
            "is_safe": bool,
            "sanitized_sql": str,
            "reason": str or None,
            "needs_confirmation": bool,
            "risk_warnings": List[str]
        }
        """
        if not sql or not sql.strip():
            return {
                "is_safe": False,
                "sanitized_sql": "",
                "reason": "SQL 语句为空",
                "needs_confirmation": False,
                "risk_warnings": []
            }

        clean_sql = sql.strip().rstrip(";")

        # 1. 语法解析：检查是否合法 SQLite 语法
        try:
            statements = sqlglot.parse(clean_sql, read="sqlite")
        except Exception as e:
            return {
                "is_safe": False,
                "sanitized_sql": clean_sql,
                "reason": f"SQL 语法树解析失败 (Syntax Error): {str(e)}",
                "needs_confirmation": False,
                "risk_warnings": []
            }

        # 2. 拦截多语句拼接注入（只允许单条 SQL 语句）
        valid_statements = [s for s in statements if s is not None]
        if len(valid_statements) > 1:
            return {
                "is_safe": False,
                "sanitized_sql": clean_sql,
                "reason": "安全防御拦截：禁止拼接多条 SQL 语句分号执行",
                "needs_confirmation": False,
                "risk_warnings": []
            }

        ast = valid_statements[0]

        # 3. 校验 AST 白名单：必须是 SELECT 语句，禁止写入/修改/建表删表
        if not isinstance(ast, (exp.Select, exp.Union)):
            return {
                "is_safe": False,
                "sanitized_sql": clean_sql,
                "reason": f"安全防御拦截：只允许查询操作 (SELECT)，禁止执行 [{ast.key.upper()}] 语句",
                "needs_confirmation": False,
                "risk_warnings": []
            }

        # 深度扫描 AST，确保不存在任何违规修改节点
        for forbidden_type in FORBIDDEN_EXPRESSION_TYPES:
            if list(ast.find_all(forbidden_type)):
                return {
                    "is_safe": False,
                    "sanitized_sql": clean_sql,
                    "reason": f"安全防御拦截：发现高危语法节点 [{forbidden_type.__name__}]",
                    "needs_confirmation": False,
                    "risk_warnings": []
                }

        # 4. 高风险查询检测
        risk_warnings, needs_confirmation = self._analyze_query_risks(ast)

        # 5. 自动 LIMIT 补全
        sanitized_ast = self._apply_auto_limit(ast, default_limit)
        sanitized_sql = sanitized_ast.sql("sqlite")

        return {
            "is_safe": True,
            "sanitized_sql": sanitized_sql,
            "reason": None,
            "needs_confirmation": needs_confirmation,
            "risk_warnings": risk_warnings
        }

    def _apply_auto_limit(self, ast: exp.Expression, limit: int) -> exp.Expression:
        """若查询缺少 LIMIT，使用 AST 动态增补 LIMIT"""
        if isinstance(ast, exp.Select):
            if ast.args.get("limit") is None:
                # 给 AST 动态加上 limit 限制
                ast = ast.limit(limit)
        return ast

    def _analyze_query_risks(self, ast: exp.Expression) -> Tuple[List[str], bool]:
        """识别潜在的高风险查询（缺失 WHERE 条件、全表扫描、笛卡尔积等）"""
        warnings = []
        needs_confirmation = False

        if isinstance(ast, exp.Select):
            # 1. 检查大表全表扫描风险 (orders, order_items 缺 WHERE 条件)
            from_tables = [table.name.lower() for table in ast.find_all(exp.Table)]
            has_where = ast.args.get("where") is not None

            fact_tables = {"orders", "order_items"}
            if fact_tables.intersection(set(from_tables)) and not has_where:
                warnings.append("高风险提示：针对大型事实表 (orders/order_items) 的全表查询，未包含 WHERE 过滤条件")
                needs_confirmation = True

            # 2. 检查笛卡尔积风险（多表关联且缺失 JOIN / WHERE 关联条件）
            joins = list(ast.find_all(exp.Join))
            if len(from_tables) > 1 and not joins and not has_where:
                warnings.append("高风险提示：存在多表交叉查询且未发现明确连接条件，可能有笛卡尔积爆炸风险")
                needs_confirmation = True

        return warnings, needs_confirmation

sql_guard = SQLGuard()
