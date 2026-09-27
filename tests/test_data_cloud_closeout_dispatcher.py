from empire_os.data_cloud_closeout_dispatcher import dispatch_closeout_wave


def test_closeout_dispatcher_preserves_zero_cutover_authority(tmp_path):
    seen = []

    def dispatcher(_root, request, *, execute_pi):
        seen.append((request.request_id, request.base_branch, execute_pi))
        return {
            "request_id": request.request_id,
            "status": "QUEUED",
            "production_deploy": False,
            "execution_authority": "none",
        }

    payload = dispatch_closeout_wave(
        tmp_path,
        execute_pi=False,
        max_parallel=3,
        dispatcher=dispatcher,
    )

    assert payload["request_count"] == 7
    assert payload["dispatch_failure_count"] == 0
    assert payload["authority"]["production_deploy"] is False
    assert payload["authority"]["database_mutation"] is False
    assert payload["authority"]["canonical_backend_change"] is False
    assert payload["authority"]["production_cutover_authority"] is False
    assert all(
        base_branch == "agent/data-cloud-wave4"
        for _, base_branch, _ in seen
    )
    assert all(execute_pi is False for _, _, execute_pi in seen)


def test_closeout_dispatcher_records_dispatch_exception(tmp_path):
    def dispatcher(_root, request, *, execute_pi):
        if request.request_id == "empiredb-closeout-tenant-isolation":
            raise RuntimeError("boom")
        return {
            "request_id": request.request_id,
            "status": "QUEUED",
        }

    payload = dispatch_closeout_wave(
        tmp_path,
        execute_pi=False,
        dispatcher=dispatcher,
    )

    assert payload["dispatch_failure_count"] == 1
    failed = [
        row
        for row in payload["results"]
        if row["status"] == "DISPATCH_EXCEPTION"
    ]
    assert failed[0]["request_id"] == "empiredb-closeout-tenant-isolation"
    assert failed[0]["production_deploy"] is False



def test_hermes_publications_are_serialized_before_parallel_lanes(tmp_path):
    order = []
    active_hermes = 0
    max_active_hermes = 0

    def dispatcher(_root, request, *, execute_pi):
        nonlocal active_hermes, max_active_hermes
        if request.capability == "backend_code":
            active_hermes += 1
            max_active_hermes = max(max_active_hermes, active_hermes)
            order.append(request.request_id)
            active_hermes -= 1
        return {
            "request_id": request.request_id,
            "status": "QUEUED",
        }

    payload = dispatch_closeout_wave(
        tmp_path,
        execute_pi=False,
        max_parallel=4,
        dispatcher=dispatcher,
    )

    assert payload["dispatch_failure_count"] == 0
    assert payload["hermes_queue_mode"] == (
        "serial_control_branch_publication"
    )
    assert max_active_hermes == 1
    assert len(order) >= 5


def test_dispatch_exception_includes_bounded_detail(tmp_path):
    def dispatcher(_root, request, *, execute_pi):
        if request.request_id == "empiredb-closeout-tenant-isolation":
            raise RuntimeError("control branch publication race")
        return {
            "request_id": request.request_id,
            "status": "QUEUED",
        }

    payload = dispatch_closeout_wave(
        tmp_path,
        execute_pi=False,
        dispatcher=dispatcher,
    )

    failed = next(
        row
        for row in payload["results"]
        if row["request_id"] == "empiredb-closeout-tenant-isolation"
    )
    assert failed["status"] == "DISPATCH_EXCEPTION"
    assert failed["error_class"] == "RuntimeError"
    assert "publication race" in failed["error_detail"]
