"""领域服务注册表：通用资源路由按模块 key 分派到独立业务服务。"""
from __future__ import annotations

from app.services.base import BaseModuleService
from app.services.dim_entry import DimEntryService
from app.services.scd_chain import ScdChainService
from app.services.surrogate_key import SurrogateKeyService
from app.services.conform_check import ConformCheckService
from app.services.fact_assemble import FactAssembleService
from app.services.degenerate_dim import DegenerateDimService
from app.services.late_fact import LateFactService
from app.services.summary_layer import SummaryLayerService
from app.services.grain_declare import GrainDeclareService
from app.services.measure_catalog import MeasureCatalogService
from app.services.metric_bind import MetricBindService
from app.services.dim_snapshot import DimSnapshotService
from app.services.hier_path import HierPathService
from app.services.bridge_link import BridgeLinkService
from app.services.attr_decay import AttrDecayService
from app.services.load_window import LoadWindowService
from app.services.reprocess_task import ReprocessTaskService
from app.services.quality_gate import QualityGateService
from app.services.lineage_edge import LineageEdgeService
from app.services.dim_publish import DimPublishService
from app.services.model_audit import ModelAuditService
from app.services.src_extract import SrcExtractService
from app.services.dispute_service import SummaryReturnService, DisputeLocatorModuleService

SERVICES: dict[str, BaseModuleService] = {
    "dim_entry": DimEntryService(),
    "scd_chain": ScdChainService(),
    "surrogate_key": SurrogateKeyService(),
    "conform_check": ConformCheckService(),
    "fact_assemble": FactAssembleService(),
    "degenerate_dim": DegenerateDimService(),
    "late_fact": LateFactService(),
    "summary_layer": SummaryLayerService(),
    "grain_declare": GrainDeclareService(),
    "measure_catalog": MeasureCatalogService(),
    "metric_bind": MetricBindService(),
    "dim_snapshot": DimSnapshotService(),
    "hier_path": HierPathService(),
    "bridge_link": BridgeLinkService(),
    "attr_decay": AttrDecayService(),
    "load_window": LoadWindowService(),
    "reprocess_task": ReprocessTaskService(),
    "quality_gate": QualityGateService(),
    "lineage_edge": LineageEdgeService(),
    "dim_publish": DimPublishService(),
    "model_audit": ModelAuditService(),
    "src_extract": SrcExtractService(),
    # 汇总退件/处置清单：主模块名 + 常见命名别名，共用同一份内存表。
    "summary_return": SummaryReturnService(),
    "summary_returns": SummaryReturnService(),
    "return_order": SummaryReturnService(),
    "dispute_case": SummaryReturnService(),
    "dispute_locator": DisputeLocatorModuleService(),
    "dispute": DisputeLocatorModuleService(),
}


def service_for(module: str) -> BaseModuleService | None:
    return SERVICES.get(module)
