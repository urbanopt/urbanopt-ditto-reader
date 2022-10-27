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
import opendssdirect as dss

from ditto.store import Store
from ditto.readers.opendss import OpenDSSReader
from ditto.writers.opendss.write import Writer
from ditto.writers.json.write import Writer as JSONWriter

from ditto.consistency.check_loops import check_loops
from ditto.consistency.check_loads_connected import check_loads_connected
from ditto.consistency.check_unique_path import check_unique_path
from ditto.consistency.check_matched_phases import check_matched_phases
from ditto.consistency.check_transformer_phase_path import check_transformer_phase_path
from ditto.consistency.fix_transformer_phase_path import fix_transformer_phase_path
from ditto.consistency.fix_undersized_transformers import fix_undersized_transformers

from urbanopt_ditto_reader.reader import UrbanoptReader


class UrbanoptDittoReader(object):
    """A class for running OpenDSS simulation using URBANopt results.

    Args:
        config_data: An optional dictionary to specify the configuration parameters.

    Properties:
        * geojson_file
        * urbanopt_scenario_name
        * urbanopt_scenario
        * equipment_file
        * rnm_results
        * dss_analysis
        * use_reopt
        * start_time
        * end_time
        * timestep
        * upgrade_transformers
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
        self.rnm_results = os.path.join(
            self.urbanopt_scenario, 'rnm-us', 'results', 'OpenDSS')
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

    @staticmethod
    def _get_all_voltages():
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

    @staticmethod
    def _get_line_loading():
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

    @staticmethod
    def _get_xfmr_overloads(ub=1.0):
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

    @staticmethod
    def _load_json_content(json_file):
        """Load the content of a JSON file to a dictionary."""
        try:
            with open(json_file, 'r') as f:
                file_content = json.load(f)
            return file_content
        except Exception:
            raise IOError(
                'Problem trying to read json from file "{}".'.format(json_file))

    def check_model(self, model):
        """Check a Ditto Model using routines within DiTTo.

        Args:
            model: A DiTTo model to be validated using DiTTo routines.
        """
        # variables for reporting the status of tests
        OKGREEN = '\033[92m'
        FAIL = '\033[91m'
        ENDC = '\033[0m'

        # perform several checks on the model and report results
        print('\nCHECKING MODEL')
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
        result, color = ('PASS', OKGREEN) if transformer_phase_res \
            else ('FAIL', FAIL)
        print('Result:', f'{color} {result} {ENDC}')

        # if any of the previous tests failed, raise an error
        final_pass = all((loops_res, loads_connected_res, unique_path_res,
                          matched_phases_res, transformer_phase_res))
        if not final_pass:
            raise ValueError('Invalid OpenDSS input.')

    def upgrade_model_transformers(self, model):
        """Automatically upgrade any undersized transformers in a Ditto Model.

        Args:
            model: A DiTTo model to have its transformers upgraded.
        """
        print('Upgrading undersized transformers:', flush=True)
        fix_undersized_transformers(model, verbose=True)

    def write_opendss_files(self, model):
        """Write out OpenDSS files from a DiTTo model.

        This includes both the DSS files and the JSON representation of the files.
        Files will be written using the dss_analysis property on this object instance.

        Args:
            model: A DiTTo model, which will be written to OpenDSS files.

        Returns:
            The path to the master file, which can be used to execute the OpenDSS
            simulation.
        """
        dss_files_path = os.path.join(self.dss_analysis, 'dss_files')
        dss_json_path = os.path.join(self.dss_analysis, 'json_files')
        for out_dir in (dss_files_path, dss_json_path):
            os.makedirs(out_dir, exist_ok=True)
        writer = Writer(output_path=dss_files_path,
                        split_feeders=False, split_substations=False)
        writer.write(model)
        json_writer = JSONWriter(output_path=dss_json_path)
        json_writer.write(model)
        return os.path.join(self.dss_analysis, 'dss_files', 'Master.dss')

    def run(self, master_file):
        """Run an OpenDSS simulation using a master DSS file.

        Note that the timeseries_location property on this class must contain a
        timestamps CSV file in order for this simulation to run successfully. Result
        CSVs will be written to the dss_analysis folder on this object instance.

        Args:
            master_file: The path to the master DSS file to which the simulation
                will be redirected for simulation.
        """
        # set up the directories into which the results will be written
        results_path = os.path.join(self.dss_analysis, 'results')
        features_path = os.path.join(results_path, 'Features')
        trans_path = os.path.join(results_path, 'Transformers')
        lines_path = os.path.join(results_path, 'Lines')
        all_path = (features_path, trans_path, lines_path)
        for out_dir in all_path:
            os.makedirs(out_dir, exist_ok=True)

        # read the timestamps and compute the simulation interval
        timestamp_file = os.path.join(self.timeseries_location, 'timestamps.csv')
        ts = self._read_single_column_csv(timestamp_file)
        ts.pop(0)  # remove the header
        dt_format = '%Y/%m/%d %H:%M:%S'
        delta = datetime.strptime(ts[1], dt_format) - datetime.strptime(ts[0], dt_format)
        interval = delta.seconds / 3600.0
        stepsize = 60 * interval

        # get a map from the electrical junctions to buildings
        building_map = {}
        # first, look up the junctions and buildings in the feature GeoJSON
        geojson_content = self._load_json_content(self.geojson_file)
        if 'features' in geojson_content:
            for element in geojson_content['features']:
                if 'properties' in element and 'type' in element['properties'] and \
                        element['properties']['type'] == 'ElectricalJunction' and \
                        'buildingId' in element['properties']:
                    building_map[element['properties']['id']] = \
                        element['properties']['buildingId']
        # if nothing is found, try looking for an RNM output GeoJSON
        if building_map == {} and os.path.isdir(self.rnm_results):
            rnm_parent = os.path.split(self.rnm_results)[0]
            rnm_json = os.path.join(rnm_parent, 'GeoJSON', 'Distribution_system.json')
            if os.path.isfile(rnm_json):
                bldg_set = {}
                rnm_json_content = self._load_json_content(rnm_json)
                if 'features' in rnm_json_content:
                    for element in rnm_json_content['features']:
                        if 'properties' in element and 'type' in element['properties'] \
                                and element['properties']['type'] == 'Consumer' and \
                                'Node' in element['properties']:
                            node_id = element['properties']['Node']
                            bldg_id = '_'.join(node_id.split('_')[:-1])
                            if bldg_id in bldg_set:  # more than 1 node per building
                                old_node_id = bldg_set[bldg_id]
                                building_map[old_node_id.lower()] = old_node_id
                                building_map[node_id.lower()] = node_id
                            else:
                                building_map[node_id.lower()] = bldg_id
                                bldg_set[bldg_id] = node_id

        # process the start time and end time into indices
        print('\nSETTING UP SIMULATION')
        no_warn = 'Warning - Specified {} time of {} not found in timeseries file {}. {}'
        all_t = 'Using default value...'
        found_msg = 'Specified {} time of {} found in timeseries file'
        start_index, end_index = 0, len(ts)
        start_time, end_time = ts[0], ts[end_index - 1]
        if self.start_time is not None:
            try:
                start_index = ts.index(self.start_time)
                print(found_msg.format('start', self.start_time))
                start_time = self.start_time
            except ValueError:
                print(no_warn.format('start', self.start_time, timestamp_file, all_t))
        if self.end_time is not None:
            try:
                end_index = ts.index(self.end_time) + 1
                print(found_msg.format('end', self.end_time))
                end_time = self.end_time
            except ValueError:
                print(no_warn.format('end', self.end_time, timestamp_file, all_t))
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
        dss.run_command('Clear')
        # redirect the simulation to the master file
        master_dss = os.path.join(self.dss_analysis, 'dss_files', 'Master.dss') \
            if master_file is None else master_file
        redirect_cmd = 'Redirect {}'.format(master_dss)
        redirect_output = dss.run_command(redirect_cmd)
        if redirect_output:
            print(redirect_output)
        # set up the template of the command to solve for a timestep
        solve_cmd = 'Solve mode=yearly stepsize={}m number=1 hour={} sec={}'
        # setup the column in the result data frames
        bldg_columns = ['Datetime', 'p.u. voltage', 'overvoltage', 'undervoltage']
        line_columns = ['Datetime', 'p.u. loading', 'overloaded']
        trans_columns = ['Datetime', 'p.u. loading', 'overloaded']
        # loop through the timesteps and compute power flow
        for i in range(start_index, end_index, int(self.timestep / stepsize)):
            # simulate conditions at the time point
            time = ts[i]
            print('Timepoint:', time, flush=True)
            hour = int(i / (1 / (self.timestep / 60.0)))
            seconds = (i % (1 / (self.timestep / 60.0))) * 3600
            output = dss.run_command(solve_cmd.format(self.timestep, hour, seconds))
            if output:
                print(output)
            voltages = self._get_all_voltages()
            line_overloads = self._get_line_loading()
            overloaded_xfmrs = self._get_xfmr_overloads()

            # if this is the first timestep, setup the dictionaries to hold outputs
            if i == start_index:
                for element in voltages:
                    try:
                        voltage_df_dic[building_map[element]] = [bldg_columns]
                    except KeyError:  # element is not a building
                        pass
                for element in line_overloads:
                    line_df_dic[element] = [line_columns]
                for element in overloaded_xfmrs:
                    transformer_df_dic[element] = [trans_columns]

            # record the OpenDSS results in dictionaries
            for element, volt_val in voltages.items():
                try:
                    voltage_df_dic[building_map[element]].append(
                        [time, volt_val, volt_val > 1.05, volt_val < 0.95])
                except KeyError:  # element is not a building
                    pass
            for element, line_load_val in line_overloads.items():
                line_df_dic[element].append(
                    [time, line_load_val, line_load_val > 1.0])
            for element, xfrm_load_val in overloaded_xfmrs.items():
                transformer_df_dic[element].append(
                    [time, xfrm_load_val, xfrm_load_val > 1.0])

        # write the collected results into CSV files
        for element, result_values in voltage_df_dic.items():
            res_path = os.path.join(features_path, '%s.csv' % element.replace(':', ''))
            self._write_csv(result_values, res_path)
        for element, result_values in line_df_dic.items():
            res_path = os.path.join(lines_path, '%s.csv' % element.replace(':', ''))
            self._write_csv(result_values, res_path)
        for element, result_values in transformer_df_dic.items():
            res_path = os.path.join(trans_path, '%s.csv' % element.replace(':', ''))
            self._write_csv(result_values, res_path)

    @staticmethod
    def _read_single_column_csv(csv_file_path):
        """Load a single columns CSV file into a Python matrix of strings.

        Args:
            csv_file_path: Full path to a valid CSV file.
        """
        mtx = []
        with open(csv_file_path) as csv_data_file:
            for row in csv_data_file:
                mtx.append(row.strip())
        return mtx

    @staticmethod
    def _read_csv(csv_file_path):
        """Load a single columns CSV file into a Python matrix of strings.

        Args:
            csv_file_path: Full path to a valid CSV file.
        """
        mtx = []
        with open(csv_file_path) as csv_data_file:
            for row in csv_data_file:
                mtx.append(row.split(','))
        return mtx

    @staticmethod
    def _write_single_column_csv(value_list, csv_file_path, header=None):
        """Write a Python list into a single-columns CSV file.

        Args:
            value_list: A Python List.
            csv_file_path: Full path to where the CSV file.
        """
        if header is not None:
            value_list.insert(0, header)
        with open(csv_file_path, 'w') as csv_data_file:
            for v in value_list:
                csv_data_file.write(str(v) + '\n')
        return csv_file_path

    @staticmethod
    def _write_csv(matrix, csv_file_path):
        """Write a Python matrix into a CSV file.

        Args:
            matrix: A Python Matrix (list of lists).
            csv_file_path: Full path to where the CSV file.
        """
        with open(csv_file_path, 'w') as csv_data_file:
            for row in matrix:
                csv_data_file.write(','.join(str(v) for v in row))
                csv_data_file.write('\n')
        return csv_file_path

    def run_rnm_opendss(self):
        """Run OpenDSS with DSS files output by URBANopt RNM."""
        # load the URBANopt files and use them to write a timestamps CSV
        print('\nRE-SERIALIZING MODEL')
        rep_csv = os.path.join(self.urbanopt_scenario, 'default_scenario_report.csv')
        report_mtx = self._read_csv(rep_csv)
        header_row = report_mtx.pop(0)
        ts_i = header_row.index('Datetime')
        timestamps = [row[ts_i] for row in report_mtx]
        ts_loc = self.timeseries_location
        if ts_loc is not None:
            if not os.path.exists(ts_loc):
                os.makedirs(ts_loc)
            ts_path = os.path.join(ts_loc, 'timestamps.csv')
            self._write_single_column_csv(timestamps, ts_path, 'Datetime')

        # build a model from the raw OpenDSS files output by RNM
        model = Store()
        master_file = os.path.join(self.rnm_results, 'dss_files', 'Master.dss')
        buscoordinates_file = os.path.join(self.rnm_results, 'dss_files', 'BusCoord.dss')
        reader = OpenDSSReader(
            master_file=master_file,
            buscoordinates_file=buscoordinates_file
        )
        reader.parse(model)

        # run the model through OpenDSS
        self.run(master_file)

    def run_urbanopt_geojson(self):
        """Run OpenDSS assuming that the GeoJSON contains detailed OpenDSS objects."""
        # load the OpenDSS model from the URBANopt files
        print('\nRE-SERIALIZING MODEL')
        model = Store()
        reader = UrbanoptReader(
            geojson_file=self.geojson_file,
            equipment_file=self.equipment_file,
            load_folder=self.urbanopt_scenario,
            use_reopt=self.use_reopt,
            is_timeseries=True,
            timeseries_location=self.timeseries_location,
            relative_timeseries_location=os.path.join('..', 'profiles')
        )
        reader.parse(model)

        # check the model and run it through OpenDSS
        self.check_model(model)
        if self.upgrade_transformers:
            self.upgrade_model_transformers(model)
        master_file = self.write_opendss_files(model)
        self.run(master_file)
