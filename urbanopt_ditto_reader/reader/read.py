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
import math
import logging
import os
import pandas as pd
import json
import networkx as nx

from ditto.readers.abstract_reader import AbstractReader
from ditto.store import Store
from ditto.models.node import Node
from ditto.models.line import Line
from ditto.models.wire import Wire
from ditto.models.powertransformer import PowerTransformer
from ditto.models.winding import Winding
from ditto.models.phase_winding import PhaseWinding
from ditto.models.base import Unicode
from ditto.models.position import Position
from ditto.models.feeder_metadata import Feeder_metadata
from ditto.models.capacitor import Capacitor
from ditto.models.phase_capacitor import PhaseCapacitor
from ditto.models.load import Load
from ditto.models.phase_load import PhaseLoad
from ditto.models.power_source import PowerSource
from ditto.network.network import Network
from ditto.models.photovoltaic import Photovoltaic
from ditto.models.timeseries import Timeseries
from ditto.models.feeder_metadata import Feeder_metadata
from ditto.modify.modify import Modifier

class Reader(AbstractReader):
    """
    Reader for the Urbanopt geojson file with supporting database files
    """
    register_names = ["geojson","GeoJson"]

    def __init__(self, **kwargs):
        super(Reader,self).__init__(**kwargs)

        if "geojson_file" in kwargs:
            self.geojson_file = kwargs["geojson_file"]
            self.geojson_content = None
        else:
            raise ValueError("No geojson_file parameter provided")
        if "equipment_file" in kwargs:
            self.equipment_file = kwargs["equipment_file"]
            self.equipment_data = None
        else:
            raise ValueError("No equipment_file parameter provided")
        if "load_folder" in kwargs:
            self.load_folder = kwargs["load_folder"]
            self.load_data = None
        else:
            raise ValueError("No load_folder parameter provided")
        if "use_reopt" in kwargs:
            self.use_reopt = kwargs["use_reopt"]
        else:
            self.use_reopt = False
            print("Warning - using default urbanopt configuration")

        self.is_timeseries = False
        self.timeseries_location = None
        self.relative_timeseries_location = None
        if 'is_timeseries' in kwargs:
            self.is_timeseries = kwargs['is_timeseries']
            if 'timeseries_location' in kwargs:
                self.timeseries_location = kwargs['timeseries_location']
            if 'relative_timeseries_location' in kwargs:
                self.relative_timeseries_location = kwargs['relative_timeseries_location']



    def get_geojson_data(self, filename):
        """
        Helper method to save all the json data in the geojson file
        """
        content = []
        try:
            with open(filename,"r") as f:
                content = json.load(f)
        except:
            raise IOError("Problem trying to read json from file "+filename)
        return content

    def get_equipment_data(self, filename):
        """
        Helper method to save all the json data in the equipment file
        """
        content = []
        try:
            with open(filename,"r") as f:
                content = json.load(f)
        except:
            raise IOError("Problem trying to read json from file "+filename)
        return content

    def get_feature_data(self, filename):
        """
        Helper method to save all the json data in the equipment file
        """
        content = []
        try:
            with open(filename,"r") as f:
                content = json.load(f)
        except:
            raise IOError("Problem trying to read json from file "+filename)
        return content

    def parse(self, model, **kwargs):
        """General parse function.
        Responsible for calling the sub-parsers and logging progress.
        :param model: DiTTo model
        :type model: DiTTo model
        :param verbose: Set verbose mode. Optional. Default=False
        :type verbose: bool
        :returns: 1 for success, -1 for failure
        :rtype: int
        """

        self.geojson_content = self.get_geojson_data(self.geojson_file)
        self.equipment_data = self.get_equipment_data(self.equipment_file)

        # Call parse from abstract reader class
        try:
            super(Reader, self).parse(model, **kwargs)
        except KeyError:
            raise SystemExit("\nFeatureFile is missing components. Are all electrical features included?")
        return 1

    def parse_lines(self, model, **kwargs):
        """Line parser.
        :param model: DiTTo model
        :type model: DiTTo model
        :returns: 1 for success, -1 for failure
        :rtype: int
        """
        bad_lines = []
        for element in self.geojson_content["features"]:
            if 'properties' in element and 'type' in element['properties'] and element['properties']['type'] == 'ElectricalConnector':
                line = Line(model)
                line.name = element['properties']['id']
                if element['properties']['startJunctionId'] in self.substations:
                    line.from_element = 'source'
                else:
                    line.from_element = element['properties']['startJunctionId']
                if element['properties']['endJunctionId'] in self.substations:
                    line.to_element = 'source'
                else:
                    line.to_element = element['properties']['endJunctionId']
                line.length = element['properties']['total_length']*0.3048 #length from feet to meters
                all_wires = []
                if not 'wires' in element['properties'] or len(element['properties']['wires']) == 0:
                    bad_lines.append(line.name)
                    continue

                for wire_type in element['properties']['wires']:
                    for db_wire in self.equipment_data['wires']:
                        if db_wire['nameclass'] == wire_type:
                            wire = Wire(model)
                            wire.nameclass = wire_type.replace(' ','_').replace('/','-')
                            if 'OH' in wire_type:
                                line.line_type = 'overhead'
                            else:
                                line.line_type = 'underground'
                            if 'S1' in wire_type:
                                wire.phase = 'A'
                            elif 'S2' in wire_type:
                                wire.phase = 'B'
                            else:
                                wire.phase = wire_type.split(' ')[-1] #Currently the convention is that the last element is the phase.
                            wire.ampacity = float(db_wire['ampacity'])
                            wire.gmr = float(db_wire['gmr'])*0.3048
                            wire.resistance = float(db_wire['resistance'])*0.3048
                            wire.diameter = float(db_wire['diameter'])*0.3048
                            wire.X = float(db_wire['x'])*0.3048
                            wire.Y = float(db_wire['height'])*0.3048
                            all_wires.append(wire)
                line.wires = all_wires


        if len(bad_lines) > 0:
            print('Following lines are missing wires:')
            for line in bad_lines:
                print(line)
            print()
            raise ValueError("Wires missing for some lines")

        return 1

    def parse_nodes(self, model, **kwargs):
        """Node parser.
        :param model: DiTTo model
        :type model: DiTTo model
        :returns: 1 for success, -1 for failure
        :rtype: int
        """
        # Assume one substation per feeder with a single junction
        substation_map = {}
        self.substations = set()

        for element in self.geojson_content["features"]:
            if 'properties' in element and 'DSId' in element['properties'] and 'id' in element['properties']:
                if element['properties']['DSId'] in substation_map:
                    substation_map[element['properties']['DSId']].append(element['properties']['id'])
                else:
                    substation_map[element['properties']['DSId']] = [element['properties']['id']]

        for element in self.geojson_content["features"]:
            if 'properties' in element and 'district_system_type' in element['properties'] and element['properties']['district_system_type'] == 'Electrical Substation':
                if element['properties']['id'] in substation_map:
                    for i in substation_map[element['properties']['id']]:
                        self.substations.add(i)

        if len(self.substations)>1:
            print('Warning - multiple power sources have been added')
        for element in self.geojson_content["features"]:
            if 'properties' in element and 'type' in element['properties'] and element['properties']['type'] == 'ElectricalJunction':
                node = Node(model)
                node.name = element['properties']['id']
                if node.name in self.substations:
                    node.nominal_voltage = 13200
                    node.is_substation_connection = True
                    node.setpoint = 1.0
                    node.name = 'source'
                    meta = Feeder_metadata(model)
                    meta.headnode = 'source'
                    meta.nominal_voltage = 13200
                    meta.name = 'urbanopt-feeder'
                    powersource = PowerSource(model)
                    powersource.is_sourcebus = True
                    powersource.name = 'ps_source'
                    powersource.nominal_voltage = 13200
                    powersource.connecting_element = 'source'
                    powersource.per_unit = 1.0
                position = Position(model)
                position.lat = float(element['geometry']['coordinates'][1])
                position.long = float(element['geometry']['coordinates'][0])
                node.positions = [position]


        return 1

    def parse_transformers(self, model, **kwargs):
        """Transformer parser.
        :param model: DiTTo model
        :type model: DiTTo model
        :returns: 1 for success, -1 for failure
        :rtype: int
        """

        # Assume that each transformer has one from node and one to node.

        connection_map = {'Delta':'D','Wye':'Y'}
        transformer_panel_map = {}
        for element in self.geojson_content["features"]:
            if 'properties' in element and 'DSId' in element['properties'] and 'id' in element['properties']:
                if element['properties']['DSId'] in transformer_panel_map:
                    transformer_panel_map[element['properties']['DSId']].append(element['properties']['id'])
                else:
                    transformer_panel_map[element['properties']['DSId']] = [element['properties']['id']]

        for element in self.geojson_content["features"]:
            if 'properties' in element and 'district_system_type' in element['properties'] and element['properties']['district_system_type'] == 'Transformer':
                transformer_id = element['properties']['id']
                transformer = PowerTransformer(model)
                if transformer_id in transformer_panel_map:
                    if len(transformer_panel_map[transformer_id]) <2:
                        print(f"No from and to elements found for transformer {transformer_id}")
                    if len(transformer_panel_map[transformer_id]) >2:
                        print("Warning - the transformer "+transformer_id+" should have a from and to element - "+str(len(transformer_panel_map[transformer_id]))+" junctions on the transformer")
                    if len(transformer_panel_map[transformer_id]) >=2:
                        for db_transformer in self.equipment_data['transformer_properties']:
                            if element['properties']['equipment'][0] == db_transformer['nameclass']:
                                transformer.from_element = transformer_panel_map[transformer_id][0]
                                transformer.to_element = transformer_panel_map[transformer_id][1] #NOTE: Need to figure out correct from and to directions here.
                                transformer.name = transformer_id
                                transformer.reactances = [float(db_transformer['reactance'])]
                                transformer.is_center_tap = db_transformer['is_center_tap']
                                windings = [Winding(model),Winding(model)]
                                connections = db_transformer['connection'].split('-')

                                if transformer.is_center_tap:
                                    windings.append(Winding(model))
                                    transformer.reactances.append(float(db_transformer['reactance']))
                                    transformer.reactances.append(float(db_transformer['reactance'])) #TODO: map reactance values correctly for center-taps
                                for i in range(len(windings)):
                                    phase_windings = []
                                    if transformer.is_center_tap and i >0:
                                        for phase in ['A','B']:
                                            pw = PhaseWinding(model)
                                            pw.phase = phase
                                            phase_windings.append(pw)
                                    else:
                                        for phase in db_transformer['phases']:
                                            pw = PhaseWinding(model)
                                            pw.phase = phase
                                            phase_windings.append(pw)
                                    windings[i].phase_windings = phase_windings
                                    windings[i].rated_power = float(db_transformer['kva'])*1000
                                    if i<1:
                                        windings[i].nominal_voltage = float(db_transformer['high_voltage'])*1000
                                        if transformer.is_center_tap:
                                            windings[i].nominal_voltage = windings[i].nominal_voltage/(3**0.5)
                                        windings[i].connection_type = connection_map[connections[0]]
                                        windings[i].voltage_type = 0
                                        windings[i].resistance = float(db_transformer['resistance'])
                                    else:
                                        windings[i].nominal_voltage = float(db_transformer['low_voltage'])*1000
                                        windings[i].connection_type = connection_map[connections[1]]
                                        windings[i].voltage_type = 1
                                        windings[i].resistance = float(db_transformer['resistance'])
                                transformer.windings = windings


        return 1

    def parse_capacitors(self, model, **kwargs):
        """Capacitor parser.
        :param model: DiTTo model
        :type model: DiTTo model
        :returns: 1 for success, -1 for failure
        :rtype: int
        """

        return 1

    def parse_loads(self, model, **kwargs):
        """Load parser.
        :param model: DiTTo model
        :type model: DiTTo model
        :returns: 1 for success, -1 for failure
        :rtype: int
        """
        model.set_names()
        network = Network()
        network.build(model,source="source")
        number_components = nx.number_connected_components(network.graph)
        self.deleted_elements = None
        if not number_components==1:
            updated_model=model
            source_component = None
            c_id = 0
            print(f"Warning - network is disconnected with {number_components} components")
            components = []
            for component in nx.connected_components(network.graph):
                nodes = {}
                for node in component:
                    if node in model.model_names and isinstance(model[node],Node):
                        nodes[node] = (model[node].positions[0].lat,model[node].positions[0].long)
                    if node in model.model_names and isinstance(model[node],PowerSource):
                        source_component = c_id
                components.append(nodes)
                c_id+=1
            if source_component is None:
                raise ValueError("No substation in geojson_file")
            seen = set([source_component])
            self.deleted_elements = {}
            modifier = Modifier()
            while len(seen) < len(components): # Incrementally add closest component to the component connected to the substation
                closest_dist = 10000000000000000
                closest_component = None
                closest_node_pair = None
                connecting_component = None
                for c_id in range(len(components)):
                    if c_id in seen:
                        continue
                    for c_id2 in seen:
                        for node1_name,node1 in components[c_id].items():
                            for node2_name,node2 in components[c_id2].items():
                                if not node2_name in self.deleted_elements: #So don't attach to a node that's already been deleted
                                    distance = math.sqrt((node1[0]-node2[0])**2 + (node1[1]-node2[1])**2)
                                    if distance < closest_dist:
                                        closest_dist = distance
                                        closest_node_pair = (node1_name,node2_name)
                                        closest_component = c_id
                                        connecting_component = c_id2

                node_to_remove = closest_node_pair[0]
                node_to_use = closest_node_pair[1]
                for i in model.models:
                    if hasattr(i,'from_element') and i.from_element == node_to_remove:
                        i.from_element = node_to_use
                    if hasattr(i,'to_element') and i.to_element == node_to_remove:
                        i.to_element = node_to_use
                    if hasattr(i,'connecting_element') and i.connecting_element == node_to_remove:
                        i.connecting_element = node_to_use
                model = modifier.delete_element(model,model[node_to_remove])
                print(f'Deleting node {node_to_remove}',flush=True)
                seen.add(closest_component)
                self.deleted_elements[node_to_remove] = node_to_use

            model.set_names()
            network = Network()
            network.build(model,source="source")


        building_map = {}
        for element in self.geojson_content["features"]:
            if 'properties' in element and 'type' in element['properties'] and 'buildingId' in element['properties'] and element['properties']['type'] == 'ElectricalJunction':
                building_map[element['properties']['buildingId']] = element['properties']['id']
        for element in self.geojson_content["features"]:
            if 'properties' in element and 'type' in element['properties'] and element['properties']['type'] == 'Building':
                id_value = element['properties']['id']
                if not id_value in building_map:
                    print(f'Warning - {id_value} missing from building object. Skipping...',flush=True)
                    continue
                connecting_element = building_map[id_value]
                load = Load(model)
                load.name = id_value
                if self.deleted_elements is not None:
                    while connecting_element in self.deleted_elements:
                        connecting_element = self.deleted_elements[connecting_element]
                load.connecting_element = connecting_element
                upstream_transformer_name = network.get_upstream_transformer(model,connecting_element)
                if upstream_transformer_name is not None:
                    upstream_transformer = model[upstream_transformer_name]
                    is_center_tap = upstream_transformer.is_center_tap
                    load.nominal_voltage = upstream_transformer.windings[1].nominal_voltage
                else:
                    print(f'Warning - Load {load.name} is incorrectly connected',flush=True)

                load_path = os.path.join(self.load_folder,id_value,'feature_reports')
                if os.path.exists(load_path): #We've found the load data

                    load_data = None
                    load_column = None
                    if self.use_reopt:
                        load_data = pd.read_csv(os.path.join(load_path,'feature_report_reopt.csv'),header=0)
                        load_column = 'REopt:Electricity:Load:Total(kw)'
                    else:
                        load_data = pd.read_csv(os.path.join(load_path,'default_feature_report.csv'),header=0)
                        load_column = 'Net Power(kW)'
                    max_load = max(load_data[load_column])

                    phases = []
                    if upstream_transformer_name is not None:
                        for ph_wdg in upstream_transformer.windings[1].phase_windings:
                            phases.append(ph_wdg.phase)
                        if is_center_tap:
                            phases = ['A','B']

                    phase_loads = []
                    for phase in phases:
                        phase_load = PhaseLoad(model)
                        phase_load.phase = phase
                        power_factor = 0.95
                        phase_load.p = max_load/len(phases)
                        phase_load.q = phase_load.p * ((1/power_factor-1)**0.5)
                        phase_loads.append(phase_load)
                    load.phase_loads = phase_loads
                    if self.is_timeseries:
                        data = load_data[load_column]
                        timestamps = load_data['Datetime']
                        delta = datetime.datetime.strptime(timestamps.loc[1],'%Y/%m/%d %H:%M:%S') - datetime.datetime.strptime(timestamps.loc[0],'%Y/%m/%d %H:%M:%S')
                        data_pu = data/max_load
                        if not self.timeseries_location is None:
                            if not os.path.exists(self.timeseries_location):
                                os.makedirs(self.timeseries_location)
                            data.to_csv(os.path.join(self.timeseries_location,'load_'+id_value+'.csv'),header=False, index=False)
                            data_pu.to_csv(os.path.join(self.timeseries_location,'load_'+id_value+'_pu.csv'),header=False, index=False)
                            timestamps.to_csv(os.path.join(self.timeseries_location,'timestamps.csv'),header=True,index=False)
                            timeseries = Timeseries(model)
                            timeseries.feeder_name = load.feeder_name
                            timeseries.substation_name = load.substation_name
                            timeseries.interval = delta.seconds/3600.0 #assume 15 minute loads
                            timeseries.data_type = 'float'
                            timeseries.data_location = os.path.join(self.relative_timeseries_location,'load_'+id_value+'_pu.csv')
                            timeseries.data_label = 'feature_'+id_value
                            timeseries.scale_factor = 1
                            load.timeseries = [timeseries]





                else:
                    print('Load information missing for '+id_value,flush=True)


        return 1


    def parse_dg(self, model, **kwargs):
        """PV parser.
        :param model: DiTTo model
        :type model: DiTTo model
        :returns: 1 for success, -1 for failure
        :rtype: int
        """
        if not self.use_reopt:
            return 1
        model.set_names()
        network = Network()
        network.build(model,source="source")
        building_map = {}
        for element in self.geojson_content["features"]:
            if 'properties' in element and 'type' in element['properties'] and 'buildingId' in element['properties'] and element['properties']['type'] == 'ElectricalJunction':
                building_map[element['properties']['buildingId']] = element['properties']['id']
        for element in self.geojson_content["features"]:
            if 'properties' in element and 'type' in element['properties'] and element['properties']['type'] == 'Building':
                id_value = element['properties']['id']
                if not id_value in building_map:
                    print(f'Warning - {id_value} missing from building object. Skipping...',flush=True)
                    continue
                connecting_element = building_map[id_value]
                if self.deleted_elements is not None:
                    while connecting_element in self.deleted_elements:
                        connecting_element = self.deleted_elements[connecting_element]
                try:
                    feature_data = self.get_feature_data(os.path.join(self.load_folder,id_value,'feature_reports','feature_report_reopt.json'))
                except Exception as e:
                    print(e)
                    continue
                pv_kw = feature_data['distributed_generation']['total_solar_pv_kw']

                upstream_transformer_name = network.get_upstream_transformer(model,connecting_element)
                if upstream_transformer_name is not None:
                    upstream_transformer = model[upstream_transformer_name]
                    is_center_tap = upstream_transformer.is_center_tap
                else:
                    print(f'Warning - DG {pv.name} is incorrectly connected',flush=True)
                if pv_kw >0:
                    pv = Photovoltaic(model)
                    pv.name = 'solar_'+id_value
                    pv.connecting_element = connecting_element
                    if upstream_transformer_name is not None:
                        pv.nominal_voltage = upstream_transformer.windings[1].nominal_voltage
                        pv.connection_type = upstream_transformer.windings[1].connection_type
                        phases = []
                        for ph_wdg in upstream_transformer.windings[1].phase_windings:
                            phases.append(Unicode(ph_wdg.phase))
                        if is_center_tap:
                            phases = [Unicode('A'),Unicode('B')]
                        pv.phases = phases
                    pv.rated_power = pv_kw
                    pv.active_rating = 1.1*pv_kw # Should make this a parameter instead
                    if self.is_timeseries:
                        load_data = pd.read_csv(os.path.join(self.load_folder,id_value,'feature_reports','feature_report_reopt.csv'),header=0)
                        data = load_data['REopt:ElectricityProduced:PV:Total(kw)']
                        timestamps = load_data['Datetime']
                        delta = datetime.datetime.strptime(timestamps.loc[1],'%Y/%m/%d %H:%M:%S') - datetime.datetime.strptime(timestamps.loc[0],'%Y/%m/%d %H:%M:%S')
                        data_pu = data/pv_kw
                        if not self.timeseries_location is None:
                            if not os.path.exists(self.timeseries_location): #Should have already been created for the loads
                                os.makedirs(self.timeseries_location)
                            data.to_csv(os.path.join(self.timeseries_location,'pv_'+id_value+'.csv'),header=False, index=False)
                            data_pu.to_csv(os.path.join(self.timeseries_location,'pv_'+id_value+'_pu.csv'),header=False, index=False)
                            timeseries = Timeseries(model)
                            timeseries.feeder_name = pv.feeder_name
                            timeseries.substation_name = pv.substation_name
                            timeseries.interval = delta.seconds/3600.0
                            timeseries.data_type = 'float'
                            timeseries.data_location = os.path.join(self.relative_timeseries_location,'pv_'+id_value+'_pu.csv')
                            timeseries.data_label = 'feature_'+id_value
                            timeseries.scale_factor = 1
                            pv.timeseries = [timeseries]



        return 1
