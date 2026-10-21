"""Bounded, evidence-backed model guard patches for one low-risk Coder pilot.

Two independent local inferences supply the CONDITION. The code template,
source location, static semantic checks, scope and tests remain deterministic.
This is not the general multi-stage architecture writer.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from .context import ContextDocument, ContextPack
from .models import ModelRoute
from .policy import resolve_path, resolve_workspace
from .provider import ModelProvider, ModelRequest
from .structured_patch import (
    PatchOperation,
    StructuredPatchCandidate,
    StructuredPatchError,
    StructuredPatchProposal,
    StructuredPatchValidator,
)


def _source_guard_location(source: str) -> tuple[str, str, str]:
    """Identify one single-line row.get call at the start of a Python loop."""
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    matches = []
    for loop in ast.walk(tree):
        if not isinstance(loop, (ast.For, ast.AsyncFor)):
            continue
        if not isinstance(loop.target, ast.Name) or loop.target.id != "row":
            continue
        if not loop.body:
            continue
        first = loop.body[0]
        if first.lineno != first.end_lineno:
            continue
        accesses_row_get = any(
            isinstance(item, ast.Call)
            and isinstance(item.func, ast.Attribute)
            and item.func.attr == "get"
            and isinstance(item.func.value, ast.Name)
            and item.func.value.id == "row"
            for item in ast.walk(first)
        )
        if not accesses_row_get:
            continue
        old = lines[first.lineno - 1]
        header = lines[loop.lineno - 1]
        if (not old.endswith("\n") or len(old) > 250
                or old.count("\n") != 1 or len(header) > 250):
            continue
        indent = old[:len(old) - len(old.lstrip(" "))]
        if not indent or "\t" in old:
            continue
        matches.append((header, old, indent))
    if len(matches) != 1:
        raise StructuredPatchError("micro_guard_requires_one_unique_unguarded_loop")
    return matches[0]


def _safe_guard(condition: str) -> bool:
    """Only a narrow, pure AST operation is permitted from untrusted output."""
    if not isinstance(condition, str) or len(condition) > 75:
        return False
    try:
        proposed = ast.parse(condition.strip(), mode="eval")
        expected = ast.parse("not isinstance(row, dict)", mode="eval")
    except SyntaxError:
        return False
    return ast.dump(proposed, include_attributes=False) == ast.dump(
        expected, include_attributes=False,
    )


def propose_micro_guard(
    *,
    workspace: Path,
    provider: ModelProvider,
    route: ModelRoute,
    task_id: str,
    objective: str,
    source_path: str,
    required_tests: tuple[str, ...],
) -> StructuredPatchCandidate:
    """Two authentic model outputs + deterministic independent patch review.

    This helper does not enqueue, apply, deploy or grant execution authority.
    The enclosing original sandbox provides the lease, allowed paths, tests
    and separately verified proposal-only publication.
    """
    root = resolve_workspace(workspace)
    source_file = resolve_path(root, source_path)
    if source_file.is_symlink() or source_file.suffix != ".py":
        raise StructuredPatchError("micro_guard_source_not_regular_python")
    source = source_file.read_text(encoding="utf-8")
    header, old_line, indent = _source_guard_location(source)
    if source.count(old_line) != 1:
        raise StructuredPatchError("micro_guard_source_line_not_unique")
    context = ContextPack(
        objective=objective,
        task_state={},
        documents=(ContextDocument(
            path=source_path,
            reason="exact authorized source, no unrelated search results",
            excerpt=header + old_line,
        ),),
        symbols=(),
        token_budget_chars=1000,
    )
    responses: list[str] = []
    conditions: list[str] = []
    for index in range(2):
        instruction = (
            "Return STRICT JSON only with one string property named condition. "
            "The expression must be true when the Python loop variable row "
            "is NOT a dict. Output a condition expression, not an if statement, "
            "no colon, no explanation. The source accesses row.get. "
            f"Independent guard candidate {index + 1}."
        )
        reply = provider.complete(ModelRequest(
            task_id=task_id, instruction=instruction,
            context=context, route=route, max_output_chars=250,
        ))
        if reply.error or not reply.text.strip():
            raise StructuredPatchError(
                "micro_guard_model_response_failed:"
                + str(reply.error or "empty_output")
            )
        try:
            data = json.loads(reply.text)
        except (json.JSONDecodeError, TypeError) as exc:
            raise StructuredPatchError("micro_guard_invalid_model_json") from exc
        condition = data.get("condition") if isinstance(data, dict) else None
        if not _safe_guard(condition):
            raise StructuredPatchError("micro_guard_unsafe_or_incorrect_condition")
        responses.append(reply.text)
        conditions.append(condition.strip())

    if len(conditions) != 2 or conditions[0] != conditions[1]:
        raise StructuredPatchError("micro_guard_independent_outputs_disagree")
    condition = conditions[0]
    replacement = (
        indent + "if " + condition + ":\n"
        + indent + "    continue\n"
        + old_line
    )
    proposal = StructuredPatchProposal(
        operation=PatchOperation.REPLACE_EXACT,
        target_path=source_path,
        old_text=old_line,
        new_text=replacement,
        rationale="Two independent local model responses agree on the safe mapping guard.",
        expected_tests=required_tests,
    )
    validation = StructuredPatchValidator(root).validate(proposal)
    # Model text is preserved as two genuinely separate candidates, while
    # the independent critique is explicitly deterministic, not claimed
    # to have come from a third model call.
    candidate = StructuredPatchCandidate(
        candidate_texts=tuple(responses),
        critique=(
            "DETERMINISTIC_AST_REVIEW: two independently generated guard "
            "conditions matched; pure non-dict predicate, exact source "
            "line, Python parse and original path/security policy checked."
        ),
        synthesized_text=json.dumps(proposal.as_dict(), sort_keys=True),
        proposal=proposal,
        validation=validation,
    )
    if not candidate.eligible:
        raise StructuredPatchError(
            "micro_guard_validation_failed:" + ";".join(validation.reasons)
        )
    return candidate
