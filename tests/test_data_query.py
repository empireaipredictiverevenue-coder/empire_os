import pytest

from empire_os.data_query import DataFilter, FilterOperator, OrderSpec


def test_in_filter_normalizes_values_to_tuple():
    item = DataFilter.in_("tier", ["hot", "warm"])
    assert item.operator is FilterOperator.IN
    assert item.value == ("hot", "warm")


def test_in_filter_rejects_string_as_sequence():
    with pytest.raises(ValueError, match="value sequence"):
        DataFilter("tier", FilterOperator.IN, "hot")


def test_in_filter_rejects_empty_values():
    with pytest.raises(ValueError, match="at least one"):
        DataFilter.in_("tier", ())


def test_is_null_rejects_accidental_value():
    with pytest.raises(ValueError, match="does not accept"):
        DataFilter("entity_id", FilterOperator.IS_NULL, "x")


def test_order_requires_column():
    with pytest.raises(ValueError, match="order column"):
        OrderSpec("")
