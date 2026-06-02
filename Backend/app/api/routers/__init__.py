"""HTTP API 路由模块包。

各 router 按领域拆分，映射到 services 层；
整体流程：任务 → 段落/风险 → 生成配置 → Celery → 产物 → 分发。
"""
