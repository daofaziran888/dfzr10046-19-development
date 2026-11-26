"""业务路由汇总：争议定位等固定路径先注册，通用资源路由最后兜底。"""
from __future__ import annotations

from app.routers import dispute, resource

ROUTERS = [dispute, resource]
