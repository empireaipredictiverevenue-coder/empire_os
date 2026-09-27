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
