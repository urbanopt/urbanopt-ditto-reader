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
from ditto.store import Store
from ditto.writers.opendss.write import Writer
from ditto.writers.json.write import Writer as JSONWriter

from ditto.consistency.check_loops import check_loops
from ditto.consistency.check_loads_connected import check_loads_connected
from ditto.consistency.check_unique_path import check_unique_path
from ditto.consistency.check_matched_phases import check_matched_phases
from ditto.consistency.check_transformer_phase_path import check_transformer_phase_path

from ditto.consistency.fix_transformer_phase_path import fix_transformer_phase_path
from ditto.consistency.fix_undersized_transformers import fix_undersized_transformers

from urbanopt_ditto_reader.reader.read import Reader


def run(self):

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
    # Allowing MV loads
    transformer_phase_res = check_transformer_phase_path(model,needs_transformers=False, verbose=True)

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
        fix_transformer_phase_path(model,needs_transformers=False, verbose=True)
        transformer_phase_res = check_transformer_phase_path(model,needs_transformers=False, verbose=True)
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
    if not os.path.exists(os.path.join(self.dss_analysis, 'json_files')):
        os.makedirs(os.path.join(self.dss_analysis, 'json_files'), exist_ok=True)

    writer = Writer(output_path=os.path.join(self.dss_analysis, 'dss_files'), split_feeders=False, split_substations=False)
    writer.write(model)

    # write in JSON format as well
    json_writer = JSONWriter(output_path=os.path.join(self.dss_analysis, 'json_files'))
    json_writer.write(model)

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
        print(output1)
        output2 = dss.run_command("Solve mode=yearly stepsize="+str(self.timestep)+"m number=1 hour="+str(hour)+" sec="+str(seconds))
        print(output2)
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
