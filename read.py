import math
import logging
import os
import pandas as pd
import json

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
        if "load_file" in kwargs:
            self.load_file = kwargs["load_file"]
            self.load_data = None
        else:
            raise ValueError("No load_file parameter provided")

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

    def get_load_data(self, filename):
        """
        Helper method to save all the json data in the load file
        """
        content = []
        # Populate this once we know the format
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

        self.geojson_content = get_geojson_data(self.geojson_file)
        self.equipment_data = get_equipment_data(self.equipment_file)
        self.load_data = get_load_data(self.load_file)

        # Call parse from abstract reader class
        super(Reader, self).parse(model, **kwargs)
        return 1

    def parse_lines(self, model, **kwargs):
        """Line parser.
        :param model: DiTTo model
        :type model: DiTTo model
        :returns: 1 for success, -1 for failure
        :rtype: int
        """
        for element in self.geojson_content["features"]:
            if 'properties' in element and 'type' in element['properties'] and element['properties']['type'] == 'ElectricalConnector':
                line = Line(model)
                line.name = element['properties']['id']
                line.from_element = element['properties']['startJunctionId']
                line.to_element = element['properties']['endJunctionId']
                line.length = element['properties']['total_length']*0.3048 #length from feet to meters
                all_wires = []
                for wire_type in element['properties']['wires']:
                    for db_wire in self.equipment_data['wires']:
                        if db_wire['nameclass'] == wire_type:
                            wire = Wire(model)
                            wire.nameclass = wire_type
                            wire.phase = db_wire['phase']
                            wire.ampacity = float(db_wire['ampacity'])
                            wire.x = float(db_wire['x'])
                            wire.y = float(db_wire['y'])
                            all_wires.append(wire)



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
        substations = set()

       for element in self.geojson_content["features"]:
            if 'properties' in element and 'DSId' in element['properties'] and 'id' in element['properties']:
                if element['properties']p'DSId'] in substation_map:
                    substation_map[element['properties']['DSId']].append(element['properties']['id'])
                else:
                    substation_map[element['properties']['DSId']] = [element['properties']['id']]

        for element in self.geojson_content["features"]:
            if 'properties' in element and 'district_system_type' in element['properties'] and element['properties']['district_system_type'] == 'Substation':
                if element['properties']['id'] in substation_map:
                    for i in substation_map[element['properties']['id']]:
                        substations.add(i)

        for element in self.geojson_content["features"]:
            if 'properties' in element and 'type' in element['properties'] and element['properties']['type'] == 'ElectricalJunction':
                node = Node(model)
                node.name = element['properties']['id']
                if node.name in substations:
                    node.is_substation_connection = True
                    node.setpoint = 1.0
                position = Position(model)
                position.lat = float(element['geometry']['coordinates'][0])
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

        connection_map = {'Delta':'D','Wye','Y'}
        transformer_panel_map = {}
        for element in self.geojson_content["features"]:
            if 'properties' in element and 'DSId' in element['properties'] and 'id' in element['properties']:
                if element['properties']p'DSId'] in transformer_panel_map:
                    transformer_panel_map[element['properties']['DSId']].append(element['properties']['id'])
                else:
                    transformer_panel_map[element['properties']['DSId']] = [element['properties']['id']]

        for element in self.geojson_content["features"]:
            if 'properties' in element and 'district_system_type' in element['properties'] and element['properties']['district_system_type'] == 'Transformer':
                transformer_id = element['properties']['id']
                transformer = PowerTransformer(model)
                if transformer_panel_map[transformer_id] in transformer_panel_map:
                    if len(transformer_panel_map[transformer_id]) <2:
                        print("No from and two elements found tor transformer")
                    if len(transformer_panel_map[transformer_id]) >2:
                        print("Warning - the transformer should have a from and to element - "+str(len(transformer_panel_map[transformer_id]))+" junctions on the transformer")
                    if len(transformer_panel_map[transformer_id]) >=2:
                        for db_transformer in self.equipment_data['transformer_properties']:
                            if element['properties']['equipment'][0] == db_transformer['nameclass']:
                                transformer.from_element = transformer_panel_map[transformer_id][0]
                                transformer.to_element = transformer_panel_map[transformer_id][1] #NOTE: Need to figure out correct from and to directions here.
                                transformer.name = transformer_id
                                transformer.reantances = [float(db_transformer['reactance'])] 
                                transformer.is_center_tap = db_transformer['is_center_tap']
                                windings = [Winding(model),Winding(model)]
                                connections = db_transformer['connection'].split('-')

                                if transformer.is_center_tap:
                                    windings.append(Winding(model))
                                    transformer.reactances.append(float(db_transformer['reactance']))
                                    transformer.reactances.append(float(db_transformer['reactance'])) #TODO: map reactance values correctly for center-taps
                                for i in range(len(windings)):
                                    phase_windings = []
                                    for phase in db_transformer['phases']:
                                        pw = PhaseWinding(model)
                                        pw.phase = phase
                                        phase_windings.append(pw)
                                    windings[i].phase_windings = phase_windings
                                    windings[i].rated_power = float(db_transformer['kva'])
                                    if i<1:
                                        windings[i].nominal_voltage = float(db_transformer['high_voltage'])*1000
                                        windings[i].connection_type = connection_map[connections[0]]
                                        windings[i].voltage_type = 0
                                        windings[i].resistance = float(db_transformer['resistance'])
                                    else:
                                        windings[i].nominal_voltage = float(db_transformer['low_voltage'])*1000
                                        windings[i].connection_type = connection_map[connections[1]]
                                        windings[i].voltage_type = 1
                                        windings[i].resistance = float(db_transformer['resistance'])


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

        return 1

            
    def parse_dg(self, model, **kwargs):
        """PV parser.
        :param model: DiTTo model
        :type model: DiTTo model
        :returns: 1 for success, -1 for failure
        :rtype: int
        """

        return 1

