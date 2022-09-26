"""
****************************************************************************************************
URBANopt™, Copyright (c) 2019-2022, Alliance for Sustainable Energy, LLC, and other
contributors. All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

Redistributions of source code must retain the above copyright notice, this list
of conditions and the following disclaimer.

Redistributions in binary form must reproduce the above copyright notice, this
list of conditions and the following disclaimer in the documentation and/or other
materials provided with the distribution.

Neither the name of the copyright holder nor the names of its contributors may be
used to endorse or promote products derived from this software without specific
prior written permission.

Redistribution of this software, without modification, must refer to the software
by the same designation. Redistribution of a modified version of this software
(i) may not refer to the modified version by the same designation, or by any
confusingly similar designation, and (ii) must refer to the underlying software
originally provided by Alliance as “URBANopt”. Except to comply with the foregoing,
the term “URBANopt”, or any confusingly similar designation may not be used to
refer to any modified version of this software or any modified version of the
underlying software originally provided by Alliance without the prior written
consent of Alliance.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
OF THE POSSIBILITY OF SUCH DAMAGE.
****************************************************************************************************
"""

# ditto_reader_cli
import os
import json
import sys
from pathlib import Path
import click

from urbanopt_ditto_reader.urbanopt_ditto_reader import UrbanoptDittoReader

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    """URBANopt Ditto Reader"""
    pass


@cli.command(
    short_help='Run OpenDSS on an URBANopt GeoJSON containing detailed electrical '
    'grid objects.'
)
@click.option(
    '-s',
    '--scenario_file',
    type=click.Path(exists=True, file_okay=True, dir_okay=False, resolve_path=True),
    help='Path to scenario file'
)
@click.option(
    '-f',
    '--feature_file',
    type=click.Path(exists=True, file_okay=True, dir_okay=False, resolve_path=True),
    help='Path to feature file'
)
@click.option(
    '-e',
    '--equipment',
    type=click.Path(exists=True, file_okay=True, dir_okay=False, resolve_path=True),
    help='Path to optional custom equipment file'
)
@click.option(
    '-a',
    '--start_date',
    type=str,
    default=None,
    help='Beginning date of simulation. Uses format "YYYY/MM/DD". If unspecified or '
    'invalid, the simulation will begin from the earliest date available.'
)
@click.option(
    '-b',
    '--start_time',
    type=str,
    default=None,
    help='Beginning timestamp of simulation. Uses format "HH:MM:SS". If unspecified, '
    'a default assumption of 00:00:00 is used if the --start_date is specified or '
    'it will simply be the earliest timepoint available.'
)
@click.option(
    '-n',
    '--end_date',
    type=str,
    default=None,
    help='Ending date of simulation. Uses format "YYYY/MM/DD". If unspecified or '
    'invalid, the simulation will begin to the latest date available.'
)
@click.option(
    '-d',
    '--end_time',
    type=str,
    default=None,
    help='Ending timestamp of simulation. Uses format "HH/MM/SS". If unspecified, '
    'a default assumption of 32:00:00 is used if the --end_date is specified or '
    'it will simply be the latest timepoint available.'
)
@click.option(
    '-t',
    '--timestep',
    type=float,
    default=None,
    help='Interval between simulation steps in minutes. If unspecified, the timestep '
    'will be inferred from the load profile results.'
)
@click.option(
    '-r',
    '--reopt',
    is_flag=True,
    help='Flag to use REopt data in this openDSS analysis.'
)
@click.option(
    '-m',
    '--rnm',
    is_flag=True,
    help='Flag to use RNM-generated DSS files in this analysis.'
)
@click.option(
    '-c',
    '--config',
    type=click.Path(exists=True, file_okay=True, dir_okay=False, resolve_path=True),
    help='Path to a json config file that specifies all simulation settings.'
)
@click.option(
    '-u',
    '--upgrade',
    is_flag=True,
    help='Flag to automatically upgrade transformers that are undersized before '
    'running OpenDSS. Note that this will only upgrade the size of transformers '
    'that are smaller than the sum of the peak loads that they serve.'
)
def run_opendss(scenario_file, feature_file, equipment, start_date, start_time,
                end_date, end_time, timestep, reopt, rnm, config, upgrade):
    """Run OpenDSS on an URBANopt GeoJSON containing detailed electrical grid objects.

    \b
    If referencing your own json config file, all settings must be made in that
    file using absolute paths.

    \b
    Note that the start/end date and time are aggregated to get the start/end timestamp
    (using format"YYYY/MM/DD HH:MM:SS"), which is cross referenced with the timestamps
    in the SCENARIO_NAME/opendss/profiles/timestamps.csv. This file is created from
    profiles in SCENARIO_NAME/FEATURE_ID/feature_reports/feature_report_reopt.csv
    if use_reopt is true and SCENARIO_NAME/FEATURE_ID/feature_reports/
    """
    try:
        if config:
            with open(config) as f:
                config_dict = json.load(f)
        else:
            scenario_name = Path(scenario_file).stem
            scenario_dir = Path(scenario_file).parent / "run" / scenario_name

            if start_date and start_time:
                start_date_time = start_date + " " + start_time
            elif start_date and start_time is None:
                start_date_time = start_date + " 00:00:00"
            elif start_date is None or start_time is None:
                start_date_time = None

            if end_date and end_time:
                end_date_time = end_date + " " + end_time
            elif end_date and end_time is None:
                end_date_time = end_date + " 23:00:00"
            elif end_date is None or end_time is None:
                end_date_time = None

            config_dict = {
                'urbanopt_scenario_file': scenario_file,
                'urbanopt_geojson_file': feature_file,
                'use_reopt': reopt,
                'opendss_folder': scenario_dir / 'opendss',
                'start_time': start_date_time,
                'end_time': end_date_time,
                'timestep': timestep,
                'upgrade_transformers': upgrade
            }
            if equipment:
                config_dict['equipment_file'] = equipment

        ditto = UrbanoptDittoReader(config_dict)
        if rnm:
            assert os.path.isdir(ditto.rnm_results), 'The --rnm option was requested ' \
                'but no RNM results were found at "{}".'.format(ditto.rnm_results)
            ditto.run_rnm_opendss()
        else:
            ditto.run_urbanopt_geojson()
    except UnboundLocalError as ube:
        raise SystemError(f"CLI failed with message:\n{ube}")
    else:
        print(f"\nDone. Results located in {config_dict['opendss_folder']}\n")
        sys.exit(0)
