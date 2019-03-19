# -*- coding: utf-8 -*-

"""
This module contains the Qudi Hardware dummy module for stepper interface

---

Qudi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Qudi is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Qudi. If not, see <http://www.gnu.org/licenses/>.

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

import telnetlib
import time
import re

from core.module import Base, ConfigOption
from interface.steppers_interface import SteppersInterface


class DummyStepper(Base, SteppersInterface):
    """
    """

    _modtype = 'DummyStepper'
    _modclass = 'hardware'


    _default_axis = {
        'voltage_range': [0, 60],
        'frequency_range': [0, 10000],
        'position_range': [0, 5],
        'feedback': False,
        'frequency': 20,
        'voltage': 30,
        'capacitance': None,
        'busy': False
    }
    _connected = False

    _axis_config = {
        'x': {
            'id': 1,
            'position_range': [0, 5],
            'voltage_range': [0, 50],
            'frequency_range': [0, 1000],
            'feedback': False,
            'frequency': 20,
            'voltage': 30
        },
        'y': {
            'id': 2,
            'position_range': [0, 5],
            'voltage_range': [0, 50],
            'frequency_range': [0, 1000],
            'feedback': False,
            'frequency': 20,
            'voltage': 30
        },
        'z': {
            'id': 3,
            'position_range': [0, 5],
            'voltage_range': [0, 50],
            'frequency_range': [0, 1000],
            'feedback': False,
            'frequency': 20,
            'voltage': 30
        },

    }




    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """

        self._check_axis()
        self._check_connection()
        self._connect(attempt=1)

        if self.connected:
            self._initialize_axis()

    def _check_axis(self):
        """ Internal function - check that the axis in the config file are ok and complete them with default
        """
        for name in self._axis_config:
            if 'id' not in self._axis_config[name]:
                self.log.error('id of axis {} is not defined in config file.'.format(name))
            # check _axis_config and set default value if not defined
            for key in self._default_axis:
                if key not in self._axis_config[name]:
                    self._axis_config[name][key] = self._default_axis[key]

    def _check_connection(self):
        """ Internal function - Check the connection config is ok
        """
        pass

    def _initialize_axis(self):
        """ Internal function - Initialize axis with the values from the config
        """
        for name in self._axis_config:
            self.capacitance(name)  # capacitance leaves axis in step mode
            self.frequency(name, self._axis_config[name]['frequency'])
            self.voltage(name, self._axis_config[name]['voltage'])

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.
        """
        self._disconnect()

    def _connect(self, attempt=7):
        """
        Try to connect to the ANC300
        """
        self.connected = True



    def _disconnect(self, keep_active=False):
        """ Close connection with ANC after setting all axis to ground (except if keep_active is true)
        """
        self.connected = False

    def _parse_axis(self, axis):
        """
        Take an valid axis or list/tuple of axis and return a list with valid axis name.
        By doing this we have the same universal axis input for all module functions
        'x' -> ['x']
        1 -> ['x']
        ['x', 2] -> ['x', 'y']
        """
        if type(axis) == int or type(axis) == str:
            return [self._get_axis_name(axis)]
        if type(axis)==list or type(axis)==tuple:
            result = []
            for a in axis:
                result.append(self._get_axis_name(a))
            return result
        else:
            self.log.error('Can not parse axis : {}'.format(axis))

    def _get_axis_name(self, axis):
        """
        Get an axis identifier (integer or name), and return axis name after checking axis is valid
        """
        if type(axis) == str:
            if axis in self._axis_config:
                return axis
        if type(axis) == int:
            for name in self._axis_config:
                if self._axis_config[name]['id'] == axis:
                    return name
        # if still not found, we error
        self.log.error('Axis {} is not defined in config file'.format(axis))

    def _parse_result(self, axis, result):
        """
        Take a valid axis input and list result and convert result to original format
        'x' [1000] -> 10000
        ['x', 3] [0.5, 1.2] -> [0.5, 1.2]
        """
        if type(axis) == int or type(axis) == str:
            return result[0]
        if type(axis) == tuple:
            return tuple(result)
        else:
            return result

    def _get_config(self, axis, key):
        """
        Get a value in axis config for a key for a given axis input and return with same format
        """
        parsed_axis = self._parse_axis(axis)
        result = []
        for ax in parsed_axis:
            value = self._axis_config[ax][key]
            if type == list:  # protect mutable shallow array (ranges)
                result.append(tuple(value))
            else:
                result.append(value)
        return self._parse_result(axis, result)

    def _parse_value(self, axis, ax, value):
        """
        For a given axis input and a given ax, return the value that make the most sense
        """
        if type(value) == float or type(value) == int:  # a single number : we return it
            return value
        elif type(value) == list or type(value) == tuple:  # an array
            if len(value) == 1:  # a single object in array : we return it
                return value[0]
            elif len(value) == len(axis):  # one to one correspondence with axis
                return value[axis.index(ax)]
            else:
                self.log.error('Could not set value for axis {}, value list length is incorrect')

    def _in_range(self, value, value_range, error_message=None):
        """ Internal function - Check that a value is in range and eventually error of not """
        mini, maxi = value_range
        ok = mini <= value <= maxi
        if not ok and error_message is not None:
            self.log.error('{} - Value {} in not in range [{}, {}'.format(error_message, value, mini, maxi))
        return ok

    def axis(self):
        """ steppers_interface - Return a tuple of all axis identifiers"""
        return tuple(self._axis_config.keys())

    def voltage_range(self, axis):
        """ steppers_interface (overloaded) - Return the voltage range of one (or multiple) axis """
        return self._get_config(axis, 'voltage_range')

    def frequency_range(self, axis):
        """ steppers_interface (overloaded) - Return the frequency range of one (or multiple) axis """
        return self._get_config(axis, 'frequency_range')

    def position_range(self, axis):
        """ steppers_interface (overloaded) - Return the position range of one (or multiple) axis """
        return self._get_config(axis, 'position_range')

    def voltage(self, axis, value=None, buffered=False):
        """
        steppers_interface (overloaded)
        Function that get or set the voltage of one ore multiple axis
        :param axis: axis input : 'x', 2, ['z', 3]...
        :param value: value for axis : 1.0, [1.0], [2.5, 2.8]...
        :param buffered: if set to True, just return the last read voltage without asking the controller
        :return: return the voltage of the axis with the same format than axis input
        """
        parsed_axis = self._parse_axis(axis)
        if value is not None:
            for ax in parsed_axis:
                new_value = self._parse_value(axis, ax, value)
                if self._in_range(new_value, self.voltage_range(ax), 'Voltage out of range'):
                    command = "set voltage - axis : {} - voltage : {}".format(self._axis_config[ax]['id'], new_value)
                    self.log.debug(command)

        if not buffered:
            for ax in parsed_axis:
                commmand = "get voltage - axis : {}".format(self._axis_config[ax]['id'])
                self.log.debug(command)

        return self._get_config(axis, 'voltage')

    def frequency(self, axis, value=None, buffered=False):
        """
        steppers_interface (overloaded)
        Function that get or set the frequency of one ore multiple axis
        :param axis: axis input : 'x', 2, ['z', 3]...
        :param value: value for axis : 100, [200], [500, 1000]...
        :param buffered: if set to True, just return the last read voltage without asking the controller
        :return: return the frequency of the axis with the same format than axis input
        """
        parsed_axis = self._parse_axis(axis)
        if value is not None:
            for ax in parsed_axis:
                new_value = int(self._parse_value(axis, ax, value))
                if self._in_range(new_value, self.frequency_range(ax), 'Frequency out of range'):
                    command = "set frequency - axis : {} - frequency : {}".format(self._axis_config[ax]['id'], new_value)
                    self.log.debug(command)

        if not buffered:
            for ax in parsed_axis:
                commmand = "get frequency axis : {}".format(self._axis_config[ax]['id'])
                self.log.debug(command)

        return self._get_config(axis, 'frequency')

    def capacitance(self, axis, buffered=False):
        """
        steppers_interface (overloaded)
        Function that get the capacitance of one ore multiple axis
        :param axis: axis input : 'x', 2, ['z', 3]...
        :param buffered: buffered: if set to True, just return the last read capacitance without asking the controller
        will be None if never read
        """
        parsed_axis = self._parse_axis(axis)
        if not buffered:
            for ax in parsed_axis:
                command = "get capacitance axis {}".format(self._axis_config[ax]['id'])
                self.log.debug(command)
                self._axis_config[ax]['capacitance'] = 1

        return self._get_config(axis, 'capacitance')

    def steps(self, axis, number):
        """
        steppers_interface (overloaded)
        Function to do n (or n, m...) steps one one (or several) axis
        :param axis input : 'x', 2, ['z', 3]...
        :param number: 100, [200], [500, 1000]...
        """
        parsed_axis = self._parse_axis(axis)
        for ax in parsed_axis:
            if self._axis_config[ax]['busy']:
                self.warning('Stepping might not work while axis {} in capacitance measurement'.format(ax))
            number_step_axis = int(self._parse_value(axis, ax, number))
            if number_step_axis > 0:
                self.log.debug('Do steps - axis : {} - number : {}'.format(self._axis_config[ax]['id'], number_step_axis))

    def stop(self, axis=None):
        """ steppers_interface (overloaded) - Stop all movement on one, several or all (if None) axis"""
        if axis is None:
            axis = list(self._axis_config.keys())
        parsed_axis = self._parse_axis(axis)
        for ax in parsed_axis:
            self.log.debug('Stop movement axis {}'.format(self._axis_config[ax]['id']))
        self.log.info("All piezo axis stopped")
