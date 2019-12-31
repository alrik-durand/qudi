# -*- coding: utf-8 -*-
"""
This file contains the Qudi logic class for performing polarization dependence measurements.

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

import time
import numpy as np
from core.connector import Connector
from logic.generic_logic import GenericLogic
from core.statusvariable import StatusVar
from core.configoption import ConfigOption
from qtpy import QtCore


class PolarizationLogic(GenericLogic):
    """This logic module rotates polarization and records signal as a function of angle.

    """

    # declare connectors
    counterlogic = Connector(interface='CounterLogic')
    savelogic = Connector(interface='SaveLogic')
    motor = Connector(interface='MotorInterface')

    motor_axis = ConfigOption(name='motor_axis', default='phi')

    main_channel = ConfigOption(name='main_channel', default=0)
    secondary_channel = ConfigOption(name='secondary_channel', default=None)

    signal_rotation_finished = QtCore.Signal()
    signal_start_rotation = QtCore.Signal()

    _resolution = StatusVar('resolution', 90)
    _time_per_point = StatusVar('time_per_point', 1)
    _background_value = StatusVar('background_value', 0)
    _background_time = StatusVar('background_time', 5)

    _x_axis = np.array([])
    _y_axis = np.array([])
    _y2_axis = np.array([])
    _current_index = 0

    sigDataUpdated = QtCore.Signal()
    sigStateChanged = QtCore.Signal()
    sigMeasurementParametersChanged = QtCore.Signal()
    sigBackgroundParametersChanged = QtCore.Signal()

    _stop_requested = False

    def on_activate(self):
        """ Initialisation performed during activation of the module. """
        # Connect signals
        self.counterlogic().sigCountStatusChanged.connect(self.abort, QtCore.Qt.DirectConnection)

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module. """
        self.counterlogic().sigCountStatusChanged.disconnect()

    @property
    def motor_constraints(self):
        return self.motor().get_constraints()[self.motor_axis]

    @property
    def motor_velocity(self):
        return self.motor().get_velocity()[self.motor_axis]

    @property
    def motor_position(self):
        return self.motor().get_pos()[self.motor_axis]

    def set_motor_position(self, value):
        """ Set the motor to a given position

        @param (float) value: The new position to set

        @return (float): Time (in second) needed to get to this position
        """
        if self.motor_constraints['pos_min'] < value < self.motor_constraints['pos_max']:
            previous_position = self.motor_position
            self.motor().move_abs({self.motor_axis: value})
            return abs((previous_position-value)/self.motor_velocity)
        else:
            return 0

    @property
    def resolution(self):
        return self._resolution

    @resolution.setter
    def resolution(self, value):
        if 0 < value != self._resolution and self.module_state() != 'locked':
            self._resolution = int(value)
            self.sigMeasurementParametersChanged.emit()

    @property
    def time_per_point(self):
        return self._time_per_point

    @time_per_point.setter
    def time_per_point(self, value):
        counter_time_per_point = 1/self.counterlogic().get_count_frequency()
        if value == 0 or not np.isclose(int(value/counter_time_per_point), value/counter_time_per_point):
            self.log.warning('Polarization measurement time per point must be a multiple of counting resolution')
            self.sigMeasurementParametersChanged.emit()
        else:
            if self.module_state() != 'locked' and self._time_per_point != value:
                self._time_per_point = value
                self.sigMeasurementParametersChanged.emit()

    @property
    def background_value(self):
        return self._background_value

    @background_value.setter
    def background_value(self, value):
        if 0 <= value != self._background_value:
            self._background_value = value
            self.sigBackgroundParametersChanged.emit()
            self.sigDataUpdated.emit()

    @property
    def background_time(self):
        return self._background_time

    @background_time.setter
    def background_time(self, value):
        counter_time_per_point = 1 / self.counterlogic().get_count_frequency()
        if value == 0 or not np.isclose(int(value/counter_time_per_point), value/counter_time_per_point):
            self.log.warning('Polarization background measurement time must be a multiple of counting resolution.')
            self.sigBackgroundParametersChanged.emit()
        elif self._background_time != value:
            self._background_time = value
            self.sigBackgroundParametersChanged.emit()

    def reset_motor(self, wait=False):
        """ Reset the motor to its origin

        @param (bool) wait: Whether to wait for the motor to be reset before returning
        """
        reset_time = self.set_motor_position(0)
        if wait:
            time.sleep(reset_time)

    def run(self):
        """ Runs a polarization measurement """
        if self.counterlogic().module_state() == 'idle':
            self.counterlogic().startCount()
        self._stop_requested = False
        self.module_state.lock()
        self.sigStateChanged.emit()
        self._x_axis = np.linspace(start=0, stop=180, num=self.resolution)
        self._y_axis = np.full(self.resolution, np.nan)
        if self.use_secondary_channel:
            self._y2_axis = np.full(self.resolution, np.nan)
        self.sigDataUpdated.emit()
        self.reset_motor(wait=True)
        bin_per_step = int(self.counterlogic().get_count_frequency() * self.time_per_point)

        for i, x in enumerate(self._x_axis):
            self._current_index = i
            move_time = self.set_motor_position(x)
            time.sleep(move_time)
            time.sleep(self.time_per_point)
            self._y_axis[i] = self.counterlogic().countdata[self.main_channel, -bin_per_step:-1].sum()
            self._y_axis[i] /= self.time_per_point
            if self.use_secondary_channel:
                self._y2_axis[i] = self.counterlogic().countdata[self.secondary_channel, -bin_per_step:-1].sum()
                self._y2_axis[i] /= self.time_per_point
            if self._stop_requested:
                break
            self.sigDataUpdated.emit()

        self.sigDataUpdated.emit()
        self.reset_motor(wait=True)
        self.module_state.unlock()
        self.sigStateChanged.emit()

    def abort(self):
        """ Abort the acquisition in progress - the motor will reset to zero """
        if self.module_state() == 'locked':
            self._stop_requested = True

    def take_background(self, *args, duration=None):
        """ Measure signal for a given time and save it as new background value """
        if self.module_state() == 'locked':
            return
        if self.counterlogic().module_state() == 'idle':
            self.counterlogic().startCount()
        duration = duration if duration is not None else self.background_time
        self.module_state.lock()
        self.sigStateChanged.emit()
        bin_number = int(self.counterlogic().get_count_frequency() * duration)
        real_duration = bin_number*(1/self.counterlogic().get_count_frequency())
        time.sleep(real_duration)
        signal = float(self.counterlogic().countdata[self.main_channel, -bin_number:-1].sum())
        self.background_value = signal / real_duration
        self.module_state.unlock()
        self.sigStateChanged.emit()

    @property
    def use_secondary_channel(self):
        return self.secondary_channel is not None

    def get_data(self):
        """ Return current data from the last measurement"""
        return self._x_axis, self._y_axis-self.background_value, self._y2_axis-self.background_value

    def save(self):
        pass
