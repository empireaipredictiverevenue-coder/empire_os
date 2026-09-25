from empire_os.pi_tool_call_probe import evaluate_tool_call_payload


def test_structured_tool_call_is_accepted():
    payload = {"choices": [{"message": {"content": None, "tool_calls": [{
        "id": "call_1",
        "type": "function",
        "function": {"name": "empire_probe", "arguments": "{\"value\":\"TOOL_CALL_OK\"}"},
    }]}}]}
    result = evaluate_tool_call_payload(payload, expected_tool="empire_probe", model="qwen-test")
    assert result.ok is True
    assert result.tool_name == "empire_probe"


def test_textual_json_is_not_a_tool_call():
    payload = {"choices": [{"message": {"content": "{\"name\":\"empire_probe\"}"}}]}
    result = evaluate_tool_call_payload(payload, expected_tool="empire_probe", model="qwen-test")
    assert result.ok is False
    assert result.reason == "structured_tool_calls_missing"
    assert result.raw_content_present is True


def test_parsed_argument_object_is_capability_evidence():
    payload = {"choices": [{"message": {"tool_calls": [{
        "function": {"name": "empire_probe", "arguments": {"value": "TOOL_CALL_OK"}}
    }]}}]}
    result = evaluate_tool_call_payload(payload, expected_tool="empire_probe", model="qwen-test")
    assert result.ok is True
    assert result.arguments_valid_json is True
