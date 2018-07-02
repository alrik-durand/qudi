# -*- coding: utf-8 -*-

"""
A module for controlling processes via PID regulation.

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

import copy
# import numpy as np

from core.module import Connector, ConfigOption, StatusVar
from core.util.mutex import Mutex
from logic.generic_logic import GenericLogic
from qtpy import QtCore


class PIDLogic(GenericLogic):
    """ Monitor or control a process

    This module takes data_field list as input and tries to log every entry.
    To get or set properties, this module tries to call the get_<field> and set_<field> function of the hardware.

    To access data from the GUI, only one function is needed get_data by specifying a field.

    Data can be any type, eventually tuple for multiple sensors value

    """
    _modclass = 'pidlogic'
    _modtype = 'logic'

    hardware = Connector(interface='PIDControllerInterface')
    savelogic = Connector(interface='SaveLogic')
    _data_field = ConfigOption('data_field', tuple('process_value'))
    _permitted_data_field = ('enabled', 'setpoint', 'process_value', 'control_value', 'kp', 'kd', 'ki')
    
    _timestep = ConfigOption('timestep', 1.)  # update time in seconds
    _loop_enabled = False

    # signals
    sigUpdate = QtCore.Signal()

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        self.threadlock = Mutex()

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """
        self._hardware = self.hardware()
        self._save_logic = self.savelogic()

        # Check config file
        for field in self._data_field:
            if field not in self._permitted_data_field:
                self.log.error('{} field is not present in any interface'.format(field))
                return

        self._data = {}
        for key in self._data_field:
            self._data[key] = []

        self._loop_enabled = True
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(self._timestep)
        self.timer.timeout.connect(self._loop)
        self.timer.start(self._timestep)

    def on_deactivate(self):
        """ Perform required deactivation. """
        self._loop_enabled = False
        pass

    def _loop(self):
        """ Execute step in the data acquisition loop: save one of each control and process values
        """

        if not self._loop_enabled:  # let's stop here
            return  # prevent trying to read hardware after deactivation

        for key in self._data_field:
            value = getattr(self._hardware, 'get_{}'.format(key))()
            self._data['key'].append(value)

        self.sigUpdateDisplay.emit()
        self.timer.start(self._timestep)

    def get_data(self, key, start=0):
        """ Get an array of data entry for the given key from a start index

        @param str key: key of the requested data
        @param int start: start point of the array required

        @ return list(any): raw data for given field

        Main function to access data history.
        The array is deepcopied to prevent modification by user module.
        As a consequence, real time logging could take lots of resource. That is why it's better
        to access only the last unread data in by keeping track of entry index.
        """
        if key not in self._data_field:
            self.log.error('Data field {} is not acquired. Please check logic configuration parameters.'.format(key))
        length = len(self._data[key])
        if length > 0 and start >= length:
            self.log.error('Start index is out of the array')
        else:
            return copy.deepcopy(self._data[key][start:])

    def get_timestep(self):
        """ Return current timestep between data entries

        """
        return self._timestep

    def get_fields(self):
        """ Return enabled features

        """
        return self._data_field

    def save_data(self, path=None, filename=None, extension='.dat', start=0, end=None, step=1):
        """ Save all acquired data to file

        @param str path: path of where to save data
        @param str filename: filename to save
        @param str extension: extension for file
        @param int start: start index of the entry to save in the file
        @param int end: stop index of the entry to save in the file
        @param int step: step index of the entry to save in the file

        If a lot of data is acquired, parameters give a way to reduce disk usage
        """
        pass

    def set(self, key, value):
        """ Set a value on the hardware for a given key

        @param key: key of the value to set
        @param value: value to set

        @return any: the value returned by the hardware function
        """
        # Check that hardware module has setter function
        setter = 'set_{}'.format(key)
        if not hasattr(self._hardware, setter):
            self.log('Setting {} is not possible, hardware module has no function {}'.format(key, setter))
            return
        # If a get_X_limits exist in hardware, let's use it and warning if out of range
        limits = self.limits(key)
        if limits:  # True if not None
            mini, maxi = limits
            if not mini <= value <= maxi:
                self.log.warning('{} value {} is out of range [{}, {}]'.format(key, value, mini, maxi))
        # Now set it
        return getattr(self._hardware, 'set_'.format(key))(value)

    def limits(self, key):
        """ Get the limit tuple from the hardware for a given field

        @param key: key of the field

        @return tuple(any): limit returned by the hardware module

        This function can be used to check if limit are available for a given field
        """
        limit_getter = 'get_{}_limits'.format(key)
        if hasattr(self._hardware, limit_getter):
            return getattr(self._hardware(limit_getter))
        else:
            return None

