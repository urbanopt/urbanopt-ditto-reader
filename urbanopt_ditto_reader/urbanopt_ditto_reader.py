"""
****************************************************************************************************
:copyright (c) 2019-2021 URBANopt, Alliance for Sustainable Energy, LLC, and other contributors.
All rights reserved.
Redistribution and use in source and binary forms, with or without modification, are permitted
provided that the following conditions are met:
Redistributions of source code must retain the above copyright notice, this list of conditions
and the following disclaimer.
Redistributions in binary form must reproduce the above copyright notice, this list of conditions
and the following disclaimer in the documentation and/or other materials provided with the
distribution.
Neither the name of the copyright holder nor the names of its contributors may be used to endorse
or promote products derived from this software without specific prior written permission.
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR
IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER
IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT
OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
****************************************************************************************************
"""

import datetime
import json
import math
import os
from pathlib import Path
import pandas as pd
import opendssdirect as dss


class UrbanoptDittoReader(object):
    def __init__(self, config_data={}):

        self.module_path = Path(__file__).parent.parent

        # load default config from config.json
        default_data = self.default_config()

        # merge with whatever came in on config_data
        config = {**default_data, **config_data}

        print("CONFIGS used: {}".format(config))

        self.geojson_file = str(Path(config['urbanopt_geojson_file']).expanduser().resolve())
        self.urbanopt_scenario_name = Path(config['urbanopt_scenario_file']).stem
        self.urbanopt_scenario = str(Path(config['urbanopt_scenario_file']).expanduser().parent / 'run' / self.urbanopt_scenario_name)
        self.equipment_file = str(Path(config['equipment_file']).expanduser().resolve())
        self.dss_analysis = str(Path(config['opendss_folder']).expanduser().resolve())
        self.use_reopt = config['use_reopt']
        self.start_time = None
        self.end_time = None
        self.timestep = None
        if 'timestep' in config:
            self.timestep = config['timestep']
        if 'start_time' in config and 'end_time' in config:
            self.start_time = str(config['start_time'])
            self.end_time = str(config['end_time'])
        else:
            print('No start_time and end_time provided. Running all timepoints')

        self.upgrade_transformers = False
        if 'upgrade_transformers' in config:
            self.upgrade_transformers = config['upgrade_transformers']


        self.timeseries_location = os.path.join(self.dss_analysis, 'profiles')

    def default_config(self):
        """Read default config file"""
        example_config_file = Path(__file__).parent / 'example_config.json'
        with open(example_config_file) as f:
            default_data = self.fix_paths(json.load(f))
        return default_data

    def fix_paths(self, data):
        """Fix data to be relative path wrt this module"""
        for k, v in data.items():
            if k == 'use_reopt' or k == 'start_time' or k == 'end_time' or k == 'timestep' or k == 'upgrade_transformers':
                continue
            elif not Path(v).is_absolute():
                data[k] = str(Path(self.module_path) / v)
        return data

    def _get_all_voltages(self):
        """Computes over and under voltages for all buses"""
        voltage_dict = {}
        bus_names = dss.Circuit.AllBusNames()
        for b in bus_names:
            dss.Circuit.SetActiveBus(b)
            vang = dss.Bus.puVmagAngle()
            if len(vang[::2]) > 0:
                vmag = sum(vang[::2])/len(vang)
            else:
                vmag = 0
            voltage_dict[b] = vmag*2

        return voltage_dict

    def _get_line_loading(self):
        """Computes the loading for Lines."""

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
            phase = int(.5*len(dss.CktElement.Currents()))
            line_current = [math.sqrt(dss.CktElement.Currents()[2*(ii-1)+2]**2 + dss.CktElement.Currents()[2*ii+1]**2) for ii in range(phase)]

            # The loading is the ratio of the two
            ldg = max(line_current)/float(line_limit)
            line_overloads_dict[line_name] = max(line_current)/float(line_limit)

            # Move on to the next line
            flag = dss.ActiveClass.Next()
        return line_overloads_dict

    def _get_xfmr_overloads(self, ub=1.0):

        #####################################
        #    Transformer current violations
        #####################################
        #
        transformer_violation_dict = {}
        dss.Circuit.SetActiveClass("Transformer")
        flag = dss.ActiveClass.First()
        while flag > 0:
            # Get the name of the Transformer
            transformer_name = dss.CktElement.Name()
            transformer_current = []

            # transformer_limit = dss.CktElement.NormalAmps()

            hs_kv = float(dss.Properties.Value('kVs').split('[')[1].split(',')[0])
            kva = float(dss.Properties.Value('kVA'))
            n_phases = dss.CktElement.NumPhases()
            if n_phases > 1:
                transformer_limit_per_phase = kva/(hs_kv*math.sqrt(3))
            else:
                transformer_limit_per_phase = kva/hs_kv

            # nwindings = int(dss.Properties.Value("windings"))
            primary_bus = dss.Properties.Value("buses").split('[')[1].split(',')[0]

            # phase = int((len(dss.CktElement.Currents())/(nwindings*2.0)))
            Currents = dss.CktElement.CurrentsMagAng()[:2*n_phases]
            Current_magnitude = Currents[::2]

            transformer_current = Current_magnitude

            # Compute the loading
            ldg = max(transformer_current)/transformer_limit_per_phase
            transformer_violation_dict[transformer_name] = ldg

            # Move on to the next Transformer...
            flag = dss.ActiveClass.Next()

        return transformer_violation_dict

    def run(self):

        from ditto.store import Store
        from ditto.writers.opendss.write import Writer
        from urbanopt_ditto_reader.reader.read import Reader

        from ditto.consistency.check_loops import check_loops
        from ditto.consistency.check_loads_connected import check_loads_connected
        from ditto.consistency.check_unique_path import check_unique_path
        from ditto.consistency.check_matched_phases import check_matched_phases
        from ditto.consistency.check_transformer_phase_path import check_transformer_phase_path

        from ditto.consistency.fix_transformer_phase_path import fix_transformer_phase_path
        from ditto.consistency.fix_undersized_transformers import fix_undersized_transformers

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

        OKGREEN='\033[92m'
        FAIL = '\033[91m'
        ENDC = '\033[0m'

        final_pass = True

        print('Check no loops:',flush=True)
        loops_res = check_loops(model,verbose=True)
        final_pass = final_pass and loops_res
        result = 'FAIL'
        color = FAIL
        if loops_res:
            result = 'PASS'
            color = OKGREEN
        print('Result:', f'{color} {result} {ENDC}')
        print()

        print('Check loads connected to source:',flush=True)
        result = 'FAIL'
        color = FAIL
        loads_connected_res = check_loads_connected(model,verbose=True)
        final_pass = final_pass and loads_connected_res
        if loads_connected_res:
            result = 'PASS'
            color = OKGREEN
        print('Result:', f'{color} {result} {ENDC}')
        print()

        print('Check unique path from each load to source:',flush=True)
        unique_path_res = check_unique_path(model,show_all=True,verbose=True)
        final_pass = final_pass and unique_path_res
        result = 'FAIL'
        color = FAIL
        if unique_path_res:
            result = 'PASS'
            color = OKGREEN
        print('Result:', f'{color} {result} {ENDC}')
        print()

        print('Check that phases on either side of transformer are correct:',flush=True)
        matched_phases_res = check_matched_phases(model,verbose=True)
        final_pass = final_pass and check_matched_phases
        result = 'FAIL'
        color = FAIL
        if matched_phases_res:
            result = 'PASS'
            color = OKGREEN
        print('Result:', f'{color} {result} {ENDC}')
        print()

        print('Check that phases from transformer to load and source are correct:',flush=True)
        transformer_phase_res = check_transformer_phase_path(model,needs_transformers=True, verbose=True)

        # don't do check here - see if we can fix it first
        #final_pass = final_pass and transformer_phase_res
        result = 'FAIL'
        color = FAIL
        if transformer_phase_res:
            result = 'PASS'
            color = OKGREEN

        #print('Result:', f'{color} {result} {ENDC}')
        print()

        print('Attempting to fix phases from transformer to load and source', flush=True)
        if result == 'FAIL':
            fix_transformer_phase_path(model,needs_transformers=True, verbose=True)
            transformer_phase_res = check_transformer_phase_path(model,needs_transformers=True, verbose=True)
            final_pass = final_pass and transformer_phase_res
            result = 'FAIL'
            color = FAIL
            if transformer_phase_res:
                result = 'PASS'
                color = OKGREEN
            print('Result:', f'{color} {result} {ENDC}')
            print()

        if self.upgrade_transformers:
            print('Upgrading undersized transformers:',flush=True)
            fix_undersized_transformers(model,verbose=True)


        if not final_pass:
            raise ValueError("Geojson file input structure incorrect")

        if not os.path.exists(os.path.join(self.dss_analysis, 'dss_files')):
            os.makedirs(os.path.join(self.dss_analysis, 'dss_files'), exist_ok=True)
        if not os.path.exists(os.path.join(self.dss_analysis, 'results', 'Features')):
            os.makedirs(os.path.join(self.dss_analysis, 'results', 'Features'), exist_ok=True)
        if not os.path.exists(os.path.join(self.dss_analysis, 'results', 'Transformers')):
            os.makedirs(os.path.join(self.dss_analysis, 'results', 'Transformers'), exist_ok=True)
        if not os.path.exists(os.path.join(self.dss_analysis, 'results', 'Lines')):
            os.makedirs(os.path.join(self.dss_analysis, 'results', 'Lines'), exist_ok=True)

        writer = Writer(output_path=os.path.join(self.dss_analysis, 'dss_files'), split_feeders=False, split_substations=False)
        writer.write(model)

        ts = pd.read_csv(os.path.join(self.timeseries_location, 'timestamps.csv'), header=0)
        number_iterations = len(ts)

        voltage_df_dic = {}
        line_df_dic = {}
        transformer_df_dic = {}

        delta = datetime.datetime.strptime(ts.loc[1]['Datetime'], '%Y/%m/%d %H:%M:%S') - datetime.datetime.strptime(ts.loc[0]['Datetime'], '%Y/%m/%d %H:%M:%S')
        interval = delta.seconds/3600.0
        stepsize = 60*interval
        building_map = {}

        geojson_content = []
        try:
            with open(self.geojson_file, 'r') as f:
                geojson_content = json.load(f)
        except:
            raise IOError("Problem trying to read json from file " + self.geojson_file)

        for element in geojson_content["features"]:
            if 'properties' in element and 'type' in element['properties'] and 'buildingId' in element['properties'] and element['properties']['type'] == 'ElectricalJunction':
                building_map[element['properties']['id']] = element['properties']['buildingId']

        if self.start_time is not None and self.end_time is not None:
            print(f'Attempting to run from {self.start_time} to {self.end_time}:')
        else:
            print('Running for all timepoints:')

        start_index_entry = ts.Datetime[ts.Datetime==self.start_time].index
        if len(start_index_entry) == 0:
            print(f'Warning - start time of {self.start_time} not found in timeseries file {os.path.join(self.timeseries_location, "timestamps.csv")}. Running for all times...')
            start_index = 0
        if len(start_index_entry) >1:
            print(f'Warning - start time of {self.start_time} has duplicate entries in timeseries file {os.path.join(self.timeseries_location, "timestamps.csv")}. Running for all times...')
            start_index = 0
        if len(start_index_entry) ==1:
            print(f'Unique starting time of {self.start_time} found')
            start_index = start_index_entry[0]

        end_index_entry = ts.Datetime[ts.Datetime==self.end_time].index
        if len(end_index_entry) == 0:
            print(f'Warning - end time of {self.end_time} not found in timeseries file {os.path.join(self.timeseries_location, "timestamps.csv")}. Running for all times...')
            end_index = len(ts)
        if len(end_index_entry) >1:
            print(f'Warning - end time of {self.end_time} has duplicate entries in timeseries file {os.path.join(self.timeseries_location, "timestamps.csv")}. Running for all times...')
            end_index = len(ts) 
        if len(end_index_entry) ==1:
            print(f'Unique ending time of {self.end_time} found')
            end_index = end_index_entry[0]+1

        if self.timestep is None or not (isinstance(self.timestep,float) or isinstance(self.timestep,int)):
            print(f'Using default timestep of {stepsize} minutes')
            self.timestep = stepsize
        else:
            if not self.timestep%stepsize == 0:
                raise ValueError(f"Timestep {self.timestep} is not a multiple of the loadfile step size of {stepsize}")
            print(f'Using timestep of {self.timestep} minutes')
        for i in range(start_index,end_index,int(self.timestep/stepsize)):
            time = ts.loc[i]['Datetime']
            print('Timepoint:',time,flush=True)
            hour = int(i/(1/(self.timestep/60.0)))
            seconds = (i % (1/(self.timestep/60.0)))*3600
            location = os.path.join(self.dss_analysis, 'dss_files', 'Master.dss')
            dss.run_command("Clear")
            output1 = dss.run_command("Redirect "+location)
            output2 = dss.run_command("Solve mode=yearly stepsize="+str(self.timestep)+"m number=1 hour="+str(hour)+" sec="+str(seconds))
            voltages = self._get_all_voltages()
            line_overloads = self._get_line_loading()
            overloaded_xfmrs = self._get_xfmr_overloads()

            for element in voltages:
                if element not in building_map:
                    continue
                building_id = building_map[element]
                if building_id not in voltage_df_dic:
                    voltage_df_dic[building_id] = pd.DataFrame(columns=['Datetime', 'p.u. voltage', 'overvoltage', 'undervoltage'])
                voltage_df_dic[building_id].loc[i] = [time, voltages[element], voltages[element] > 1.05, voltages[element] < 0.95]
            for element in line_overloads:
                if element not in line_df_dic:
                    line_df_dic[element] = pd.DataFrame(columns=['Datetime', 'p.u. loading', 'overloaded'])
                line_df_dic[element].loc[i] = [time, line_overloads[element], line_overloads[element] > 1.0]
            for element in overloaded_xfmrs:
                if element not in transformer_df_dic:
                    transformer_df_dic[element] = pd.DataFrame(columns=['Datetime', 'p.u. loading', 'overloaded'])
                transformer_df_dic[element].loc[i] = [time, overloaded_xfmrs[element], overloaded_xfmrs[element] > 1.0]

        for element in voltage_df_dic:
            voltage_df_dic[element].to_csv(os.path.join(self.dss_analysis, 'results', 'Features', element+'.csv'), header=True, index=False)
        for element in line_df_dic:
            line_df_dic[element].to_csv(os.path.join(self.dss_analysis, 'results', 'Lines', element+'.csv'), header=True, index=False)
        for element in transformer_df_dic:
            transformer_df_dic[element].to_csv(os.path.join(self.dss_analysis, 'results', 'Transformers', element+'.csv'), header=True, index=False)
