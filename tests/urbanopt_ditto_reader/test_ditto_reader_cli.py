import subprocess
from pathlib import Path

examples_dir = Path(__file__).parent.parent.parent / "example"
config_file_path = examples_dir / "example_config.json"

# Test CLI commands


# https://pytest.org/en/latest/how-to/capture-stdout-stderr.html
# not sure why we need capfd instead of capsys
def test_default_settings(capfd):
    subprocess.run(
        ["ditto_reader_cli", "run-opendss", "--config", "example_config.json"],
        cwd=examples_dir,
    )
    captured = capfd.readouterr()
    assert "Done. Results located in" in captured.out


# This doesn't test the quality of the results, only that it doesn't crash
def test_rnm(capfd):
    subprocess.run(
        ["ditto_reader_cli", "run-opendss", "--config", "example_config.json", "-m"],
        cwd=examples_dir,
    )
    captured = capfd.readouterr()
    assert "Done. Results located in" in captured.out


def test_upgrade_transformers(capfd):
    subprocess.run(
        [
            "ditto_reader_cli",
            "run-opendss",
            "--config",
            "example_config.json",
            "--upgrade",
        ],
        cwd=examples_dir,
    )
    captured = capfd.readouterr()
    assert "Upgrading to" in captured.out
    # This text is printed by ditto.consistency.fix_undersized_transformers


# REopt data for testing not present in this repo as of 2023-04-05
# def test_use_reopt(capfd):
#     subprocess.run(
#         ["ditto_reader_cli", "run-opendss", "--config", "example_config.json", "-r"],
#         cwd=examples_dir,
#     )
#     captured = capfd.readouterr()
#     assert "Done. Results located in" in captured.out


def test_specific_times(capfd):
    subprocess.run(
        [
            "ditto_reader_cli",
            "run-opendss",
            "--config",
            "example_config.json",
            "--start_date",
            "2017/08/15",
            "--start_time",
            "18:00:00",
            "--end_date",
            "2017/08/16",
            "--end_time",
            "12:00:00",
        ],
        cwd=examples_dir,
    )
    captured = capfd.readouterr()
    assert "Timepoint: 2017/08/16 12:00:00" in captured.out
    assert "Timepoint: 2017/08/15 17:00:00" not in captured.out


def test_timestep(capfd):
    subprocess.run(
        [
            "ditto_reader_cli",
            "run-opendss",
            "--config",
            "example_config.json",
            "--timestep",
            "360",
        ],
        cwd=examples_dir,
    )
    captured = capfd.readouterr()
    assert "timestep: 360" in captured.out
