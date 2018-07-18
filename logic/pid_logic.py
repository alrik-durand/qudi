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
import time
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

    _active_fields = ConfigOption('active_fields')  # list of active fields on the hardware
    # This field are accessible via the logic but their value is not logged

    _logged_field = ConfigOption('logged_field', None) # list of fields to log
    # If None, all active fields will be monitored

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
        if self._logged_field is None:
            self._logged_field = self._active_fields

        for field in self._data_field:
            if field not in self._active_fields + self._logged_field:
                self.log.error('{} field is not present in any interface'.format(field))
                return

        self._data = {}
        for key in self._logged_field:
            self._data[key] = []

        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._loop)
        self.start_loop()

    def on_deactivate(self):
        """ Perform required deactivation. """
        self.stop_loop()

    def start_loop(self):
        """ Start the data recording loop.
        """
        self._loop_enabled = True
        self.timer.start(self._timestep)

    def stop_loop(self):
        """ Stop the data recording loop.
        """
        self._loop_enabled = False

    def _loop(self):
        """ Execute step in the data acquisition loop: save one of each control and process values
        """

        if not self._loop_enabled:  # let's stop here
            return  # prevent trying to read hardware after deactivation

        for key in self._logged_field:
            value = self.parameter(key)
            self._data[key].append(value)

        self._data['time'].append(time.time())

        self.sigUpdateDisplay.emit()
        self.timer.start(self._timestep)

    def get_data(self, key):
        """ Get an array of data entry for the given key

        @param str key: key of the requested data

        @return list(any): raw data for given field

        Main function to access data history.
        """
        if key not in self._logged_field:
            self.log.error('Data field {} is not acquired. Please check logic configuration parameters.'.format(key))
        return self._data[key]

    def timestep(self, value=None):
        """ Function to get or change the timestep between entries """
        if value:
            self._timestep = value
            self.timer.clear()
            self.timer.start(self._timestep)
        return self._timestep

    def get_fields(self):
        """ Return enabled features

        """
        return {'active': self._active_fields, 'logged': self._logged_field}

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

    def parameter(self, key, value=None):
        """ Get or set a value of the hardware for a given key

        @param key: key of the value to set
        @param value: value to set

        @return any: the value returned by the hardware function
        """
        if value:
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
            return getattr(self._hardware, setter)(value)
        # else just get
        getter = 'get_{}'.format(key)
        if not hasattr(self._hardware, getter):
            self.log('Getting {} is not possible, hardware module has no function {}'.format(key, getter))
            return
        return getattr(self._hardware, getter)

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

