from src.database.models.asset import Asset
from src.database.models.audit import AuditRecord
from src.database.models.job import JobRecord
from src.database.models.project import Project
from src.database.models.qa import QAResult
from src.database.models.repair import RepairPlan
from src.database.models.shot import Shot
from src.database.models.shot_version import ShotVersion
from src.database.models.video_generation import VideoGeneration
from src.database.models.world_state import WorldStateRecord
from src.database.models.human_gate import HumanGate
from src.database.models.gpu_job import GpuJob

# Backward-compatible name expected by existing tests/importers.
Job = JobRecord

__all__ = [
    "Asset",
    "AuditRecord",
    "Job",
    "JobRecord",
    "Project",
    "QAResult",
    "RepairPlan",
    "Shot",
    "ShotVersion",
    "VideoGeneration",
    "WorldStateRecord",
    "HumanGate",
    "GpuJob",
]
