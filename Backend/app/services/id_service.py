"""分布式 ID 生成工具。

在任务、段落、产物、风险记录等实体创建时生成带前缀的短唯一标识。
"""

from uuid import uuid4


def create_id(prefix: str) -> str:
    """生成带业务前缀的短唯一 ID。

    用途：
        为各类数据库主键或业务实体提供可读且唯一的字符串 ID。

    参数：
        prefix: 业务前缀，如 task、seg、artifact，便于日志与排查。

    返回：
        形如 ``{prefix}_{8位hex}`` 的字符串。

    逻辑：
        截取 uuid4 十六进制串的前 8 位，与前缀拼接，兼顾唯一性与长度。
    """
    return f"{prefix}_{uuid4().hex[:8]}"
