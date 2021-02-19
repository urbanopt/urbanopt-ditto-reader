# urbanopt-ditto-reader
Enhancement of URBANopt™ GeoJSON that can be consumed by DiTTo reader
More detailed documentation is available on the [URBANopt documentation page](https://docs.urbanopt.net/opendss/opendss.html)

# Installation Pre-requisites
- Python >=3.7

# Installation

`pip install urbanopt-ditto-reader`

# Running the converter

## Use the included Command Line Interface:

`ditto_reader_cli -h`

### For help text in the terminal:
`ditto_reader_cli run-opendss -h`

### Example command to run the ditto-reader:
`ditto_reader_cli run-opendss -s <ScenarioFile> -f <FeatureFile>`

### Or build and use a config file (not necessary if using flags like the above example):
`ditto_reader_cli run-opendss -c example/config.json`

#### If you are using your own config.json file, use the following fields:
1. "urbanopt_scenario_file": Required, Path to scenario csv file
1. "urbanopt_geojson_file": Required, Path to feature json file
1. "equipment_file": Optional, Path to custom equipment file
1. "opendss_folder": Required, Path to dir created by this command, holding openDSS output
1. "use_reopt": Required, Boolean (True/False) to analyze reopt data, if it has been provided
1. "number_of_timepoints": Required, Integer number of hours to simulate. 8760 is a complete year

# Developer installation

Clone the repository:
`git clone https://github.com/urbanopt/urbanopt-ditto-reader.git`

Change directories into the repository:
`cd urbanopt-ditto-reader`

Install the respository:

`pip install -e .`
