# -*- coding: utf-8 -*-

"""
A module for controlling the steppers via analog user input.

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

from core.module import Connector, ConfigOption, StatusVar
from core.util.mutex import Mutex
from logic.generic_logic import GenericLogic
from qtpy import QtCore
import numpy as np
import time

class AnalogSteppersLogic(GenericLogic):
    """
    Control xyz steppers via a joystick controller

    The idea is to use joystick axis to control the setpoint position (continuous value) and execute steps based on the
    discretisation of the space.
    """
    _modclass = 'analogstepperslogic'
    _modtype = 'logic'

    # declare connectors
    hardware = Connector(interface='SteppersInterface')
    joystick = Connector(interface='JoystickLogic')
    _button_interlock = ConfigOption('button_interlock', 'right_left')  # if this button is not pushed, do nothing

    _hardware_frequency = ConfigOption('hardware_frequency', 100)
    _hardware_voltage = ConfigOption('hardware_voltage', 30)
    _axis = ConfigOption('axis', ('x', 'y', 'z'))
    _xy_max_velocity = ConfigOption('xy_max_velocity', 100)  # the maximum number of steps by second
    _z_max_velocity = ConfigOption('z_max_velocity', 20)  # the maximum number of steps by second

    _joystick_setpoint_position = np.zeros(3)
    _hardware_position = np.zeros(3)

    _enabled = False

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        self.threadlock = Mutex()

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """
        self._hardware = self.hardware()
        self._joystick = self.joystick()

        self._joystick.sig_new_frame.connect(self.on_new_frame)

        self._joystick.signal_left_up_pushed.connect(lambda: self.discrete_movement((0, 1, 0)))
        self._joystick.signal_left_down_pushed.connect(lambda: self.discrete_movement((0, -1, 0)))
        self._joystick.signal_left_left_pushed.connect(lambda: self.discrete_movement((-1, 0, 0)))
        self._joystick.signal_left_right_pushed.connect(lambda: self.discrete_movement((1, 0, 0)))
        self._joystick.signal_left_shoulder_pushed.connect(lambda: self.discrete_movement((0, 0, -1)))
        self._joystick.signal_right_shoulder_pushed.connect(lambda: self.discrete_movement((0, 0, 1)))

        self.setup_axis()

    def setup_axis(self):
        """ Set axis as in config file"""
        for axis in self._axis:
            if axis:
                self._hardware.frequency(axis, self._hardware_frequency)
                self._hardware.voltage(axis, self._hardware_voltage)


    def on_deactivate(self):
        """ Perform required deactivation. """
        pass

    def _get_interlock(self):
        """ This function return whether the interlock button is pressed to prevent accidental change """
        return self._joystick.get_last_state()['buttons'][self._button_interlock]



    def on_new_frame(self):
        """ Executed function when a new frame from the joystick controller is received """

        if not self._get_interlock():
            return

        state = self._joystick.get_last_state()
        fps = self._joystick.get_fps()

        y = float(state['axis']['left_vertical'])
        x = float(state['axis']['left_horizontal'])
        z = float(-state['axis']['left_trigger'] + state['axis']['right_trigger'])

        # 1. Let's correct the "deadzone" noise
        deadzone = 0.05
        if -0.05 < x < 0.05:
            x = 0
        if -0.05 < y < 0.05:
            y = 0
        if -0.05 < z < 0.05:
            z = 0

        # 2. Let's use a power to add "precision"
        power = 3.0
        x = x**power / fps * self._xy_max_velocity
        y = y**power / fps * self._xy_max_velocity
        z = z**power / fps * self._z_max_velocity

        self.discrete_movement((x, y, z))

    def discrete_movement(self, relative_movement):
        """ Function to do a discrete relative movement """
        if not self._get_interlock():
            return

        self._joystick_setpoint_position += relative_movement
        self._update_hardware()

    def _update_hardware(self):
        """ Eventually send command to hardware if position has changed
        """
        before = self._hardware_position
        after = np.floor(self._joystick_setpoint_position)

        difference = after - before
        changed = False
        for index, axis in enumerate(self._axis):
            if axis:
                steps = difference[int(index)]
                if steps:
                    self._hardware.steps(axis, steps)
                    changed = True
        self._hardware_position = after
        if changed:
            self.log.debug('New position ({}, {}, {})'.format(*after))
#            print('New position ({}, {}, {})'.format(*after)) # print is bad but log.debug is too slow


    def hello(self):
        """ Greet humans properly """

        axis = self._axis[0]
        notes = {'c': 261, 'd': 294, 'e': 329, 'f': 349, 'g': 391, 'gS': 415, 'a': 440, 'aS': 455, 'b': 466, 'cH': 523,
                 'cSH': 554, 'dH': 587, 'dSH': 622, 'eH': 659, 'fH': 698, 'fSH': 740, 'gH': 784, 'gSH': 830, 'aH': 880}

        first_section = [('a', 500), ('a', 500), ('a', 500), ('f', 350), ('cH', 150), ('a', 500), ('f', 350),
                         ('cH', 150), ('a', 650), ('', 500), ('eH', 500), ('eH', 500), ('eH', 500), ('fH', 350),
                         ('cH', 150), ('gS', 500), ('f', 350), ('cH', 150), ('a', 650), ('', 500)]
        second_section = [('aH', 500), ('a', 300), ('a', 150), ('aH', 500), ('gSH', 325), ('fSH', 125), ('fH', 125),
                          ('fSH', 250), ('', 325), ('aS', 250), ('dSH', 500), ('dH', 325), ('cSH', 175), ('cH', 125),
                          ('b', 125), ('cH', 250), ('', 350)]
        variant_1 = [('f', 250), ('gS', 500), ('f', 350), ('a', 125), ('cH', 500), ('a', 375), ('cH', 125), ('eH', 650),
                     ('', 500)]
        variant_2 = [('f', 250), ('gS', 500), ('f', 375), ('cH', 125), ('a', 500), ('f', 375), ('cH', 125), ('a', 650),
                     ('', 650)]
        total = first_section + second_section + variant_1 + second_section + variant_2
        count = 0
        up = True
        for note, duration in total:
            if note != '':
                frequency = notes[note]
                steps = int(frequency * (float(duration)/1000.))
                self._hardware.frequency(axis, frequency)
                if not up:
                    steps = -steps
                count += steps
                self._hardware.steps(axis, steps)
            time.sleep((duration + 50)/1000)
            up = not up
        self._hardware.steps(axis, -count)  # Back to origin
