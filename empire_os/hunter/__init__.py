"""Empire Hunter — native commercial identity and contact intelligence."""

from empire_os.hunter.domain_intelligence import analyze_domain
from empire_os.hunter.evidence_graph import build_evidence_plan
from empire_os.hunter.materializer import SupabaseHunterMaterializer
from empire_os.hunter.models import ContactEvidence, DomainPattern, VerificationState
from empire_os.hunter.pattern_brain import (
    generate_candidate,
    infer_pattern,
    learn_domain_pattern,
)
from empire_os.hunter.verification_mesh import VerificationMesh

__all__ = [
    "ContactEvidence",
    "DomainPattern",
    "VerificationState",
    "VerificationMesh",
    "SupabaseHunterMaterializer",
    "analyze_domain",
    "build_evidence_plan",
    "generate_candidate",
    "infer_pattern",
    "learn_domain_pattern",
]
