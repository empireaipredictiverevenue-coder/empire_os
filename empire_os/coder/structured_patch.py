"""Machine-checkable patch proposals for Empire Coder."""
from __future__ import annotations

import ast
import json
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .ast_patch import find_python_symbol
from .context import ContextPack
from .models import ModelRoute
from .patch import PatchError
from .policy import PolicyError, resolve_path, resolve_workspace
from .provider import ModelProvider, ModelRequest
from .security import scan_text


class PatchOperation(str, Enum):
    REPLACE_EXACT = "replace_exact"
    REPLACE_PYTHON_SYMBOL = "replace_python_symbol"
    CREATE_FILE = "create_file"


@dataclass(frozen=True)
class StructuredPatchProposal:
    operation: PatchOperation
    target_path: str
    new_text: str
    rationale: str
    symbol: str | None = None
    old_text: str | None = None
    expected_tests: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["operation"] = self.operation.value
        data["expected_tests"] = list(self.expected_tests)
        return data


@dataclass(frozen=True)
class PatchValidation:
    valid: bool
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StructuredPatchCandidate:
    candidate_texts: tuple[str, ...]
    critique: str
    synthesized_text: str
    proposal: StructuredPatchProposal
    validation: PatchValidation

    @property
    def eligible(self) -> bool:
        return (
            len(self.candidate_texts) >= 2
            and bool(self.critique.strip())
            and self.validation.valid
        )


_ALLOWED_CREATE_SUFFIXES = frozenset({
    ".py", ".js", ".ts", ".tsx", ".json", ".md",
    ".sql", ".yaml", ".yml", ".toml", ".txt",
})


class StructuredPatchError(RuntimeError):
    pass


class StructuredPatchValidator:
    def __init__(self, workspace: str | Path) -> None:
        self.workspace = resolve_workspace(workspace)

    def validate(
        self,
        proposal: StructuredPatchProposal,
    ) -> PatchValidation:
        reasons: list[str] = []
        warnings: list[str] = []

        try:
            target = resolve_path(
                self.workspace,
                proposal.target_path,
                allow_missing=(
                    proposal.operation is PatchOperation.CREATE_FILE
                ),
            )
        except (PolicyError, FileNotFoundError) as exc:
            return PatchValidation(
                False,
                (f"path_validation_failed:{exc}",),
            )

        if not proposal.new_text.strip():
            reasons.append("new_text_empty")

        findings = scan_text(
            proposal.new_text,
            path=proposal.target_path,
        )
        if any(
            finding.severity in {"critical", "high"}
            for finding in findings
        ):
            reasons.append("security_scan_failed")

        if proposal.operation is PatchOperation.CREATE_FILE:
            if target.exists():
                reasons.append("create_target_already_exists")
            if target.suffix.lower() not in _ALLOWED_CREATE_SUFFIXES:
                reasons.append("create_suffix_not_allowed")
            if target.suffix.lower() == ".py":
                self._validate_python(
                    proposal.new_text,
                    reasons,
                )

        elif proposal.operation is PatchOperation.REPLACE_EXACT:
            if proposal.old_text is None or not proposal.old_text:
                reasons.append("old_text_required")
            else:
                try:
                    source = target.read_text(
                        encoding="utf-8",
                        errors="replace",
                    )
                    count = source.count(proposal.old_text)
                    if count != 1:
                        reasons.append(
                            f"old_text_match_count:{count}"
                        )
                    elif target.suffix.lower() == ".py":
                        candidate_source = source.replace(
                            proposal.old_text,
                            proposal.new_text,
                            1,
                        )
                        self._validate_python(
                            candidate_source,
                            reasons,
                        )
                except OSError:
                    reasons.append("target_read_failed")

        elif proposal.operation is PatchOperation.REPLACE_PYTHON_SYMBOL:
            if target.suffix.lower() != ".py":
                reasons.append("python_symbol_target_must_be_py")
            if not proposal.symbol:
                reasons.append("symbol_required")
            else:
                try:
                    source = target.read_text(encoding="utf-8")
                    find_python_symbol(
                        source,
                        proposal.symbol,
                    )
                except (OSError, SyntaxError, PatchError) as exc:
                    reasons.append(
                        f"symbol_validation_failed:{exc}"
                    )
                self._validate_python_symbol_replacement(
                    proposal,
                    reasons,
                )

        for test_path in proposal.expected_tests:
            test_candidate = Path(test_path)
            if (
                test_candidate.is_absolute()
                or ".." in test_candidate.parts
            ):
                reasons.append("expected_test_path_invalid")

        if not proposal.rationale.strip():
            warnings.append("rationale_missing")
        if not proposal.expected_tests:
            warnings.append("expected_tests_missing")

        return PatchValidation(
            not reasons,
            tuple(reasons),
            tuple(warnings),
        )

    @staticmethod
    def _validate_python(
        source: str,
        reasons: list[str],
    ) -> None:
        try:
            ast.parse(source)
        except SyntaxError:
            reasons.append("python_syntax_invalid")

    @staticmethod
    def _validate_python_symbol_replacement(
        proposal: StructuredPatchProposal,
        reasons: list[str],
    ) -> None:
        try:
            tree = ast.parse(proposal.new_text)
        except SyntaxError:
            reasons.append("python_replacement_syntax_invalid")
            return
        definitions = [
            node
            for node in tree.body
            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            )
        ]
        if (
            len(definitions) != 1
            or definitions[0].name != proposal.symbol
        ):
            reasons.append(
                "python_replacement_must_define_requested_symbol"
            )


class StructuredPatchRefiner:
    """Best-of-N strict-JSON patch synthesis plus live-file validation."""

    def __init__(
        self,
        provider: ModelProvider,
        validator: StructuredPatchValidator,
    ) -> None:
        self.provider = provider
        self.validator = validator

    def propose(
        self,
        *,
        task_id: str,
        objective: str,
        context: ContextPack,
        route: ModelRoute,
        max_output_chars: int = 3_200,
    ) -> StructuredPatchCandidate:
        candidates: list[str] = []
        strategy_schema = (
            '{"operation":"replace_python_symbol|replace_exact|create_file",'
            '"target_path":"relative/path",'
            '"symbol":"name-or-null",'
            '"approach":"concise implementation approach",'
            '"expected_tests":["tests/..."]}'
        )
        final_schema = (
            '{"operation":"replace_python_symbol|replace_exact|create_file",'
            '"target_path":"relative/path",'
            '"symbol":"name-or-null",'
            '"old_text":"exact-text-or-null",'
            '"new_text":"replacement",'
            '"rationale":"why",'
            '"expected_tests":["tests/..."]}'
        )

        for index in range(2):
            response = self.provider.complete(ModelRequest(
                task_id=task_id,
                instruction=(
                    "Produce an independent PATCH STRATEGY for the objective "
                    "using supplied repository evidence only. Do not emit the "
                    "full replacement code yet and do not apply anything. "
                    "Return STRICT JSON only using this compact shape: "
                    + strategy_schema
                    + f"\nThis is candidate {index + 1}.\nOBJECTIVE:\n"
                    + objective
                ),
                context=context,
                route=route,
                max_output_chars=min(max_output_chars, 1_200),
            ))
            if response.error:
                raise StructuredPatchError(response.error)
            if not response.text.strip():
                raise StructuredPatchError(
                    "empty structured patch strategy"
                )
            candidates.append(response.text)

        block = "\n\n".join(
            f"CANDIDATE {i + 1}:\n{text}"
            for i, text in enumerate(candidates)
        )
        critique = self.provider.complete(ModelRequest(
            task_id=task_id,
            instruction=(
                "Compare both patch strategies against the actual repository "
                "evidence. Identify stale assumptions, wrong target paths or "
                "symbols, over-broad edits, missing tests and safety issues. "
                "Do not simply choose candidate one. Return concise critique "
                "only.\n\n" + block
            ),
            context=context,
            route=route,
            max_output_chars=1_000,
        ))
        if critique.error:
            raise StructuredPatchError(critique.error)
        if not critique.text.strip():
            raise StructuredPatchError(
                "empty structured patch critique"
            )

        synthesis = self.provider.complete(ModelRequest(
            task_id=task_id,
            instruction=(
                "Synthesize a NEW complete strict-JSON patch proposal from "
                "the strongest evidence-backed parts of both compact strategies "
                "and critique. This is the only stage that should include the "
                "full replacement code. Do not apply the patch. Return JSON "
                "only using exactly this shape: "
                + final_schema
                + "\n\n"
                + block
                + "\n\nCRITIQUE:\n"
                + critique.text
            ),
            context=context,
            route=route,
            max_output_chars=min(max_output_chars, 3_200),
        ))
        if synthesis.error:
            raise StructuredPatchError(synthesis.error)

        proposal = self._parse(synthesis.text)
        validation = self.validator.validate(proposal)
        return StructuredPatchCandidate(
            tuple(candidates),
            critique.text,
            synthesis.text,
            proposal,
            validation,
        )

    @staticmethod
    def _parse(text: str) -> StructuredPatchProposal:
        value = text.strip()
        if value.startswith("```"):
            lines = value.splitlines()
            if (
                len(lines) < 3
                or lines[0].strip().lower() not in {"```", "```json"}
                or lines[-1].strip() != "```"
            ):
                raise StructuredPatchError(
                    "synthesized patch was not strict JSON"
                )
            value = "\n".join(lines[1:-1]).strip()
        if not value.startswith("{") or not value.endswith("}"):
            raise StructuredPatchError(
                "synthesized patch was not strict JSON"
            )
        try:
            raw = json.loads(value)
        except json.JSONDecodeError as exc:
            raise StructuredPatchError(
                "synthesized patch was not strict JSON"
            ) from exc
        if not isinstance(raw, dict):
            raise StructuredPatchError(
                "structured patch must be a JSON object"
            )
        try:
            operation = PatchOperation(raw["operation"])
            target_path = str(raw["target_path"])
            new_text = str(raw["new_text"])
            rationale = str(raw.get("rationale") or "")
        except (KeyError, ValueError, TypeError) as exc:
            raise StructuredPatchError(
                "structured patch required fields invalid"
            ) from exc
        tests = raw.get("expected_tests") or []
        if not isinstance(tests, list) or any(
            not isinstance(item, str) for item in tests
        ):
            raise StructuredPatchError(
                "expected_tests must be a string array"
            )
        symbol = raw.get("symbol")
        old_text = raw.get("old_text")
        return StructuredPatchProposal(
            operation=operation,
            target_path=target_path,
            new_text=new_text,
            rationale=rationale,
            symbol=(
                None if symbol is None else str(symbol)
            ),
            old_text=(
                None if old_text is None else str(old_text)
            ),
            expected_tests=tuple(dict.fromkeys(tests)),
        )
