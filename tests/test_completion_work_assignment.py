from empire_os.completion_work_assignment import completion_wave1_requests


def test_wave1_is_non_overlapping_and_current_branch():
    requests = completion_wave1_requests()
    assert len(requests) == 6
    leased = set()
    for request in requests:
        request.validate()
        assert request.base_branch == "agent/data-cloud-wave4"
        for resource in request.lease_resources:
            assert resource not in leased
            leased.add(resource)


def test_wave1_has_required_worker_lanes():
    requests = completion_wave1_requests()
    capabilities = {request.capability for request in requests}
    assert "backend_code" in capabilities
    assert "parallel_backend_code" in capabilities
    assert "public_research" in capabilities
    assert "integration_qa" in capabilities


def test_wave1_preserves_consequential_gates():
    for request in completion_wave1_requests():
        assert request.authority in {"observe", "internal_write"}
        assert request.risk_class != "consequential"
        text = request.objective.lower()
        assert "move funds" not in text
        assert "recognize revenue" not in text
