"""
*****************************************************************************************
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
*****************************************************************************************
"""

import json
import math
import os
from datetime import datetime
from pathlib import Path
import pandas as pd
import opendssdirect as dss


class UrbanoptDittoReader(object):
    """A base class for managing inputs for OpenDSS simulation.

    Args:
        config_data: An optional dictionary to specify the configuration parameters.

    Properties:
        * module_path
        * geojson_file
        * urbanopt_scenario_name
        * urbanopt_scenario
        * equipment_file
        * dss_analysis
        * use_reopt
        * start_time
        * end_time
        * timestep
    """

    def __init__(self, config_data=None):
        # set the path to where this module is located
        self.module_path = Path(__file__).parent.parent

        # load default config from config.json; merge with input config_data
        default_data = self.default_config()
        if config_data is None:
            config_data = {}
        config = {**default_data, **config_data}

        print('\nCONFIGS USED:\n{}'.format(
            '\n'.join(['{}: {}'.format(k, v,) for k, v in config.items()])))

        # set the attributes of the class using the configuration variables
        feature_json = config['urbanopt_geojson_file']
        scenario = config['urbanopt_scenario_file']
        self.geojson_file = str(Path(feature_json).expanduser().resolve())
        self.urbanopt_scenario_name = Path(scenario).stem
        self.urbanopt_scenario = str(
            Path(scenario).expanduser().parent / 'run' / self.urbanopt_scenario_name)
        self.equipment_file = str(Path(config['equipment_file']).expanduser().resolve())
        self.dss_analysis = str(Path(config['opendss_folder']).expanduser().resolve())
        self.use_reopt = config['use_reopt']
        self.start_time = None
        self.end_time = None
        self.timestep = None
        if config['timestep'] is not None:
            self.timestep = config['timestep']
        if config['start_time'] is not None:
            self.start_time = str(config['start_time'])
        if config['end_time'] is not None:
            self.end_time = str(config['end_time'])

        self.upgrade_transformers = False
        if 'upgrade_transformers' in config:
            self.upgrade_transformers = config['upgrade_transformers']

        self.timeseries_location = os.path.join(self.dss_analysis, 'profiles')

    def default_config(self):
        """Get a dictionary for the default configuration variables."""
        example_config_file = Path(__file__).parent / 'example_config.json'
        with open(example_config_file) as f:
            default_data = self.fix_paths(json.load(f))
        return default_data

    def fix_paths(self, data):
        """Change a configuration dictionary to use relative paths wrt this module.

        Args:
            data: A dictionary of configuration variables.
        """
        non_path_vars = (
            'use_reopt', 'start_time', 'end_time', 'timestep', 'upgrade_transformers')
        for k, v in data.items():
            if k in non_path_vars:
                continue
            elif not Path(v).is_absolute():
                data[k] = str(Path(self.module_path) / v)
        return data

    def _get_all_voltages(self):
        """Get a dictionary of over and under voltages for all buses."""
        voltage_dict = {}
        bus_names = dss.Circuit.AllBusNames()
        for b in bus_names:
            dss.Circuit.SetActiveBus(b)
            vang = dss.Bus.puVmagAngle()
            if len(vang[::2]) > 0:
                vmag = sum(vang[::2]) / len(vang)
            else:
                vmag = 0
            voltage_dict[b] = vmag * 2

        return voltage_dict

    def _get_line_loading(self):
        """Get a dictionary of loading for the Lines."""
        line_overloads_dict = {}
        # Set the active class to be the lines
        dss.Circuit.SetActiveClass("Line")

        # Loop over the lines
        flag = dss.ActiveClass.First()
        while flag > 0:
            line_name = dss.CktElement.Name()
            # Get the current limit
            line_limit = dss.CktElement.NormalAmps()

            # Compute the current through the line
            dss_curr = dss.CktElement.Currents()
            line_current = []
            for ii in range(int(0.5 * len(dss_curr))):
                current = math.sqrt(
                    dss_curr[2 * (ii - 1) + 2] ** 2 + dss_curr[2 * ii + 1] ** 2)
                line_current.append(current)

            # The loading is the ratio of the two
            line_overloads_dict[line_name] = max(line_current) / float(line_limit)

            # Move on to the next line
            flag = dss.ActiveClass.Next()
        return line_overloads_dict

    def _get_xfmr_overloads(self, ub=1.0):
        """Get a dictionary of Transformer current violations."""
        transformer_violation_dict = {}
        dss.Circuit.SetActiveClass("Transformer")
        flag = dss.ActiveClass.First()
        while flag > 0:
            # Get the name of the Transformer
            transformer_name = dss.CktElement.Name()
            transformer_current = []

            hs_kv = float(dss.Properties.Value('kVs').split('[')[1].split(',')[0])
            kva = float(dss.Properties.Value('kVA'))
            n_phases = dss.CktElement.NumPhases()
            if n_phases > 1:
                transformer_limit_per_phase = kva / (hs_kv * math.sqrt(3))
            else:
                transformer_limit_per_phase = kva / hs_kv

            currents = dss.CktElement.CurrentsMagAng()[:2 * n_phases]
            transformer_current = currents[::2]

            # Compute the loading
            ldg = max(transformer_current) / transformer_limit_per_phase
            transformer_violation_dict[transformer_name] = ldg

            # Move on to the next Transformer...
            flag = dss.ActiveClass.Next()

        return transformer_violation_dict

    def run(self):

        from ditto.store import Store
        from ditto.writers.opendss.write import Writer
        from ditto.writers.json.write import Writer as JSONWriter
        from urbanopt_ditto_reader.reader.read import Reader

        from ditto.consistency.check_loops import check_loops
        from ditto.consistency.check_loads_connected import check_loads_connected
        from ditto.consistency.check_unique_path import check_unique_path
        from ditto.consistency.check_matched_phases import check_matched_phases
        from ditto.consistency.check_transformer_phase_path import \
            check_transformer_phase_path
        from ditto.consistency.fix_transformer_phase_path import \
            fix_transformer_phase_path
        from ditto.consistency.fix_undersized_transformers import \
            fix_undersized_transformers

        # load the OpenDSS model from the URBANopt files
        print('\nRE-SERIALIZING MODEL')
        model = Store()
        reader = Reader(
            geojson_file=self.geojson_file,
            equipment_file=self.equipment_file,
            load_folder=self.urbanopt_scenario,
            use_reopt=self.use_reopt,
            is_timeseries=True,
            timeseries_location=self.timeseries_location,
            relative_timeseries_location=os.path.join('..', 'profiles')
        )
        reader.parse(model)

        # variables for reporting the status of tests
        print('\nCHECKING MODEL')
        OKGREEN = '\033[92m'
        FAIL = '\033[91m'
        ENDC = '\033[0m'

        # perform several checks on the model and report results
        print('Checking that the network has no loops:', flush=True)
        loops_res = check_loops(model, verbose=True)
        result, color = ('PASS', OKGREEN) if loops_res else ('FAIL', FAIL)
        print('Result:', f'{color} {result} {ENDC}')

        print('Checking that all loads are connected to source:', flush=True)
        loads_connected_res = check_loads_connected(model, verbose=True)
        result, color = ('PASS', OKGREEN) if loads_connected_res else ('FAIL', FAIL)
        print('Result:', f'{color} {result} {ENDC}')

        print('Checking for unique paths from each load to source:', flush=True)
        unique_path_res = check_unique_path(model, show_all=True, verbose=True)
        result, color = ('PASS', OKGREEN) if unique_path_res else ('FAIL', FAIL)
        print('Result:', f'{color} {result} {ENDC}')

        print('Checking that phases on either side of transformer are correct:',
              flush=True)
        matched_phases_res = check_matched_phases(model, verbose=True)
        result, color = ('PASS', OKGREEN) if matched_phases_res else ('FAIL', FAIL)
        print('Result:', f'{color} {result} {ENDC}')

        # check that phases are correct and allow for MV loads
        print('Checking that phases from transformer to load and source match:',
              flush=True)
        transformer_phase_res = check_transformer_phase_path(
            model, needs_transformers=False, verbose=True)
        if not transformer_phase_res:
            print('Attempting to fix phases from transformer to load and source',
                  flush=True)
            fix_transformer_phase_path(model, needs_transformers=False, verbose=True)
            transformer_phase_res = check_transformer_phase_path(
                model, needs_transformers=False, verbose=True)
        result, color = ('PASS', OKGREEN) if transformer_phase_res else ('FAIL', FAIL)
        print('Result:', f'{color} {result} {ENDC}')

        # if any of the previous tests failed, raise an error
        final_pass = all((loops_res, loads_connected_res, unique_path_res,
                          matched_phases_res, transformer_phase_res))
        if not final_pass:
            raise ValueError("Geojson file input structure incorrect")

        # autosize the transformers if this specified
        if self.upgrade_transformers:
            print('Upgrading undersized transformers:', flush=True)
            fix_undersized_transformers(model, verbose=True)

        # set up the directories into which the results will be written
        dss_files_path = os.path.join(self.dss_analysis, 'dss_files')
        dss_json_path = os.path.join(self.dss_analysis, 'json_files')
        results_path = os.path.join(self.dss_analysis, 'results')
        features_path = os.path.join(results_path, 'Features')
        trans_path = os.path.join(results_path, 'Transformers')
        lines_path = os.path.join(results_path, 'Lines')
        all_path = (dss_files_path, dss_json_path, features_path, trans_path, lines_path)
        for out_dir in all_path:
            os.makedirs(out_dir, exist_ok=True)

        # write the OpenDSS files and the JSON formatted files
        writer = Writer(output_path=dss_files_path,
                        split_feeders=False, split_substations=False)
        writer.write(model)
        json_writer = JSONWriter(output_path=dss_json_path)
        json_writer.write(model)

        # read the timestamps and compute the simulation interval
        timestamp_file = os.path.join(self.timeseries_location, 'timestamps.csv')
        ts = pd.read_csv(timestamp_file, header=0)
        dt_format = '%Y/%m/%d %H:%M:%S'
        delta = datetime.strptime(ts.loc[1]['Datetime'], dt_format) - \
            datetime.strptime(ts.loc[0]['Datetime'], dt_format)
        interval = delta.seconds / 3600.0
        stepsize = 60 * interval

        # get a map from the electrical junctions to buildings
        geojson_content = []
        try:
            with open(self.geojson_file, 'r') as f:
                geojson_content = json.load(f)
        except Exception:
            raise IOError("Problem trying to read json from file " + self.geojson_file)
        building_map = {}
        for element in geojson_content["features"]:
            if 'properties' in element and 'type' in element['properties'] and \
                    'buildingId' in element['properties'] and \
                    element['properties']['type'] == 'ElectricalJunction':
                building_map[element['properties']['id']] = \
                    element['properties']['buildingId']

        # process the start time and end time into indices
        print('\nSETTING UP SIMULATION')
        no_warn = 'Warning - Specified {} time of {} not found in timeseries file {}. {}'
        dup_warn = 'Warning - Specified {} time of {} has duplicate entries in ' \
            'timeseries file {}. {}'
        all_t = 'Using default value...'
        found_msg = 'Specified {} time of {} found in timeseries file'
        start_index, end_index = 0, len(ts)
        start_time, end_time = ts.loc[0]['Datetime'], ts.loc[end_index - 1]['Datetime']
        if self.start_time is not None:
            start_index_entry = ts.Datetime[ts.Datetime == self.start_time].index
            if len(start_index_entry) == 1:
                print(found_msg.format('start', self.start_time))
                start_index, start_time = start_index_entry[0], self.start_time
            elif len(start_index_entry) == 0:
                print(no_warn.format('start', self.start_time, timestamp_file, all_t))
            else:
                print(dup_warn.format('start', self.start_time, timestamp_file, all_t))
        if self.end_time is not None:
            end_index_entry = ts.Datetime[ts.Datetime == self.end_time].index
            if len(end_index_entry) == 1:
                print(found_msg.format('end', self.end_time))
                end_index, end_time = end_index_entry[0] + 1, self.end_time
            elif len(end_index_entry) == 0:
                print(no_warn.format('end', self.end_time, timestamp_file, all_t))
            else:
                print(dup_warn.format('end', self.end_time, timestamp_file, all_t))
        print(f'Running from {start_time} to {end_time}:')

        # process the step size into an integer
        if self.timestep is None or not (isinstance(self.timestep, (int, float))):
            print(f'Using default timestep of {stepsize} minutes')
            self.timestep = stepsize
        else:
            if not self.timestep % stepsize == 0:
                raise ValueError(
                    'Timestep {} is not a multiple of the electrical load file step '
                    'size of {}'.format(self.timestep, stepsize))
            print(f'Using timestep of {self.timestep} minutes')

        # setup dictionaries to hold the results
        voltage_df_dic = {}
        line_df_dic = {}
        transformer_df_dic = {}

        # begin running the simulation
        print('\nBEGINNING SIMULATION')
        # setup template strings for OpenDSS commands
        master_dss = os.path.join(self.dss_analysis, 'dss_files', 'Master.dss')
        redirect_cmd = 'Redirect {}'.format(master_dss)
        solve_cmd = 'Solve mode=yearly stepsize={}m number=1 hour={} sec={}'
        # setup the column in the result data frames
        bldg_columns = ['Datetime', 'p.u. voltage', 'overvoltage', 'undervoltage']
        line_columns = ['Datetime', 'p.u. loading', 'overloaded']
        trans_columns = ['Datetime', 'p.u. loading', 'overloaded']
        # loop through the timesteps and compute power flow
        for i in range(start_index, end_index, int(self.timestep / stepsize)):
            # simulate conditions at the time point
            time = ts.loc[i]['Datetime']
            print('Timepoint:', time, flush=True)
            hour = int(i / (1 / (self.timestep / 60.0)))
            seconds = (i % (1 / (self.timestep / 60.0))) * 3600
            dss.run_command('Clear')
            output1 = dss.run_command(redirect_cmd)
            if output1:
                print(output1)
            output2 = dss.run_command(solve_cmd.format(self.timestep, hour, seconds))
            if output2:
                print(output2)
            voltages = self._get_all_voltages()
            line_overloads = self._get_line_loading()
            overloaded_xfmrs = self._get_xfmr_overloads()

            # if this is the first timestep, setup the data frames
            if i == start_index:
                for element in voltages:
                    try:
                        voltage_df_dic[building_map[element]] = \
                            pd.DataFrame(columns=bldg_columns)
                    except KeyError:  # element is not a building
                        pass
                for element in line_overloads:
                    line_df_dic[element] = pd.DataFrame(columns=line_columns)
                for element in overloaded_xfmrs:
                    transformer_df_dic[element] = pd.DataFrame(columns=trans_columns)

            # record the OpenDSS results in dictionaries
            for element in voltages:
                if element not in building_map:
                    continue
                volt_val = voltages[element]
                voltage_df_dic[building_map[element]].loc[i] = \
                    [time, volt_val, volt_val > 1.05, volt_val < 0.95]
            for element in line_overloads:
                line_load_val = line_overloads[element]
                line_df_dic[element].loc[i] = \
                    [time, line_load_val, line_load_val > 1.0]
            for element in overloaded_xfmrs:
                xfrm_load_val = overloaded_xfmrs[element]
                transformer_df_dic[element].loc[i] = \
                    [time, xfrm_load_val, xfrm_load_val > 1.0]

        # write the collected results into CSV files
        for element, result_values in voltage_df_dic.items():
            res_path = os.path.join(features_path, '{}.csv'.format(element))
            result_values.to_csv(res_path, header=True, index=False)
        for element, result_values in line_df_dic.items():
            res_path = os.path.join(lines_path, '{}.csv'.format(element))
            result_values.to_csv(res_path, header=True, index=False)
        for element, result_values in transformer_df_dic.items():
            res_path = os.path.join(trans_path, '{}.csv'.format(element))
            result_values.to_csv(res_path, header=True, index=False)
