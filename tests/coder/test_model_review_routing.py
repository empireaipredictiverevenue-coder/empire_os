import json

from empire_os.coder.context import ContextPack
from empire_os.coder.model_review import DistinctModelReviewer
from empire_os.coder.orchestrator import EmpireCoder
from empire_os.coder.provider import ModelResponse
from empire_os.coder.router import ModelProfile, ModelRouter


def make_repo(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/BLUEPRINT_V6.md").write_text(
        "# Blueprint\nKeep Empire Coder governed.\n",
        encoding="utf-8",
    )
    (tmp_path / "empire_os").mkdir()
    return tmp_path


class FakeProvider:
    def __init__(self, name, response):
        self.name = name
        self.response = response
        self.calls = []

    def complete(self, request):
        self.calls.append(request)
        return ModelResponse(
            self.name,
            request.route.model,
            self.response,
        )


def test_router_can_separate_writer_and_verifier_roles():
    router = ModelRouter([
        ModelProfile(
            "writer-provider",
            "writer-model",
            capability=3,
            roles=("writer",),
        ),
        ModelProfile(
            "verify-provider",
            "verify-model",
            capability=3,
            roles=("verifier",),
        ),
    ])
    writer = router.route("refactor module", role="writer")
    verifier = router.route(
        "refactor module",
        role="verifier",
        exclude=((writer.provider, writer.model),),
    )
    assert writer.model == "writer-model"
    assert verifier.model == "verify-model"
    assert (writer.provider, writer.model) != (
        verifier.provider,
        verifier.model,
    )


def test_router_fails_closed_without_distinct_verifier():
    router = ModelRouter([
        ModelProfile(
            "same-provider",
            "same-model",
            capability=3,
            roles=("writer", "verifier"),
        ),
    ])
    writer = router.route("security refactor", role="writer")
    verifier = router.route(
        "security refactor",
        role="verifier",
        exclude=((writer.provider, writer.model),),
    )
    assert verifier.provider == "unconfigured"
    assert verifier.model == "none"


def test_distinct_model_reviewer_parses_strict_json():
    provider = FakeProvider(
        "verify-provider",
        json.dumps({
            "verdict": "PASS_WITH_WARNINGS",
            "reasons": ["diff matches objective"],
            "warnings": ["consider one extra edge-case test"],
        }),
    )
    review = DistinctModelReviewer(provider).review(
        task_id="coder_test",
        objective="change bounded behavior",
        context=ContextPack("goal", {}, (), (), 4000),
        route=ModelRouter([
            ModelProfile(
                "verify-provider",
                "verify-model",
                capability=3,
                roles=("verifier",),
            ),
        ]).route("change bounded behavior", role="verifier"),
        changed_files=("empire_os/core.py",),
        diff_excerpt="+ return 2",
    )
    assert review.provider == "verify-provider"
    assert review.model == "verify-model"
    assert review.verdict.value == "PASS_WITH_WARNINGS"
    assert review.advisory_only is True


def test_orchestrator_uses_distinct_verifier_profile(tmp_path):
    root = make_repo(tmp_path)
    coder = EmpireCoder(
        root,
        model_profiles=(
            ModelProfile(
                "writer-provider",
                "writer-model",
                capability=3,
                roles=("writer",),
            ),
            ModelProfile(
                "verify-provider",
                "verify-model",
                capability=3,
                roles=("verifier",),
            ),
        ),
    )
    coder.providers.register(
        FakeProvider("writer-provider", "unused")
    )
    coder.providers.register(
        FakeProvider(
            "verify-provider",
            json.dumps({
                "verdict": "PASS",
                "reasons": ["bounded change"],
                "warnings": [],
            }),
        )
    )
    task = coder.create_task("Refactor safely")
    writer = coder.model_route(task.id)
    verifier = coder.verifier_model_route(task.id)

    assert writer.model == "writer-model"
    assert verifier.model == "verify-model"

    review = coder.advisory_model_review(
        task.id,
        changed_files=("empire_os/core.py",),
        context=ContextPack("goal", {}, (), (), 4000),
        diff_excerpt="+ bounded change",
    )
    assert review is not None
    assert review.model == "verify-model"
    assert review.advisory_only is True


def test_orchestrator_skips_model_review_when_second_model_missing(tmp_path):
    root = make_repo(tmp_path)
    coder = EmpireCoder(
        root,
        model_profiles=(
            ModelProfile(
                "writer-provider",
                "writer-model",
                capability=3,
                roles=("writer",),
            ),
        ),
    )
    coder.providers.register(
        FakeProvider("writer-provider", "unused")
    )
    task = coder.create_task("Refactor safely")
    route = coder.verifier_model_route(task.id)
    assert route.provider == "unconfigured"

    review = coder.advisory_model_review(
        task.id,
        changed_files=("empire_os/core.py",),
        context=ContextPack("goal", {}, (), (), 4000),
        diff_excerpt="+ bounded change",
    )
    assert review is None
