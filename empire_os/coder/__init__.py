"""Empire Coder — governed developer intelligence for EmpireOS."""

from .context import ContextBuilder, ContextPack
from .jobs import CoderJob, JobKind, JobStatus, LocalJobQueue
from .models import (
    CoderTask,
    TaskPhase,
    TaskStatus,
    ToolDecision,
    VerificationVerdict,
)
from .ollama_provider import OllamaProvider
from .orchestrator import EmpireCoder, EmpireCoderError
from .permissions import (
    OBSERVE_DEVELOPER,
    REVIEW_ONLY,
    Capability,
    PermissionProfile,
)
from .refinement import (
    ModelProposal, OutputRefiner, ProposalStage, RefinementPolicy,
)
from .repo import RepoIntelligence
from .router import ModelProfile, ModelRouter
from .verifier import Verifier
from .worker import CoderTaskWorker

__all__ = [
    "Capability",
    "CoderJob",
    "CoderTaskWorker",
    "JobKind",
    "JobStatus",
    "LocalJobQueue",
    "CoderTask",
    "ContextBuilder",
    "ContextPack",
    "EmpireCoder",
    "EmpireCoderError",
    "ModelProfile",
    "ModelRouter",
    "RefinementPolicy",
    "ProposalStage",
    "OutputRefiner",
    "ModelProposal",
    "OBSERVE_DEVELOPER",
    "OllamaProvider",
    "PermissionProfile",
    "REVIEW_ONLY",
    "RepoIntelligence",
    "TaskPhase",
    "TaskStatus",
    "ToolDecision",
    "VerificationVerdict",
    "Verifier",
]
