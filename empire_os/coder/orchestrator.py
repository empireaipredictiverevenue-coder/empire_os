"""Empire Coder governed engineering orchestrator."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .ast_patch import AstPatchEngine
from .audit import AuditTrail
from .benchmark import BenchmarkHarness
from .command_proposal import CommandProposal, CommandRefiner
from .context import ContextBuilder, ContextPack
from .dependencies import DependencyIndex
from .knowledge_garden import KnowledgeGarden
from .memory import ContextMemory
from .model_review import DistinctModelReviewer, ModelReview
from .models import (
    CoderTask,
    ModelRoute,
    TaskPhase,
    TaskStatus,
    ToolRunResult,
    VerificationReport,
    VerificationVerdict,
)
from .ollama_provider import OllamaProvider
from .patch import PatchEngine
from .permissions import (
    Capability,
    OBSERVE_DEVELOPER,
    PermissionProfile,
)
from .plan import PlanStep, TaskPlan
from .provider import (
    DisabledProvider,
    ModelRequest,
    ModelResponse,
    ProviderRegistry,
)
from .refinement import ModelProposal, OutputRefiner
from .repo import RepoIntelligence
from .roles import ROLES
from .router import ModelProfile, ModelRouter
from .runner import SafeCommandRunner
from .self_build import validate_self_build_scope
from .skills import SkillLoader
from .state import LocalTaskStore, compact_task_context
from .structured_patch import (
    PatchOperation,
    StructuredPatchCandidate,
    StructuredPatchError,
    StructuredPatchRefiner,
    StructuredPatchValidator,
)
from .verifier import Verifier
from .worktree import WorktreeController


class EmpireCoderError(RuntimeError):
    pass


def default_task_plan() -> TaskPlan:
    plan = TaskPlan([
        PlanStep("understand", "Understand objective", TaskPhase.UNDERSTAND),
        PlanStep(
            "search_repo", "Retrieve relevant repository context",
            TaskPhase.SEARCH_REPO, ("understand",),
        ),
        PlanStep(
            "plan", "Create implementation plan",
            TaskPhase.PLAN, ("search_repo",),
        ),
        PlanStep(
            "patch", "Apply targeted patch",
            TaskPhase.PATCH, ("plan",),
        ),
        PlanStep(
            "test", "Run focused validation",
            TaskPhase.TEST, ("patch",),
        ),
        PlanStep(
            "verify", "Independent verifier review",
            TaskPhase.VERIFY, ("test",),
        ),
        PlanStep(
            "diff", "Review final candidate diff",
            TaskPhase.DIFF, ("verify",),
        ),
        PlanStep(
            "approval", "Await human approval",
            TaskPhase.APPROVAL, ("diff",),
        ),
    ])
    plan.validate()
    return plan


class EmpireCoder:
    def __init__(
        self,
        workspace: str | Path,
        *,
        runtime_root: str | Path | None = None,
        permission_profile: PermissionProfile = OBSERVE_DEVELOPER,
        model_profiles: Iterable[ModelProfile] = (),
    ) -> None:
        self.workspace = Path(workspace).expanduser().resolve()
        self.runtime_root = Path(
            runtime_root or self.workspace / "runtime" / "coder"
        ).resolve()
        self.permissions = permission_profile
        self.store = LocalTaskStore(
            self.workspace, self.runtime_root
        )
        self.repo = RepoIntelligence(self.workspace)
        self.knowledge = KnowledgeGarden(
            self.workspace,
            runtime_root=self.runtime_root,
        )
        self._knowledge_report = None
        self.context = ContextBuilder(self.repo)
        self.runner = SafeCommandRunner(
            self.workspace, runtime_root=self.runtime_root
        )
        self.patch = PatchEngine(
            self.workspace, runtime_root=self.runtime_root
        )
        self.ast_patch = AstPatchEngine(self.patch)
        self.structured_patch_validator = StructuredPatchValidator(
            self.workspace
        )
        self.dependencies = DependencyIndex(self.repo)
        self.verifier = Verifier(self.workspace)
        requested_profiles = tuple(model_profiles)
        self.providers = ProviderRegistry()
        self.providers.register(DisabledProvider())
        ollama = OllamaProvider(num_threads=8)
        local_model = "qwen3-coder:30b"
        if ollama.health() and ollama.has_model(local_model):
            self.providers.register(ollama)
            if not requested_profiles:
                requested_profiles = (
                    ModelProfile(
                        "ollama",
                        local_model,
                        capability=3,
                        cost_tier=0,
                        local=True,
                        roles=("writer",),
                    ),
                )
        self.router = ModelRouter(requested_profiles)
        self.skills = SkillLoader(self.workspace)
        self.audit = AuditTrail(self.runtime_root)
        self.memory = ContextMemory(self.store, self.audit)
        self.benchmarks = BenchmarkHarness(self.runner)
        self.worktrees = WorktreeController(self.workspace)

    def refresh_knowledge(self) -> dict:
        report = self.knowledge.scan()
        self._knowledge_report = report
        active_paths = self.knowledge.active_paths(report)
        self.context.set_active_knowledge_paths(active_paths)
        self.skills.set_active_knowledge_paths(active_paths)
        manifest = self.knowledge.sync_manifest()
        return {
            "scanned": report.scanned,
            "active": report.active,
            "review": report.review,
            "quarantined": report.quarantined,
            "manifest_active": len(manifest["active"]),
        }

    def _git_state_for_memory(self) -> dict:
        try:
            state = self.worktrees.inspect()
            return {
                "branch": state.branch,
                "head": state.head,
                "dirty": state.dirty,
                "status": state.status[-4000:],
            }
        except Exception as exc:
            return {"error": exc.__class__.__name__}

    def _sync_context(self, task_id: str, trigger: str) -> dict:
        return self.memory.refresh(
            task_id,
            trigger=trigger,
            git_state=self._git_state_for_memory(),
        )

    def _record_and_sync(
        self,
        *,
        task_id: str,
        event: str,
        data: dict | None = None,
    ) -> dict:
        self.audit.record(
            task_id=task_id,
            event=event,
            data=data or {},
        )
        return self._sync_context(task_id, event)

    def _fresh_context_pack(
        self,
        task_id: str,
        context: ContextPack,
        *,
        trigger: str,
    ) -> ContextPack:
        self._sync_context(task_id, trigger)
        model_state = self.memory.model_view(task_id)
        return ContextPack(
            objective=context.objective,
            task_state=model_state,
            documents=context.documents,
            symbols=context.symbols,
            token_budget_chars=context.token_budget_chars,
        )

    def create_task(
        self,
        objective: str,
        *,
        blueprint_path: str = "docs/BLUEPRINT_V6.md",
    ) -> CoderTask:
        task = self.store.create(
            objective,
            blueprint_path=blueprint_path,
        )
        plan = default_task_plan()
        task.plan = [step.name for step in plan.steps]
        task.plan_steps = [step.as_dict() for step in plan.steps]
        task.status = TaskStatus.RUNNING
        task.phase = TaskPhase.UNDERSTAND
        self.store.save(task)
        knowledge = self.refresh_knowledge()
        self._record_and_sync(
            task_id=task.id,
            event="task_created",
            data={
                "objective": task.objective,
                "knowledge": knowledge,
            },
        )
        return task

    def load_task(self, task_id: str) -> CoderTask:
        return self.store.load(task_id)

    def build_context(
        self,
        task_id: str,
        *,
        terms: Iterable[str] = (),
        symbols: Iterable[str] = (),
        budget_chars: int = 24_000,
    ) -> ContextPack:
        self._require(Capability.SEARCH_REPO)
        task = self.store.load(task_id)
        knowledge = self.refresh_knowledge()
        report = self._knowledge_report or self.knowledge.scan()
        task_active_paths = self.knowledge.active_paths_for_task(
            task.id,
            report,
        )
        self.context.set_active_knowledge_paths(task_active_paths)
        self.skills.set_active_knowledge_paths(task_active_paths)
        promotion = self.knowledge.task_promotion_status(task.id)
        knowledge = {
            **knowledge,
            "task_active": len(task_active_paths),
            "task_promoted": promotion["promoted"],
        }
        pack = self.context.build(
            task,
            terms=terms,
            symbol_terms=symbols,
            budget_chars=budget_chars,
        )
        discovered = [
            item.path for item in pack.documents
            if item.path not in task.discovered_files
        ]
        task.discovered_files.extend(discovered)
        task.phase = TaskPhase.SEARCH_REPO
        self.store.save(task)
        self._record_and_sync(
            task_id=task.id,
            event="context_built",
            data={
                "documents": [item.path for item in pack.documents],
                "symbols": list(pack.symbols),
                "knowledge": knowledge,
            },
        )
        return self._fresh_context_pack(
            task.id,
            pack,
            trigger="context_ready",
        )

    def promote_task_knowledge(
        self,
        task_id: str,
        paths: Iterable[str],
        *,
        reason: str,
        approved: bool = False,
    ) -> dict:
        self.store.load(task_id)
        payload = self.knowledge.promote_for_task(
            task_id,
            paths,
            reason=reason,
            approved=approved,
        )
        status = self.knowledge.task_promotion_status(task_id)
        self._record_and_sync(
            task_id=task_id,
            event="task_knowledge_promoted",
            data={
                "promoted": status["promoted"],
                "paths": [
                    entry["path"]
                    for entry in payload.get("entries") or []
                ],
            },
        )
        return status

    def read_for_patch(self, task_id: str, path: str) -> str:
        self._require(Capability.READ_REPO)
        text = self.patch.read(path)
        self._record_and_sync(
            task_id=task_id,
            event="file_read_for_patch",
            data={"path": path},
        )
        return text

    def patch_exact(
        self,
        task_id: str,
        path: str,
        old: str,
        new: str,
        *,
        expected_count: int = 1,
    ) -> dict[str, str]:
        self._require(Capability.CREATE_PATCH)
        task = self.store.load(task_id)
        result = self.patch.replace_exact(
            task_id,
            path,
            old,
            new,
            expected_count=expected_count,
        )
        task.phase = TaskPhase.PATCH
        self.store.save(task)
        self._record_and_sync(
            task_id=task_id,
            event="patch_applied",
            data=result,
        )
        return result

    def patch_python_symbol(
        self,
        task_id: str,
        path: str,
        symbol_name: str,
        replacement: str,
    ) -> dict[str, str]:
        self._require(Capability.CREATE_PATCH)
        task = self.store.load(task_id)
        result = self.ast_patch.replace_python_symbol(
            task_id,
            path,
            symbol_name,
            replacement,
        )
        task.phase = TaskPhase.PATCH
        self.store.save(task)
        self._record_and_sync(
            task_id=task_id,
            event="symbol_patch_applied",
            data={
                **result,
                "symbol": symbol_name,
            },
        )
        return result

    def propose_structured_patch(
        self,
        task_id: str,
        objective: str,
        context: ContextPack,
    ) -> StructuredPatchCandidate:
        self.refresh_knowledge()
        route = self.model_route(task_id)
        provider = self.providers.get(route.provider)
        context = self._fresh_context_pack(
            task_id,
            context,
            trigger="before_structured_patch_refinement",
        )
        candidate = StructuredPatchRefiner(
            provider,
            self.structured_patch_validator,
        ).propose(
            task_id=task_id,
            objective=objective,
            context=context,
            route=route,
        )
        proposal = candidate.proposal
        self.store.save_structured_patch_proposal(
            task_id,
            {
                "task_id": task_id,
                "provider": route.provider,
                "model": route.model,
                "candidate_texts": list(candidate.candidate_texts),
                "candidate_count": len(candidate.candidate_texts),
                "critique": candidate.critique,
                "synthesized_text": candidate.synthesized_text,
                **proposal.as_dict(),
                "valid": candidate.validation.valid,
                "validation_reasons": list(
                    candidate.validation.reasons
                ),
                "validation_warnings": list(
                    candidate.validation.warnings
                ),
                "eligible": candidate.eligible,
            },
        )
        self._record_and_sync(
            task_id=task_id,
            event="structured_patch_refined",
            data={
                "provider": route.provider,
                "model": route.model,
                "candidate_count": len(candidate.candidate_texts),
                "path": proposal.target_path,
                "symbol": proposal.symbol,
                "valid": candidate.validation.valid,
                "eligible": candidate.eligible,
            },
        )
        return candidate

    def apply_structured_patch(
        self,
        task_id: str,
        candidate: StructuredPatchCandidate,
    ) -> dict:
        self._require(Capability.CREATE_PATCH)
        if not candidate.eligible:
            raise EmpireCoderError(
                "structured patch has not passed best-of-N and validation"
            )

        live_validation = self.structured_patch_validator.validate(
            candidate.proposal
        )
        if not live_validation.valid:
            raise EmpireCoderError(
                "structured patch no longer matches live repository: "
                + "; ".join(live_validation.reasons)
            )

        proposal = candidate.proposal
        if proposal.operation is PatchOperation.REPLACE_EXACT:
            self.read_for_patch(task_id, proposal.target_path)
            result = self.patch_exact(
                task_id,
                proposal.target_path,
                proposal.old_text or "",
                proposal.new_text,
            )
        elif (
            proposal.operation
            is PatchOperation.REPLACE_PYTHON_SYMBOL
        ):
            result = self.patch_python_symbol(
                task_id,
                proposal.target_path,
                proposal.symbol or "",
                proposal.new_text,
            )
        elif proposal.operation is PatchOperation.CREATE_FILE:
            result = self.patch.create_file(
                task_id,
                proposal.target_path,
                proposal.new_text,
            )
            task = self.store.load(task_id)
            task.phase = TaskPhase.PATCH
            self.store.save(task)
        else:
            raise EmpireCoderError(
                f"unsupported structured patch operation: "
                f"{proposal.operation.value}"
            )

        task = self.store.load(task_id)
        for test_path in proposal.expected_tests:
            if test_path not in task.tests_required:
                task.tests_required.append(test_path)
        self.store.save(task)
        self._record_and_sync(
            task_id=task_id,
            event="structured_patch_applied",
            data={
                **result,
                "operation": proposal.operation.value,
                "symbol": proposal.symbol,
                "expected_tests": list(proposal.expected_tests),
            },
        )
        return result

    def impacted_tests(
        self,
        changed_files: Iterable[str],
    ) -> tuple[str, ...]:
        self.dependencies.build()
        return tuple(self.dependencies.impacted_tests(changed_files))

    def specialist_roles(self) -> dict[str, dict]:
        return {
            name: {
                "mission": role.mission,
                "permission_profile": role.permission_profile.name,
                "can_patch": role.can_patch,
                "can_verify": role.can_verify,
                "required_outputs": list(role.required_outputs),
            }
            for name, role in ROLES.items()
        }

    def run_tool(
        self,
        task_id: str,
        argv: Iterable[str],
        *,
        timeout: int = 120,
        approved: bool = False,
    ) -> ToolRunResult:
        self._require(Capability.RUN_SAFE_COMMAND)
        result = self.runner.run(
            tuple(argv),
            task_id=task_id,
            timeout=timeout,
            approved=approved,
        )
        self._record_and_sync(
            task_id=task_id,
            event="tool_run",
            data=result.as_dict(),
        )
        return result

    def model_route(self, task_id: str) -> ModelRoute:
        task = self.store.load(task_id)
        route = self.router.route(
            task.objective,
            role="writer",
        )
        self._record_and_sync(
            task_id=task_id,
            event="model_routed",
            data={
                "provider": route.provider,
                "model": route.model,
                "reason": route.reason,
            },
        )
        return route

    def verifier_model_route(
        self,
        task_id: str,
    ) -> ModelRoute:
        task = self.store.load(task_id)
        writer = self.router.route(
            task.objective,
            role="writer",
        )
        route = self.router.route(
            task.objective,
            role="verifier",
            exclude=((writer.provider, writer.model),),
        )
        self._record_and_sync(
            task_id=task_id,
            event="verifier_model_routed",
            data={
                "provider": route.provider,
                "model": route.model,
                "reason": route.reason,
                "writer_provider": writer.provider,
                "writer_model": writer.model,
                "distinct": (
                    (route.provider, route.model)
                    != (writer.provider, writer.model)
                    and route.provider != "unconfigured"
                ),
            },
        )
        return route

    def advisory_model_review(
        self,
        task_id: str,
        *,
        changed_files: Iterable[str],
        context: ContextPack,
        diff_excerpt: str,
    ) -> ModelReview | None:
        """Run a distinct-model advisory review if configured.

        Deterministic verifier results remain authoritative.
        """
        route = self.verifier_model_route(task_id)
        if route.provider == "unconfigured":
            self._record_and_sync(
                task_id=task_id,
                event="advisory_model_review_unavailable",
                data={"reason": route.reason},
            )
            return None

        provider = self.providers.get(route.provider)
        context = self._fresh_context_pack(
            task_id,
            context,
            trigger="before_advisory_model_review",
        )
        task = self.store.load(task_id)
        review = DistinctModelReviewer(provider).review(
            task_id=task_id,
            objective=task.objective,
            context=context,
            route=route,
            changed_files=tuple(dict.fromkeys(changed_files)),
            diff_excerpt=diff_excerpt,
        )
        self._record_and_sync(
            task_id=task_id,
            event="advisory_model_review_completed",
            data=review.as_dict(),
        )
        return review

    def ask_model(
        self,
        task_id: str,
        instruction: str,
        context: ContextPack,
        *,
        max_output_chars: int = 6_000,
    ) -> ModelResponse:
        """Return a raw DRAFT_ONLY response.

        Raw model output is never actionable. Automated engineering flows must
        use polished_model_output(), which enforces critique + refinement.
        """
        self.refresh_knowledge()
        route = self.model_route(task_id)
        provider = self.providers.get(route.provider)
        context = self._fresh_context_pack(
            task_id,
            context,
            trigger="before_model_call",
        )
        response = provider.complete(ModelRequest(
            task_id=task_id,
            instruction=instruction,
            context=context,
            route=route,
            max_output_chars=max(
                256, min(int(max_output_chars), 12_000)
            ),
        ))
        self._record_and_sync(
            task_id=task_id,
            event="model_response_draft",
            data={
                "provider": response.provider,
                "model": response.model,
                "error": response.error,
                "output_chars": len(response.text),
            },
        )
        return response

    def polished_model_output(
        self,
        task_id: str,
        instruction: str,
        context: ContextPack,
        *,
        max_output_chars: int = 4_000,
    ) -> ModelProposal:
        self.refresh_knowledge()
        route = self.model_route(task_id)
        provider = self.providers.get(route.provider)
        context = self._fresh_context_pack(
            task_id,
            context,
            trigger="before_refined_model_call",
        )
        proposal = OutputRefiner(provider).polished(
            task_id=task_id,
            instruction=instruction,
            context=context,
            route=route,
            max_output_chars=max(
                256, min(int(max_output_chars), 8_000)
            ),
        )
        self.store.save_proposal(
            task_id,
            {
                "task_id": proposal.task_id,
                "provider": route.provider,
                "model": route.model,
                "stage": proposal.stage.value,
                "draft": proposal.draft,
                "candidate_drafts": list(proposal.candidate_drafts),
                "critique": proposal.critique,
                "refined": proposal.refined,
                "revision_count": proposal.revision_count,
                "actionable": proposal.actionable,
            },
        )
        self._record_and_sync(
            task_id=task_id,
            event="model_output_refined",
            data={
                "provider": route.provider,
                "model": route.model,
                "revision_count": proposal.revision_count,
                "candidate_count": len(proposal.candidate_drafts),
                "draft_chars": len(proposal.draft),
                "critique_chars": len(proposal.critique),
                "refined_chars": len(proposal.refined),
                "actionable": proposal.actionable,
            },
        )
        return proposal

    def propose_next_command(
        self,
        task_id: str,
        objective: str,
        context: ContextPack,
    ) -> CommandProposal:
        self.refresh_knowledge()
        route = self.model_route(task_id)
        provider = self.providers.get(route.provider)
        context = self._fresh_context_pack(
            task_id,
            context,
            trigger="before_command_refinement",
        )
        proposal = CommandRefiner(provider).propose(
            task_id=task_id,
            objective=objective,
            context=context,
            route=route,
        )
        self.store.save_command_proposal(
            task_id,
            {
                "task_id": task_id,
                "provider": route.provider,
                "model": route.model,
                "candidate_texts": list(proposal.candidate_texts),
                "critique": proposal.critique,
                "synthesized_text": proposal.synthesized_text,
                "argv": list(proposal.argv),
                "decision": proposal.decision.value,
                "stage": proposal.stage.value,
                "eligible": proposal.eligible,
            },
        )
        self._record_and_sync(
            task_id=task_id,
            event="next_command_refined",
            data={
                "provider": route.provider,
                "model": route.model,
                "candidate_count": len(proposal.candidate_texts),
                "argv": list(proposal.argv),
                "decision": proposal.decision.value,
                "eligible": proposal.eligible,
            },
        )
        return proposal

    def run_command_proposal(
        self,
        proposal: CommandProposal,
        *,
        timeout: int = 120,
        approved: bool = False,
    ) -> ToolRunResult:
        if not proposal.eligible:
            raise EmpireCoderError(
                "command proposal has not passed best-of-N and policy checks"
            )
        return self.run_tool(
            proposal.task_id,
            proposal.argv,
            timeout=timeout,
            approved=approved,
        )

    def verify(
        self,
        task_id: str,
        *,
        changed_files: Iterable[str],
        commands: Iterable[Iterable[str]] = (),
        self_build: bool = False,
    ) -> VerificationReport:
        self._require(Capability.RUN_TESTS)
        files = tuple(dict.fromkeys(changed_files))
        if self_build:
            validate_self_build_scope(files)
        task = self.store.load(task_id)
        task.status = TaskStatus.VERIFYING
        task.phase = TaskPhase.VERIFY
        self.store.save(task)
        report = self.verifier.verify(
            task_id=task_id,
            changed_files=files,
            commands=commands,
        )
        task.verification_status = report.verdict
        if report.verdict is VerificationVerdict.FAIL:
            task.status = TaskStatus.BLOCKED
            task.phase = TaskPhase.REPAIR
            task.unresolved_issues.extend(report.reasons)
        else:
            task.status = TaskStatus.AWAITING_APPROVAL
            task.phase = TaskPhase.APPROVAL
            if "candidate_commit" not in task.pending_approval:
                task.pending_approval.append("candidate_commit")
        self.store.save(task)
        self._record_and_sync(
            task_id=task_id,
            event="verification_completed",
            data=report.as_dict(),
        )
        return report

    def doctor(self) -> dict:
        state = self.worktrees.inspect()
        ollama = OllamaProvider(num_threads=8)
        local_model = "qwen3-coder:30b"
        knowledge = self.refresh_knowledge()
        writer_route = self.router.route(
            "Empire Coder diagnostic",
            role="writer",
        )
        verifier_route = self.router.route(
            "Empire Coder diagnostic",
            role="verifier",
            exclude=((writer_route.provider, writer_route.model),),
        )
        return {
            "ok": True,
            "workspace": str(self.workspace),
            "branch": state.branch,
            "head": state.head,
            "dirty": state.dirty,
            "blueprint_present": (
                self.workspace / "docs" / "BLUEPRINT_V6.md"
            ).is_file(),
            "execution_mode": "OBSERVE",
            "permission_profile": self.permissions.name,
            "ollama_healthy": ollama.health(),
            "ollama_models": list(ollama.models()),
            "local_coder_ready": ollama.has_model(local_model),
            "local_coder_model": local_model,
            "writer_model": {
                "provider": writer_route.provider,
                "model": writer_route.model,
                "reason": writer_route.reason,
            },
            "verifier_model": {
                "provider": verifier_route.provider,
                "model": verifier_route.model,
                "reason": verifier_route.reason,
            },
            "distinct_verifier_model_ready": (
                verifier_route.provider != "unconfigured"
            ),
            "deterministic_verifier_authoritative": True,
            "knowledge": knowledge,
            "production_authority": False,
        }

    def candidate_report(self, task_id: str) -> dict:
        task = self.store.load(task_id)
        status = self.run_tool(task_id, ("git", "status", "--short"))
        stat = self.run_tool(task_id, ("git", "diff", "--stat"))
        diff_check = self.run_tool(
            task_id, ("git", "diff", "--check")
        )
        return {
            "task": compact_task_context(task),
            "git_status": status.stdout,
            "diff_stat": stat.stdout,
            "diff_check_passed": diff_check.returncode == 0,
            "pending_approval": list(task.pending_approval),
        }

    def _require(self, capability: Capability) -> None:
        if not self.permissions.allows(capability):
            raise EmpireCoderError(
                f"capability denied by profile "
                f"{self.permissions.name}: {capability.value}"
            )
