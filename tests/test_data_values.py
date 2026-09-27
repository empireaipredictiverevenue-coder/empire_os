from empire_os.data_values import JsonValue, json_value, unwrap_data_value


def test_json_value_marks_list_without_changing_contents():
    wrapped = json_value(["a", "b"])
    assert isinstance(wrapped, JsonValue)
    assert wrapped.value == ["a", "b"]


def test_legacy_unwrap_recurses_through_json_values():
    value = {
        "payload": JsonValue({"dimensions": JsonValue(["a", "b"])}),
        "identity_keys": ["phone:1", "website:x"],
    }

    assert unwrap_data_value(value) == {
        "payload": {"dimensions": ["a", "b"]},
        "identity_keys": ["phone:1", "website:x"],
    }
