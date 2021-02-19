# ditto_reader_cli

import click
import json
import sys
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
    type=click.Path(exists=True, file_okay=True, dir_okay=False, resolve_path=True),
    help="Path to scenario file"
)
@click.option(
    '-f',
    "--feature_file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, resolve_path=True),
    help="Path to feature file"
)
@click.option(
    "-e",
    "--equipment",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, resolve_path=True),
    help="Path to optional custom equipment file"
)
@click.option(
    "-t",
    "--time_points",
    type=int,
    default=10,
    help="Number of hours to analyze. 8760 hours per year"
)
@click.option(
    '-r',
    '--reopt',
    is_flag=True,
    help="Flag to use REopt data in this openDSS analysis"
)
@click.option(
    '-c',
    '--config',
    type=click.Path(exists=True, file_okay=True, dir_okay=False, resolve_path=True),
    help="Path to a json config file for all settings"
)
def run_opendss(scenario_file, feature_file, equipment, time_points, reopt, config):
    """
    \b
    Run OpenDSS on an existing URBANopt scenario.
    If referencing your own json config file: all settings must be made in that file using absolute paths.

    \f
    :param scenario_file: Path, location and name of scenario csv file
    :param feature_file: Path, location & name of feature json file
    :param equipment: Path, location and name of custom equipment file
    :param time_points: Int, number of hours in opendss analysis
    :param reopt: Boolean, flag to specify that reopt data is present and OpenDSS analysis should include it
    :param config: Path, location of config file specifying input options for OpenDSS
    """

    try:
        if config:
            with open(config) as f:
                config_dict = json.load(f)
        else:
            scenario_name = Path(scenario_file).stem
            scenario_dir = Path(scenario_file).parent / "run" / scenario_name

            config_dict = {
                'urbanopt_scenario_file': scenario_file,
                'urbanopt_geojson_file': feature_file,
                'use_reopt': reopt,
                'opendss_folder': scenario_dir / 'opendss',
                'number_of_timepoints': time_points
                }
            if equipment:
                config_dict['equipment_file'] = equipment

        ditto = UrbanoptDittoReader(config_dict)
        ditto.run()
    except Exception as e:
        print(f"CLI failed with message: {e}")
        sys.exit(1)
    else:
        print(f"\nDone. Results located in {config_dict['opendss_folder']}\n")
