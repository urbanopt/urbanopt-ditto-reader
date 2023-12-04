# urbanopt-ditto-reader
Enhancement of URBANopt™ GeoJSON that can be consumed by DiTTo reader \
More detailed documentation is available on the [URBANopt documentation page](https://docs.urbanopt.net/opendss/opendss.html)

# Installation Pre-requisites
- Python >=3.8
- Requires Python 3.10 if using via the URBANopt CLI.

# Installation

`pip install urbanopt-ditto-reader`

# Running the converter

You are expected to have an existing URBANopt project dir with successful simulations of electrical network components before using this package.

## Use the included Command Line Interface:

`ditto_reader_cli -h`

### For help text in the terminal:
`ditto_reader_cli run-opendss -h`

### Example command to run the ditto-reader:
`ditto_reader_cli run-opendss -s <ScenarioFile> -f <FeatureFile>`

### Or build and use a config file (not necessary if using flags like the above example):
`ditto_reader_cli run-opendss -c urbanopt_ditto_reader/example_config.json`

#### If you are using your own config.json file, use the following fields:
1. "urbanopt_scenario_file": Required, Path to scenario csv file
1. "urbanopt_geojson_file": Required, Path to feature json file
1. "equipment_file": Optional, Path to custom equipment file. If not specified, the 'extended_catalog.json' file will be used
1. "opendss_folder": Required, Path to dir created by this command, holding openDSS output
1. "use_reopt": Required, Boolean (True/False) to analyze reopt data, if it has been provided
1. "start_date": Optional, String, Indicates the start date of the simulation. Uses format "YYYY/MM/DD"
1. "start_time": Optional, String, Indicates the start time of the simulation. Uses format
   "HH:MM:SS".
The start_date and
   start_time are concatenated to get the timestamp (using format "YYYY/MM/DD HH:MM:SS") for the config
   file that is cross referenced with the timestamps in the
   SCENARIO_NAME/opendss/profiles/timestamps.csv file created from profiles in
   SCENARIO_NAME/FEATURE_ID/feature_reports/feature_report_reopt.csv if use_reopt is true and
   SCENARIO_NAME/FEATURE_ID/feature_reports/default_feature_report.csv if use_reopt is false. It assumes start_time to be 00:00:00 if start_date is found but no
    start_time. It runs the entire year if timestamp not found.
1. "end_date": Optional, String, Indicates the end date of the simulation. Uses format "YYYY/MM/DD"
1. "end_time": Optional, String, Indicates the end time of the simulation. Uses format "HH:MM:SS".
   The end_date and end_time are concatenated to get the timestamp (using format
   "YYYY/MM/DD HH:MM:SS") for the config file and is cross referenced with the timestamps in the
   SCENARIO_NAME/opendss/profiles/timestamps.csv file created from profiles in
   SCENARIO_NAME/FEATURE_ID/feature_reports/feature_report_reopt.csv if use_reopt is true and
   SCENARIO_NAME/FEATURE_ID/feature_reports/default_feature_report.csv if use_reopt is false. It assumes end_time to be 23:00:00 if end_date is found but no end_time. It runs the entire year if timestamp not found.
1. "timestep": Optional, Float number of minutes between each simulation. If smaller than timesteps (or not an even multiple) provided by the reopt feature reports (if use_repot is true), or urbanopt feature reports (if use_reopt is false), an error is raised
1. "upgrade_transformers": Optional, Boolean (True/False). If true, will automatically upgrade transformers that are sized smaller than the sum of the peak loads that it serves. Does not update geojson file - just opendss output files

If either start_time and end_time are invalid or set to None, the simulation will be run for all timepoints provided by the reopt simulation (if use_reopt is true) or urbanopt simulation (if use_reopt is false)

# Developer installation

- Clone the repository: `git clone https://github.com/urbanopt/urbanopt-ditto-reader.git`
- Change directories into the repository: `cd urbanopt-ditto-reader`
- As general guidance, we recommend using virtual environments to avoid dependencies colliding between your Python projects. [venv](https://docs.python.org/3/library/venv.html) is the Python native solution that will work everywhere, though other options may be more user-friendly.
    - Some popular alternatives are:
        - [pyenv](https://github.com/pyenv/pyenv) and [the virtualenv plugin](https://github.com/pyenv/pyenv-virtualenv) work together nicely for Linux/Mac machines
        - [virtualenv](https://virtualenv.pypa.io/en/latest/)
        - [miniconda](https://docs.conda.io/projects/miniconda/en/latest/)
    - Activate pre-commit (only once, after making a new venv): `pre-commit install`
    - Runs automatically on your staged changes before every commit
- Update pip and setuptools: `pip install -U pip setuptools`
- Install the respository with developer dependencies: `pip install -e .[dev]`
- To check the whole repo, run `pre-commit run --all-files`
    - Settings and documentation links for pre-commit and ruff are in .pre-commit-config.yaml and pyproject.toml

# Releasing
Increment the version in pyproject.toml. Use [semantic versioning](https://semver.org/). When a new release is made in GitHub, a [workflow](https://github.com/marketplace/actions/pypi-publish) automatically publishes to PyPI.
