import json
import math
import os
import pandas as pd
import opendssdirect as dss
from ditto.store import Store
from ditto.writers.opendss.write import Writer
from ditto.readers.urbanopt_ditto_reader.read import Reader

def get_all_voltages():
    """Computes over and under voltages for all buses"""
    voltage_dict = {}
    #vmag_pu = dss.Circuit.AllBusMagPu()
    #print(len(vmag_pu))
    bus_names = dss.Circuit.AllBusNames()
    for b in bus_names:
        dss.Circuit.SetActiveBus(b)
        vang = dss.Bus.puVmagAngle()
        if len(vang[::2]) >0:
            vmag = sum(vang[::2])/len(vang)
        else:
            vmag = 0
        voltage_dict[b] = vmag*2

    return voltage_dict

def get_line_overloads():
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
        if ldg>1:
            line_overloads_dict[line_name] = max(line_current)/float(line_limit)
            
        # Move on to the next line
        flag = dss.ActiveClass.Next()
    return line_overloads_dict


def get_xfmr_overloads(ub=1.0):
    
    #####################################
    #    Transformer current violations
    #####################################
    #
    transformer_violation_dict ={}
    unloaded_transformers_dict = {}
    dss.Circuit.SetActiveClass("Transformer")
    flag = dss.ActiveClass.First()
    while flag > 0:
        # Get the name of the Transformer
        transformer_name = dss.CktElement.Name()
        transformer_current = []
        
        #transformer_limit = dss.CktElement.NormalAmps()
        
        
        hs_kv = float(dss.Properties.Value('kVs').split('[')[1].split(',')[0])
        kva = float(dss.Properties.Value('kVA'))
        n_phases = dss.CktElement.NumPhases()
        if n_phases>1:
            transformer_limit_per_phase = kva/(hs_kv*math.sqrt(3))
        else:
            transformer_limit_per_phase = kva/hs_kv
    
        #nwindings = int(dss.Properties.Value("windings"))
        primary_bus = dss.Properties.Value("buses").split('[')[1].split(',')[0]
        
        #phase = int((len(dss.CktElement.Currents())/(nwindings*2.0)))
        Currents = dss.CktElement.CurrentsMagAng()[:2*n_phases]
        Current_magnitude = Currents[::2]    
        
        transformer_current = Current_magnitude

        # Compute the loading
        ldg = max(transformer_current)/transformer_limit_per_phase
        
        # If the loading is more than 100%, store the violation
        if ldg > ub:
            transformer_violation_dict[transformer_name] = {'Bus': primary_bus, 'Loading (p.u.)': ldg, 'kVA' : kva, 'number_of_phases': n_phases}
        elif ldg == 0:
            unloaded_transformers_dict[transformer_name] = {'Bus': primary_bus, 'kVA' : kva, 'number_of_phases': n_phases}
        
        # Move on to the next Transformer...
        flag = dss.ActiveClass.Next()
    
      
    return transformer_violation_dict, unloaded_transformers_dict



def get_voltage_violations():
    """Computes over and under voltages for all buses"""
    overvoltages_dict = {}
    undervoltages_dict = {}
    #vmag_pu = dss.Circuit.AllBusMagPu()
    #print(len(vmag_pu))
    bus_names = dss.Circuit.AllBusNames()
    dss.PVsystems.Name('pv_load_p1ulv7544')
    for b in bus_names:
        dss.Circuit.SetActiveBus(b)
        vang = dss.Bus.puVmagAngle()
        maxv = max(vang[::2])
        minv = min(vang[::2])
        if maxv>1.05:
            overvoltages_dict[b] = maxv
        if minv<0.95:
            undervoltages_dict[b] = minv
    
    return undervoltages_dict, overvoltages_dict




base_folder = os.path.join('C:\\','Users','telgindy','Documents','Urbanopt')
geojson_file = os.path.join(base_folder,'urbanopt-example-geojson-project','example_electrical_with_sub_one_junction.json')
geojson_file = os.path.join(base_folder,'urbanopt-example-geojson-project','example_final_pretty.json')
equipment_file = os.path.join(base_folder,'urbanopt-example-geojson-project','electrical_database.json')
load_folder = os.path.join('C:\\','Users','telgindy','Documents','Urbanopt','baseline_scenario','baseline_scenario')
dss_analysis = os.path.join('C:\\','Users','telgindy','Documents','Urbanopt','baseline_scenario','opendss')
feature_file = os.path.join('C:\\','Users','telgindy','Documents','Urbanopt','baseline_scenario_old','baseline_scenario','baseline_features.json')

timeseries_location = 'profiles'
model = Store()
reader = Reader(geojson_file=geojson_file,equipment_file = equipment_file,load_folder = load_folder,feature_file = feature_file,is_timeseries = True, timeseries_location = timeseries_location, relative_timeseries_location = os.path.join('..','profiles'))
reader.parse(model)

#from ditto.modify.system_structure import system_structure_modifier
#model.set_names()
#modifier = system_structure_modifier(model,"source")
#modifier.set_nominal_voltages()

writer = Writer(output_path = 'output',split_feeders=False,split_substations=False)
writer.write(model)

ts = pd.read_csv(os.path.join(timeseries_location,'timestamps.csv'),header=0)
number_iterations = len(ts)
voltages_dict = {}
overvoltages_dict = {}
undervoltages_dict = {}
line_overloads_dict = {}
transformer_overloads_dict = {}
for i, row in ts.iterrows():
    #if i>10:
    #    break
    time = row['Datetime']
    print(i,flush=True)
    hour = int(i/4)
    seconds = (i%4)*3600
    dss.run_command("Clear")
    dss.run_command("Redirect output/Master.dss")
    dss.run_command("Solve mode=yearly stepsize=15m number=1 hour="+str(hour)+" sec="+str(seconds))
    voltages = get_all_voltages()
    line_overloads = get_line_overloads()
    undervoltages,overvoltages = get_voltage_violations()
    overloaded_xfmrs, unloaded_xfmrs = get_xfmr_overloads()

    voltages_dict[time] = voltages
    overvoltages_dict[time] = overvoltages
    undervoltages_dict[time] = undervoltages
    line_overloads_dict[time] = line_overloads
    transformer_overloads_dict[time] = overloaded_xfmrs
if not os.path.exists(dss_analysis):
    os.makedirs(dss_analysis)
with open(os.path.join(dss_analysis,'all_voltages.json'),'w') as fp:
    json.dump(voltages_dict,fp,indent=4, sort_keys=True)
with open(os.path.join(dss_analysis,'overvoltages.json'),'w') as fp:
    json.dump(overvoltages_dict,fp,indent=4, sort_keys=True)
with open(os.path.join(dss_analysis,'undervoltages.json'),'w') as fp:
    json.dump(undervoltages_dict,fp,indent=4, sort_keys=True)
with open(os.path.join(dss_analysis,'line_overloads.json'),'w') as fp:
    json.dump(line_overloads_dict,fp,indent=4, sort_keys=True)
with open(os.path.join(dss_analysis,'transformer_overloads.json'),'w') as fp:
    json.dump(transformer_overloads_dict,fp,indent=4, sort_keys=True)
