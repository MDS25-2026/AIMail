"""Re-running the dataset generator never overwrites the human-audited files by accident."""

import pytest

from scripts.generate_category_dataset import refuse_to_overwrite


@pytest.mark.parametrize("name", ["train.csv", "holdout_gold.csv", "holdout_audit.csv"])
def test_any_existing_output_stops_the_run_before_any_model_call(tmp_path, name):
    (tmp_path / name).write_text("text,category\n")
    with pytest.raises(SystemExit, match=name):
        refuse_to_overwrite(tmp_path)


def test_an_empty_folder_lets_it_run(tmp_path):
    refuse_to_overwrite(tmp_path)
