import pandas as pd

from ml.features import required_columns, validate_training_dataframe


def test_missing_training_columns_are_rejected():
    result = validate_training_dataframe(
        pd.DataFrame({"default_flag": [0, 1]})
    )
    assert not result.valid
    assert "Missing required columns" in result.errors[0]


def test_required_columns_include_target_and_ids():
    columns = required_columns()
    assert "application_id" in columns
    assert "as_of_date" in columns
    assert "default_flag" in columns
