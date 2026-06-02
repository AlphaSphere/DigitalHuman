"""
用途：应用级日志初始化，在进程启动时统一格式与级别，便于容器与本地排查。
"""

import logging


def configure_logging() -> None:
    """
    用途：配置根 logger 的级别与输出格式，应在 create_app 最早阶段调用一次。

    逻辑：
        1. 使用 INFO 级别与带时间、级别、logger 名的行格式，适配标准输出采集
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
