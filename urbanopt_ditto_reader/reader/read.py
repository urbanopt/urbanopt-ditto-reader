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
import os
import json
from datetime import datetime

from ditto.readers.abstract_reader import AbstractReader
from ditto.models.node import Node
from ditto.models.line import Line
from ditto.models.wire import Wire
from ditto.models.powertransformer import PowerTransformer
from ditto.models.winding import Winding
from ditto.models.phase_winding import PhaseWinding
from ditto.models.base import Unicode
from ditto.models.position import Position
from ditto.models.feeder_metadata import Feeder_metadata
from ditto.models.load import Load
from ditto.models.phase_load import PhaseLoad
from ditto.models.power_source import PowerSource
from ditto.network.network import Network
from ditto.models.photovoltaic import Photovoltaic
from ditto.models.timeseries import Timeseries


class Reader(AbstractReader):
    """Object to translate URBANopt GeoJSON files and scenario results to OpenDSS.

    Keyword Arguments:
        geojson_file (str): Path to a GeoJSON file following the URBANopt schema.
        equipment_file (str): Path to an equipment database JSON file.
        load_folder(str): Path to the folder that contains the energy simulation
            results that will be used as the OpenDSS load profiles. This usually
            includes the name of the scenario that was simulated.
        use_reopt (bool): Boolean to note whether REopt results should be
            used. (Default: False).
        is_timeseries (bool): A boolean to note wether the load profiles are
            timeseries data. (Default: False).
        timeseries_location (str): Path to where the timeseries load profiles
            should be written in CSV format.
        relative_timeseries_location (str): Relative path to where the timeseries
            load profiles should be written in CSV format (relative to
            the timeseries_location).
    """

    register_names = ['geojson', 'GeoJson']

    def __init__(self, **kwargs):
        super(Reader, self).__init__(**kwargs)

        if 'geojson_file' in kwargs:
            self.geojson_file = kwargs['geojson_file']
            self.geojson_content = None
        else:
            raise ValueError('No geojson_file parameter provided')
        if 'equipment_file' in kwargs:
            self.equipment_file = kwargs['equipment_file']
            self.equipment_data = None
        else:
            raise ValueError('No equipment_file parameter provided')
        if 'load_folder' in kwargs:
            self.load_folder = kwargs['load_folder']
            self.load_data = None
        else:
            raise ValueError('No load_folder parameter provided')
        if 'use_reopt' in kwargs:
            self.use_reopt = kwargs['use_reopt']
        else:
            self.use_reopt = False
            print('Warning - using default urbanopt configuration')

        self.is_timeseries = False
        self.timeseries_location = None
        self.relative_timeseries_location = None
        if 'is_timeseries' in kwargs:
            self.is_timeseries = kwargs['is_timeseries']
            if 'timeseries_location' in kwargs:
                self.timeseries_location = kwargs['timeseries_location']
            if 'relative_timeseries_location' in kwargs:
                self.relative_timeseries_location = \
                    kwargs['relative_timeseries_location']

    def get_json_data(self, filename):
        """Helper method to load the json data in a JSON file.

        Args:
            filename: Path to a JSON file.
        """
        content = []
        try:
            with open(filename, 'r') as f:
                content = json.load(f)
        except Exception:
            raise IOError('Problem trying to read json from file {}.'.format(filename))
        return content

    def parse(self, model, **kwargs):
        """Parse all of the data from the GeoJSON, Equipment, and load profile files.

        This will call of the sub-parsers on this class to load lines, transformers,
        building loads, etc.

        Args:
            model (DiTTo model): A DiTTo model object to be assigned to the reader.

        Keyword Arguments:
            verbose (bool): Boolean to set verbose mode. (Default: False).

        Returns:
            An integer. 1 for success, -1 for failure.
        """
        self.geojson_content = self.get_json_data(self.geojson_file)
        self.equipment_data = self.get_json_data(self.equipment_file)

        # Call parse from abstract reader class
        super(Reader, self).parse(model, **kwargs)
        return 1

    def parse_lines(self, model, **kwargs):
        """Parse the lines of the GeoJSON and equipment files.

        Args:
            model (DiTTo model): A DiTTo model object assigned to the reader.

        Returns:
            An integer. 1 for success, -1 for failure.
        """
        wire_map = {}
        for wire in self.equipment_data['WIRES']['WIRES CATALOG']:
            wire_map[wire['nameclass']] = wire

        bad_lines = []
        for element in self.geojson_content["features"]:
            if 'properties' in element and 'type' in element['properties'] and \
                    element['properties']['type'] == 'ElectricalConnector':
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
                line.length = element['properties']['total_length'] * 0.3048  # ft to m
                all_wires = []
                if 'electrical_catalog_name' in element['properties']:
                    catalog_name = element['properties']['electrical_catalog_name']
                    found_line = False
                    for all_zone in self.equipment_data['LINES']:  # Look in all zones.
                        if not isinstance(all_zone, dict):
                            continue
                        for zone in all_zone:  # TODO: consider using a single zone?
                            for db_line in all_zone[zone]:
                                if found_line:
                                    break
                                if catalog_name == db_line['Name']:
                                    found_line = True
                                    for db_wire in db_line['Line geometry']:
                                        wire = Wire(model)
                                        wire_type = db_wire['wire']
                                        wire.nameclass = \
                                            wire_type.replace(' ', '_').replace('/', '-')
                                        wire.phase = db_wire['phase']
                                        wire.X = db_wire['x (m)']
                                        wire.Y = db_wire['height (m)']
                                        self._assign_wire_properties(
                                            wire, wire_map[wire_type])
                                        if 'OH' in wire_map[wire_type]['type']:
                                            line.line_type = 'overhead'
                                        elif 'UG' in wire_map[wire_type]['type']:
                                            line.line_type = 'underground'

                                        all_wires.append(wire)
                    if not found_line:
                        raise ValueError(
                            'No line found in catalog for {}'.format(
                                element["properties"]["electrical_catalog_name"]
                            ))
                else:
                    bad_lines.append(line.name)
                line.wires = all_wires

        if len(bad_lines) > 0:
            print('Following lines are missing wires:')
            for line in bad_lines:
                print(line)
            raise ValueError("Wires missing for some lines")

        return 1

    @staticmethod
    def _assign_wire_properties(wire, wire_props):
        """Assign properties to a DiTTo Wire using the catalog dictionary."""
        wire.ampacity = wire_props['ampacity (A)']
        # all ditto length units are in meters
        wire.gmr = wire_props['gmr (mm)'] / 1000
        wire.diameter = wire_props['diameter (mm)'] / 1000
        # ditto internal resistance is in ohms/meter
        wire.resistance = wire_props['resistance (ohm/km)'] / 1000
        if wire_props['type'] == 'UG concentric neutral':
            wire.concentric_neutral_gmr = \
                wire_props['gmr neutral (mm)'] / 1000
            wire.concentric_neutral_resistance = \
                wire_props['resistance neutral (ohm/km)'] / 1000
            wire.concentric_neutral_diameter = \
                wire_props['concentric diameter neutral strand (mm)'] / 1000
            wire.concentric_neutral_outside_diameter = \
                wire_props['concentric neutral outside diameter (mm)'] / 1000
            wire.concentric_neutral_nstrand = \
                wire_props['# concentric neutral strands']
            wire.insulation_thickness = 10 / 1000.0

    def parse_nodes(self, model, **kwargs):
        """Parse the nodes of the GeoJSON.

        Args:
            model (DiTTo model): A DiTTo model object assigned to the reader.

        Returns:
            An integer. 1 for success, -1 for failure.
        """
        # Assume one substation per feeder with a single junction
        substation_map = {}
        self.substations = set()

        for element in self.geojson_content['features']:
            if 'properties' in element and 'DSId' in element['properties'] and \
                    'id' in element['properties']:
                e_ds_id = element['properties']['DSId']
                if e_ds_id in substation_map:
                    substation_map[e_ds_id].append(element['properties']['id'])
                else:
                    substation_map[e_ds_id] = [element['properties']['id']]

        for element in self.geojson_content['features']:
            if 'properties' in element and 'district_system_type' in \
                    element['properties']:
                sys_type = element['properties']['district_system_type']
                if sys_type == 'Electrical Substation':
                    if element['properties']['id'] in substation_map:
                        for i in substation_map[element['properties']['id']]:
                            self.substations.add(i)

        if len(self.substations) > 1:
            print('Warning - multiple power sources have been added')
        for element in self.geojson_content['features']:
            if 'properties' in element and 'type' in element['properties'] and \
                    element['properties']['type'] == 'ElectricalJunction':
                node = Node(model)
                node.name = element['properties']['id']
                if node.name in self.substations:
                    node.nominal_voltage = 13200  # placeholder voltage
                    node.is_substation_connection = True
                    node.setpoint = 1.0
                    node.name = 'source'
                    meta = Feeder_metadata(model)
                    meta.headnode = 'source'
                    meta.nominal_voltage = 13200  # placeholder voltage
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
        """Parse the transformers of the GeoJSON.

        Args:
            model (DiTTo model): A DiTTo model object assigned to the reader.

        Returns:
            An integer. 1 for success, -1 for failure.
        """
        # Assume that each transformer has one from node and one to node.
        transformer_panel_map = {}
        for element in self.geojson_content["features"]:
            if 'properties' in element and 'DSId' in element['properties'] \
                    and 'id' in element['properties']:
                e_id = element['properties']['id']
                if element['properties']['DSId'] in transformer_panel_map:
                    transformer_panel_map[element['properties']['DSId']].append(e_id)
                else:
                    transformer_panel_map[element['properties']['DSId']] = [e_id]

        source_voltages = set()
        for element in self.geojson_content["features"]:
            if 'properties' in element and \
                    'district_system_type' in element['properties'] and \
                    element['properties']['district_system_type'] == 'Transformer':
                tr_id = element['properties']['id']
                transformer = PowerTransformer(model)
                if tr_id in transformer_panel_map:
                    if len(transformer_panel_map[tr_id]) < 2:
                        print('No from and to elements found for transformer '
                              '{}'.format(tr_id))
                    if len(transformer_panel_map[tr_id]) > 2:
                        print(
                            'Warning - the transformer {} should have a from and to '
                            'element - {} junctions on the transformer'.format(
                                tr_id, len(transformer_panel_map[tr_id])))
                    if len(transformer_panel_map[tr_id]) >= 2:
                        found_transformer = False
                        trans_cat_key = 'SUBSTATIONS AND DISTRIBUTION TRANSFORMERS'
                        catalog_name = element['properties']['electrical_catalog_name']
                        for all_zone in self.equipment_data[trans_cat_key]:
                            # TODO: Figure out why there duplicate zones
                            for zone in all_zone:
                                for db_transformer in all_zone[zone]:
                                    if found_transformer:
                                        break
                                    if catalog_name == db_transformer['Name']:
                                        found_transformer = True
                                        # NOTE: direction can be wrong
                                        # Will be fixed in the consistency module
                                        transformer.from_element = \
                                            transformer_panel_map[tr_id][0]
                                        transformer.to_element = \
                                            transformer_panel_map[tr_id][1]
                                        transformer.name = tr_id
                                        self._assign_transformer_properties(
                                            transformer, db_transformer, element, model)
                                        nv = db_transformer['Primary Voltage (kV)']
                                        source_voltages.add(float(nv) * 1000)
                        if not found_transformer:
                            raise ValueError('No transformer found in catalog for '
                                             '{}'.format(catalog_name))

        # Note that the source voltage is set to be the highest side of the transformer
        if len(source_voltages) == 1:
            source_voltage = source_voltages.pop()
            model.set_names()
            model['source'].nominal_voltage = source_voltage
            model['ps_source'].nominal_voltage = source_voltage
            model['urbanopt-feeder'].nominal_voltage = source_voltage
        elif len(source_voltages) == 0:  # no transformers in this model
            pass
        else:
            raise ValueError(
                'Problem setting source voltage. No high transformer values '
                'or non-unique high side voltages.')
        return 1

    @staticmethod
    def _assign_transformer_properties(transformer, trans_props, element, model):
        """Assign properties to a DiTTo Transformer using the catalog dictionary."""
        # set the overall transformer properties
        transformer.reactances = [float(trans_props['Reactance (p.u. transf)'])]
        transformer.is_center_tap = trans_props['Centertap']
        con_map = {'Delta': 'D', 'Wye': 'Y'}
        connections = [con_map[conn] for conn in trans_props['connection'].split('-')]

        # set up the windings
        windings = [Winding(model), Winding(model)]
        if transformer.is_center_tap:
            # TODO: map reactance values correctly for center-taps
            windings.append(Winding(model))
            transformer.reactances.append(float(trans_props['Reactance (p.u. transf)']))
            transformer.reactances.append(float(trans_props['Reactance (p.u. transf)']))

        # edit the properties of the windings
        for i, winding in enumerate(windings):
            # set up the phase windings
            phase_windings = []
            if transformer.is_center_tap and i > 0:
                # Create A and B phase for low side of center-tap transformers
                # per OpenDSS convention
                for phase in ('A', 'B'):
                    pw = PhaseWinding(model)
                    pw.phase = phase
                    phase_windings.append(pw)
            else:
                # Phases must be added as an extra attribute in the geojson file
                # under properties. This is normally an optional field.
                if 'phases' not in element['properties']:
                    raise ValueError(
                        'Transformer {} does not have phases included in geojson '
                        'file'.format(element["properties"]["id"]))
                phases = element['properties']['phases']
                if len(phases) != int(trans_props['Nphases']):
                    raise ValueError(
                        'Phases for transformer {} in database do not match number '
                        'of phases of transformer {} in geojson file'.format(
                            element["properties"]["electrical_catalog_name"],
                            element["properties"]["id"]))
                for phase in phases:
                    pw = PhaseWinding(model)
                    pw.phase = phase
                    phase_windings.append(pw)
            winding.phase_windings = phase_windings

            # set the winding kVA rating
            if 'Installed Power(MVA)' in trans_props:
                kva = float(trans_props['Installed Power (MVA)']) * 1000
            else:
                kva = float(trans_props['Installed Power(kVA)'])
            winding.rated_power = kva * 1000

            # set the winding voltages
            if i == 0:
                winding.nominal_voltage = \
                    float(trans_props['Primary Voltage (kV)']) * 1000
                if transformer.is_center_tap:
                    winding.nominal_voltage = winding.nominal_voltage / (3 ** 0.5)
                winding.connection_type = connections[0]
                winding.voltage_type = 0
            else:
                winding.nominal_voltage = \
                    float(trans_props['Secondary Voltage (kV)']) * 1000
                winding.connection_type = connections[1]
                winding.voltage_type = 1
            winding.resistance = \
                float(trans_props['Low-voltage-side short-circuit resistance (ohms)'])
        transformer.windings = windings

    def parse_capacitors(self, model, **kwargs):
        """Parse the transformers of the GeoJSON.

        Args:
            model (DiTTo model): A DiTTo model object assigned to the reader.

        Returns:
            An integer. 1 for success, -1 for failure.
        """
        # TODO: actually fill this in with parsing methods
        return 1

    def parse_loads(self, model, **kwargs):
        """Parse the load profiles from the simulation results.

        Args:
            model (DiTTo model): A DiTTo model object assigned to the reader.

        Returns:
            An integer. 1 for success, -1 for failure.
        """
        # set up the model and network
        model.set_names()
        network = Network()
        network.build(model, source="source")

        # get building elements and a map from buildings to the electrical junctions
        building_map = self.create_building_map(self.geojson_content)
        bldg_elements = self.collect_building_elements(self.geojson_content)

        # loop through the buildings and parse their load profiles
        disconnected_loads = []
        for element in bldg_elements:
            id_value = element['properties']['id']
            if id_value not in building_map:
                print(f'Warning - {id_value} missing from building object. Skipping...',
                      flush=True)
                continue

            # determine the nominal voltage from the upstream transformer
            connecting_element = building_map[id_value]
            load = Load(model)
            load.name = id_value
            load.connecting_element = connecting_element
            upstream_transformer_name = None
            try:
                upstream_transformer_name = network.get_upstream_transformer(
                    model, connecting_element)
            except Exception:  # caused by elements not being connected
                disconnected_loads.append(element['properties']['id'])
            if upstream_transformer_name is not None:
                upstream_transformer = model[upstream_transformer_name]
                is_center_tap = upstream_transformer.is_center_tap
                load.nominal_voltage = \
                    upstream_transformer.windings[1].nominal_voltage
            else:
                print(f'Warning - Load {load.name} has no transformer. '
                      'Assigning as MV load', flush=True)
                load.nominal_voltage = model['urbanopt-feeder'].nominal_voltage

            # load the power draw of the buildings from the energy sim results
            load_path = os.path.join(self.load_folder, id_value, 'feature_reports')
            load_multiplier = 1000
            if os.path.exists(load_path):  # We've found the load data
                if self.use_reopt:
                    rep_csv = os.path.join(load_path, 'feature_optimization.csv')
                    report_mtx = self._read_csv(rep_csv)
                    header_row = report_mtx.pop(0)
                    load_col_i = header_row.index('REopt:Electricity:Load:Total(kw)')
                    load_column = [row[load_col_i] for row in report_mtx]
                else:
                    rep_csv = os.path.join(load_path, 'default_feature_report.csv')
                    report_mtx = self._read_csv(rep_csv)
                    header_row = report_mtx.pop(0)
                    try:
                        load_col_i = header_row.index('Net Power(kW)')
                    except ValueError:  # column has a different name
                        try:
                            load_col_i = header_row.index('Net Power(W)')
                            load_multiplier = 1
                        except ValueError:  # no load data was found
                            raise ValueError(
                                'Neither of the columns "Net Power(W)" or "Net Power'
                                '(kW)" were found in default_feature_report.csv')
                load_column = [float(row[load_col_i]) for row in report_mtx]
                max_load = max(load_column)

                # get the phases of the load profile from the transformer
                phases = []
                if upstream_transformer_name is not None:
                    for ph_wdg in upstream_transformer.windings[1].phase_windings:
                        phases.append(ph_wdg.phase)
                    if is_center_tap:
                        phases = ['A', 'B']
                else:  # NOTE: we are assuming that MV loads are all three phase
                    phases = ['A', 'B', 'C']

                # determine the phase loads
                phase_loads = []
                for phase in phases:
                    phase_load = PhaseLoad(model)
                    phase_load.phase = phase
                    power_factor = 0.95
                    phase_load.p = max_load / len(phases) * load_multiplier
                    phase_load.q = phase_load.p * ((1 / power_factor - 1) ** 0.5)
                    phase_loads.append(phase_load)
                load.phase_loads = phase_loads

                # assign the timeseries load profile
                if self.is_timeseries:
                    data = load_column
                    data_pu = [d / max_load for d in data]
                    ts_i = header_row.index('Datetime')
                    timestamps = [row[ts_i] for row in report_mtx]
                    dt_format = '%Y/%m/%d %H:%M:%S'
                    delta = datetime.strptime(timestamps[1], dt_format) - \
                        datetime.strptime(timestamps[0], dt_format)
                    ts_loc = self.timeseries_location
                    if ts_loc is not None:
                        if not os.path.exists(ts_loc):
                            os.makedirs(ts_loc)
                        load_path = os.path.join(ts_loc, 'load_{}.csv'.format(id_value))
                        pu_path = os.path.join(ts_loc, 'load_{}_pu.csv'.format(id_value))
                        ts_path = os.path.join(ts_loc, 'timestamps.csv')
                        self._write_single_column_csv(data, load_path)
                        self._write_single_column_csv(data_pu, pu_path)
                        self._write_single_column_csv(timestamps, ts_path, 'Datetime')
                        timeseries = Timeseries(model)
                        timeseries.feeder_name = load.feeder_name
                        timeseries.substation_name = load.substation_name
                        timeseries.interval = delta.seconds / 3600.0
                        timeseries.data_type = 'float'
                        rel_pu_path = os.path.join(self.relative_timeseries_location,
                                                   'load_{}_pu.csv'.format(id_value))
                        timeseries.data_location = rel_pu_path
                        timeseries.data_label = 'feature_{}'.format(id_value)
                        timeseries.scale_factor = 1
                        load.timeseries = [timeseries]
            else:
                print('Load information missing for {}'.format(id_value), flush=True)

        # give a warning about any disconnected loads that were discovered
        if len(disconnected_loads) > 1:
            print('The following loads have connection problems:'
                  '\n{}'.format(','.join(disconnected_loads)))
        return 1

    def parse_dg(self, model, **kwargs):
        """Parse the load profiles from the PV results from REopt.

        Args:
            model (DiTTo model): A DiTTo model object assigned to the reader.

        Returns:
            An integer. 1 for success, -1 for failure.
        """
        # set up the model and network
        if not self.use_reopt:
            return 1
        model.set_names()
        network = Network()
        network.build(model, source="source")

        # get building elements and a map from buildings to the electrical junctions
        building_map = self.create_building_map(self.geojson_content)
        bldg_elements = self.collect_building_elements(self.geojson_content)

        # loop through the buildings and parse any of their generated PV electricity
        for element in bldg_elements:
            id_value = element['properties']['id']
            if id_value not in building_map:
                print(f'Warning - {id_value} missing from building object. Skipping...',
                      flush=True)
                continue

            # determine the installed kW of PV from the REopt results
            connecting_element = building_map[id_value]
            re_folder = os.path.join(self.load_folder, id_value, 'feature_reports')
            try:
                load_file = os.path.join(re_folder, 'feature_optimization.json')
                feature_data = self.get_json_data(load_file)
            except Exception as e:
                print(e)
                continue
            pv_kw = feature_data['distributed_generation']['total_solar_pv_kw']

            # determine the nominal voltage from the upstream transformer
            upstream_transformer_name = network.get_upstream_transformer(
                model, connecting_element)
            if upstream_transformer_name is not None:
                upstream_transformer = model[upstream_transformer_name]
                is_center_tap = upstream_transformer.is_center_tap
            else:
                print(f'Warning - DG {upstream_transformer_name} is incorrectly '
                      'connected', flush=True)

            # if there is PV on the building, create an OpenDSS object for it
            if pv_kw > 0:
                # create the Photovoltaic object; assign voltages, phases and power
                pv = Photovoltaic(model)
                pv.name = 'solar_{}'.format(id_value)
                pv.connecting_element = connecting_element
                if upstream_transformer_name is not None:
                    pv.nominal_voltage = upstream_transformer.windings[1].nominal_voltage
                    pv.connection_type = upstream_transformer.windings[1].connection_type
                    phases = []
                    for ph_wdg in upstream_transformer.windings[1].phase_windings:
                        phases.append(Unicode(ph_wdg.phase))
                    if is_center_tap:
                        phases = [Unicode('A'), Unicode('B')]
                    pv.phases = phases
                pv.rated_power = pv_kw * 1000  # (stored in watts in ditto)
                pv.active_rating = 1.1 * pv_kw * 1000  # should be a parameter instead

                # assign the timeseries load profile
                if self.is_timeseries:
                    ts_csv = os.path.join(re_folder, 'feature_optimization.csv')
                    report_mtx = self._read_csv(ts_csv)
                    header_row = report_mtx.pop(0)
                    load_i = header_row.index('REopt:ElectricityProduced:PV:Total(kw)')
                    load_data = [float(row[load_i]) for row in report_mtx]
                    ts_i = header_row.index('Datetime')
                    timestamps = [row[ts_i] for row in report_mtx]
                    dt_format = '%Y/%m/%d %H:%M:%S'
                    delta = datetime.strptime(timestamps[1], dt_format) - \
                        datetime.strptime(timestamps[0], dt_format)
                    data_pu = [d / pv_kw for d in load_data]
                    ts_loc = self.timeseries_location
                    if ts_loc is not None:
                        if not os.path.exists(ts_loc):
                            os.makedirs(ts_loc)
                        load_path = os.path.join(ts_loc, 'pv_{}.csv'.format(id_value))
                        pu_path = os.path.join(ts_loc, 'pv_{}_pu.csv'.format(id_value))
                        self._write_single_column_csv(load_data, load_path)
                        self._write_single_column_csv(data_pu, pu_path)
                        timeseries = Timeseries(model)
                        timeseries.feeder_name = pv.feeder_name
                        timeseries.substation_name = pv.substation_name
                        timeseries.interval = delta.seconds / 3600.0
                        timeseries.data_type = 'float'
                        rel_pu_path = os.path.join(self.relative_timeseries_location,
                                                   'pv_{}_pu.csv'.format(id_value))
                        timeseries.data_location = rel_pu_path
                        timeseries.data_label = 'pv_feature_{}'.format(id_value)
                        timeseries.scale_factor = 1
                        pv.timeseries = [timeseries]
        return 1

    @staticmethod
    def create_building_map(geojson_content):
        """Get a dictionary mapping electrical junctions to buildings."""
        # create a map from the buildings to the electrical junctions
        building_map = {}
        for element in geojson_content["features"]:
            if 'properties' in element and 'type' in element['properties'] and \
                    'buildingId' in element['properties'] and \
                    element['properties']['type'] == 'ElectricalJunction':
                building_map[element['properties']['buildingId']] = \
                    element['properties']['id']
        return building_map

    @staticmethod
    def collect_building_elements(geojson_content):
        """Get a list of all building elements in a GeoJSON dictionary."""
        bldg_elements = []
        for element in geojson_content["features"]:
            if 'properties' in element and 'type' in element['properties'] and \
                    element['properties']['type'] == 'Building':
                bldg_elements.append(element)
        return bldg_elements

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
