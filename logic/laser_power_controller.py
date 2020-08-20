# -*- coding: utf-8 -*-
"""
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

import numpy as np
import time
import lmfit

from collections import OrderedDict
from qtpy import QtCore

from logic.generic_logic import GenericLogic
from core.connector import Connector
from core.statusvariable import StatusVar
from core.configoption import ConfigOption


class LaserPowerController(GenericLogic):
    """ This is the logic for controlling the power of one laser device

    This logic handle the multiple methods used to regulated the effective power sent by a laser to an experimental
    setup. It give a general interface to control and configure the power.

    Multiple methods can be used :
        - Use an AOM analog input or an electronic variable optical attenuators
            - Via a control value
            - Via a scanner analog output
        - Use a half wave plate with a polarizer
            - Via motor interface

    Additionally, a switch interface can be used in addition to the analog control to reach real zero. This can be
    useful for half wave plate with non total extinction.

    Direct laser power change leads to power variation and laser isntability so it should not be used as a main source
    of control. This module does not implement it. (See laser_logic.py for that)

    To configure the power, a power meter can be connected via procces_interface.

    ---

    This module control one output. The GUI can be connected to one or multiple logic module.

    Example configuration :

    green_power_controller:
        module.Class: 'laser_power_controller.LaserPowerController'
        connect:
            process_control: 'process_control'
            #scanner_logic: 'scanner_logic'
            #motor_hardware: 'half_wave_plate_power_"
            power_switch: 'power_switch'
            power_meter: 'power_meter'
        name: 'Green"
        color: '#00FF00'
    """

    process_control = Connector(interface='ProcessControlInterface', optional=True)
    scanner_logic = Connector(interface='ConfocalLogic', optional=True)
    motor_hardware = Connector(interface='MotorInterface', optional=True)
    power_switch = Connector(interface='SwitchInterface', optional=True)
    power_meter = Connector(interface='ProcessInterface', optional=True)

    name = ConfigOption('name', 'Laser')  # Match the name of the motor axis
    color = ConfigOption('color', 'lightgreen')  # Match the name of the motor axis

    config_control_limits = ConfigOption('control_limits', [None, None])  # In case hardware does not fix this
    power_switch_index = ConfigOption('power_switch_index', 0)  # If hardware has multiple switches
    scanner_channel_index = ConfigOption('scanner_channel_index', 3)  # To set the analog channel (4th is default)
    motor_axis = ConfigOption('motor_axis', 'phi')  # Match the name of the motor axis


    sigNewPowerRange = QtCore.Signal()

    # Configure panel
    sigNewDataPoint = QtCore.Signal()
    sigStarted = QtCore.Signal()
    sigFinished = QtCore.Signal()

    # Status variable containing control to model information
    model = StatusVar('model', 'aom')  # ['aom', 'half_wave_plate']
    model_params = StatusVar('voltages', {})

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        """ Initialisation performed during activation of the module. """

        # Check that one control is connected :
        if int(self.process_control.is_connected) + int(self.scanner_logic.is_connected) + \
                int(self.motor_hardware.is_connected) != 1:
            self.log.error('No or too many controller connected. Check configuration. ')
            return

        if self.model_params == {}:
            _, _, estimator = self.get_model_functions()
            self.model_params = estimator().valuesdict()

    def on_deactivate(self):
        pass

    def _get_control(self):
        """ Get the value of the control parameter """
        if self.process_control.is_connected:
            return self.process_control().get_control_value()
        elif self.scanner_logic.is_connected:
            return self.scanner_logic().get_position()[self.scanner_channel_index]
        elif self.motor_hardware.is_connected:
            return self.motor_hardware().get_pos()[self.motor_axis]

    def _set_control(self, value):
        """ Set the value of the control parameter """
        limit_low, limit_high = self._get_control_limits()
        if not (limit_low <= value <= limit_high):
            self.log.error('Value {} is out of bound : [{}, {}]'.format(value, limit_low, limit_high))
            return

        if self.process_control.is_connected:
            return self.process_control().set_control_value(value)
        elif self.scanner_logic.is_connected:
            return self.scanner_logic().set_position('power_control', **{'xyza'[self.scanner_channel_index]: value})
        elif self.motor_hardware.is_connected:
            return self.motor_hardware().move_abs({str(self.motor_axis): value})
        else:
            self.log.error('No connected controller anymore. Can not set control value.')

    def _get_control_limits(self):
        """ Get the control limit, either imposed by hardware or by config """
        if self.process_control.is_connected:
            limits = self.process_control().get_control_limit()
        elif self.scanner_logic.is_connected:
            # The line bellow should not do things like this, but confocal_logic does not provide any other way.
            limits = self.scanner_logic()._scanning_device.get_position_range()[self.scanner_channel_index]
        elif self.motor_hardware.is_connected:
            constraints = self.motor_hardware().get_constraints()[str(self.motor_axis)]
            limits = constraints['pos_min'], constraints['pos_max']
        if self.config_control_limits[0] is not None:
            limit_low = max(self.config_control_limits[0], limits[0])
        else:
            limit_low = limits[0]
        if self.config_control_limits[1] is not None:
            limit_high = min(self.config_control_limits[1], limits[1])
        else:
            limit_high = limits[1]
        return limit_low, limit_high

    def get_power(self):
        """ Get the power sent to the setup. Returns zero is switch is off.

        @return (float): Power sent to setup
        """
        return self.get_power_setpoint() if self.get_switch_state() is not False else 0.

    def get_power_setpoint(self):
        """ Get the power set, whether switch state is on or off.

         @return (float): Power set in logic """
        direct, _, _ = self.get_model_functions()
        return direct(self.model_params, self._get_control())

    def set_power(self, value):
        """ Set the power to a given value

        @param (float) value: The power in Watt to set
        """
        if value < self.power_min:
            self.log.error('Can not set power less than {}. Use switch to go bellow.')

        if value > self.power_max:
            self.log.error('Can not set power more than {}. Increase laser power and recompute model.')

        _, inverse, _ = self.get_model_functions()
        self._set_control(inverse(self.model_params, value))

    @property
    def power_max(self):
        """ Get the maximum possible power with current model """
        direct, _, _ = self.get_model_functions()
        mini, maxi = self._get_control_limits()
        return np.max([direct(self.model_params, mini), direct(self.model_params, maxi)])

    @property
    def power_min(self):
        """ Get the maximum possible power with current model """
        direct, _, _ = self.get_model_functions()
        mini, maxi = self._get_control_limits()
        return np.min([direct(self.model_params, mini), direct(self.model_params, maxi)])

    def get_switch_state(self):
        """ Returns the current switch state of the laser

         @return (bool|None): Boolean state if switch is connected else None
         """
        if self.power_switch.is_connected:
            return self.power_switch().getSwitchState(self.power_switch_index)
        else:
            return None

    def get_model_functions(self, model=None):
        """ Get the direct, inverse and estimator for a given model

        @param (str) model: The model to use 'aom' or 'half_wave_plate'

        @return (tuple(function)): A tuple of the direct, inverse and estimator function
        """
        if model is None:
            model = self.model
        if model == 'aom':
            return self._aom_model, self._aom_model_inverse, self._aom_model_estimator

    # List of models use to map control value to laser power
    # They need to be monotone on the control limit range to have a defined inverse function

    def _aom_model(self, params, control):
        """ Compute the expected power given a set of parameters and a control value

        @param (dict) params: A dictionnary containing the models keys :
            - 'x0', 'sigma', 'slope', 'max', 'beta'
        @param (float) control: The input control value

        @return: The predicted laser power
        """
        X = np.array([control]) / params['sigma']
        X[X == 0] = np.NaN  # Set zero as NaN to treat it separately
        denominator = 1 + (1/X)**params['slope']
        result = params['max'] / denominator**params['beta']
        result[np.isnan(result)] = 0
        return result[0]

    def _aom_model_inverse(self, params, power):
        """ Compute the control value to use given a set of parameters to set a given power

        @param (dict) params: A dictionnary containing the models keys :
            - 'x0', 'sigma', 'slope', 'max', 'beta'
        @param (float) power: The input control value

        @return: The predicted laser power
        """
        power = np.array([power])
        power[power == 0] = np.NaN  # Set zero as NaN to treat it separately
        denominator = (params['max']/power)**params['beta'] - 1
        X = (1 / denominator)**(1/params['slope'])
        result = X*params['sigma']
        result[np.isnan(result)] = 0
        return result[0]

    def _aom_model_estimator(self, control=None, power=None):
        """ Compute a fit starting point for the AOM model """
        if control is None:
            control = np.array(self._get_control_limits())
        if power is None:
            power = np.array([1])
        params = lmfit.Parameters()
        params.add('max', value=power.max())
        params.add('sigma', value=(control.max() - control.min())/2, vary=True)
        params.add('slope', value=5, vary=True)
        params.add('beta', value=1, vary=True)
        return params
