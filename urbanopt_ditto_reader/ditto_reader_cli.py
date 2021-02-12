# ditto_reader_cli

import click
import json
from pathlib import Path
from urbanopt_ditto_reader.urbanopt_ditto_reader import UrbanoptDittoReader

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    """URBANopt Ditto Reader"""
    pass

@cli.command(short_help="Run OpenDSS on existing urbanopt simulations")
@click.option(
    '-s',
    '--scenario_file',
    type=click.Path(exists=True),
    help="Path to scenario file"
)
@click.option(
    '-f',
    "--feature_file",
    type=click.Path(exists=True),
    help="Path to feature file"
)
@click.option(
    "-e",
    "--equipment",
    type=click.Path(exists=True),
    help="Path to optional custom equipment file"
)
@click.option(
    '-r',
    '--reopt',
    is_flag=True,
    help="Flag to signify this project also has reopt data"
)
@click.option(
    '-c',
    '--config',
    type=click.Path(exists=True),
    help="Path to a json config file for all settings"
)
def run_opendss(scenario_file, feature_file, equipment, reopt, config):
    """
    \b
    Run OpenDSS on an existing URBANopt scenario.
    If referencing a json config file, all settings must be made in that file.
    See urbanopt_ditto_reader/config.json for an example.

    \f
    :param scenario_file: Path, location and name of scenario csv file
    :param feature_file: Path, location & name of feature json file
    :param equipment: Path, Location and name of custom equipment file
    :param reopt: Boolean, flag to specify that reopt data is present and should be included in modeling
    """

    if config:
        with open(config) as f:
            config_dict = json.load(f)
    else:
        scenario_name = Path(scenario_file).stem
        scenario_filepath = Path(scenario_file).resolve()
        scenario_dir = scenario_filepath.parent / "run" / scenario_name
        feature_filepath = Path(feature_file).resolve()

        config_dict = {
            'urbanopt_scenario': scenario_dir,
            'geojson_file': feature_filepath,
            'use_reopt': reopt,
            'opendss_folder': scenario_dir / 'opendss'
            }
        if equipment:
            config_dict['equipment_file'] = Path(equipment)

    ditto = UrbanoptDittoReader(config_dict)
    ditto.run()

    print(f"\nDone. Results located in {config_dict['opendss_folder']}\n")
