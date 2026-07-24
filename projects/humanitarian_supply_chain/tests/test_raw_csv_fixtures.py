import pytest

pytestmark = pytest.mark.component


def test_raw_csv_fixture_row_counts(
    warehouses_df,
    programmes_df,
    items_df,
    shipments_df,
):
    assert warehouses_df.count() == 6
    assert programmes_df.count() == 5
    assert items_df.count() == 7
    assert shipments_df.count() == 167
