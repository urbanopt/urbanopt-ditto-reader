# urbanopt-ditto-reader
Enhancement of URBANopt™ GeoJSON that can be consumed by DiTTo reader
More detailed documentation is available on the [URBANopt documentation page](https://docs.urbanopt.net/opendss/opendss.html)

# Installation Pre-requisites
- Python >=3.7
- git
- pip

# Installation

Clone the repository:
`git clone https://github.com/urbanopt/urbanopt-ditto-reader.git`

Change directories into the repository:
`cd urbanopt-ditto-reader`

Install the respository:

`pip install -e .`

# Running the converter

For help text in the terminal: \
`ditto_reader_cli -h`

Example command to run the ditto-reader: \
`ditto_reader_cli run-opendss -s <ScenarioFile> -f <FeatureFile>`
