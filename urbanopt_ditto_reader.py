"""
****************************************************************************************************
URBANopt™, Copyright (c) 2019-2020, Alliance for Sustainable Energy, LLC, and other contributors.
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

import sys
import datetime
import json
import math
import os
import pandas as pd
import opendssdirect as dss


class UrbanoptDittoReader(object):
    def __init__(self, config_data={}):

        self.module_path = os.path.dirname(os.path.realpath(__file__))

        # load default config from config.json
        default_data = self.default_config()

        # make sure all paths are absolute wrt this module file
        config_data = self.fix_paths(config_data)

        # merge with whatever came in on config_data
        config = {**default_data, **config_data}

        print("CONFIGS used: {}".format(config))

        self.geojson_file = os.path.abspath(config['geojson_file'])
        self.urbanopt_scenario = os.path.abspath(config['urbanopt_scenario'])
        self.equipment_file = os.path.abspath(config['equipment_file'])
        self.dss_analysis = os.path.abspath(config['opendss_folder'])
        self.ditto_folder = os.path.abspath(config['ditto_folder'])
        self.use_reopt = config['use_reopt']

        self.timeseries_location = os.path.join(self.dss_analysis, 'profiles')

    def default_config(self):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        data = open(os.path.join(dir_path, 'config.json'))
        default_data = json.load(data)

        # fix data to be relative path wrt this module
        default_data = self.fix_paths(default_data)

        data.close()
        return default_data

    def fix_paths(self, data):

        # fix data to be relative path wrt this module
        for k, v in data.items():
            if k == 'use_reopt':
                continue
            elif not os.path.isabs(v):
                data[k] = os.path.join(self.module_path, v)
                # print("warning: {} is not a full path, using path: {}".format(k, default_data[k]))

        return data

    def _get_all_voltages(self):
        """Computes over and under voltages for all buses"""
        voltage_dict = {}
        # vmag_pu = dss.Circuit.AllBusMagPu()
        # print(len(vmag_pu))
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

        # relative import (relative to THIS MODULE)
        if os.path.isabs(self.ditto_folder):
            # keep it
            df = self.ditto_folder
        else:
            df = os.path.join(os.path.dirname(os.path.realpath(__file__)), self.ditto_folder)

        sys.path.insert(0, df)  # don't append in case there are other multiple DiTTo installations.

        from ditto.store import Store
        from ditto.writers.opendss.write import Writer
        from reader.read import Reader

        model = Store()

        reader = Reader(geojson_file=self.geojson_file, equipment_file=self.equipment_file, load_folder=self.urbanopt_scenario, use_reopt=self.use_reopt, is_timeseries=True, timeseries_location=self.timeseries_location, relative_timeseries_location=os.path.join('..', 'profiles'))
        reader.parse(model)

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

        for i, row in ts.iterrows():
            time = row['Datetime']
            print(i, flush=True)
            hour = int(i/(1/interval))
            seconds = (i % (1/interval))*3600
            location = os.path.join(self.dss_analysis, 'dss_files', 'Master.dss')
            dss.run_command("Clear")
            dss.run_command("Redirect "+location)
            dss.run_command("Solve mode=yearly stepsize="+str(stepsize)+"m number=1 hour="+str(hour)+" sec="+str(seconds))
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
