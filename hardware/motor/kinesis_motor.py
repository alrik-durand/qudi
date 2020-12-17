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

import os
import ctypes as ct
from core.module import Base
from core.configoption import ConfigOption


class KinesisMotor(Base):
    """ This class is implements communication with Thorlabs motors via Kinesis dll

    Example config for copy-paste:

    kinesis:
        module.Class: 'motor.kinesis_motor.KinesisMotor'
        dll_folder: 'C:\Program Files\Thorlabs\Kinesis'
        serial_numbers: [000000123]
        names: ['phi']

    This hardware file have been develop for the TDC001/KDC101 rotation controller. It should work with other motors
    compatible with kinesis. Please be aware that Kinesis dll can be a little buggy sometimes.
    In particular conversion to real unit is sometimes broken. The following page helped me :
    https://github.com/MSLNZ/msl-equipment/issues/1

    """
    dll_folder = ConfigOption('dll_folder', default=r'C:\Program Files\Thorlabs\Kinesis')
    dll_file = ConfigOption('dll_ffile', default='Thorlabs.MotionControl.TCube.DCServo.dll')
    serial_numbers = ConfigOption('serial_numbers', missing='error')
    names = ConfigOption('names', missing='error')
    polling_rate_ms = ConfigOption('polling_rate_ms', default=200)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dll = None
        self._codes = None
        self._serial_numbers = None

    def on_activate(self):
        """ Module activation method """
        os.environ['PATH'] = str(self.dll_folder) + os.pathsep + os.environ['PATH']  # needed otherwise dll don't load
        self._dll = ct.cdll.LoadLibrary(self.dll_file)
        self._dll.TLI_BuildDeviceList()

        self._serial_numbers = {}

        for i, name in enumerate(self.names):
            serial_number = ct.c_char_p(str(self.serial_numbers[i]).encode('utf-8'))
            self._dll.CC_Open(serial_number)
            self._dll.CC_LoadSettings(serial_number)
            self._dll.CC_StartPolling(serial_number, ct.c_int(200))
            self._serial_numbers[name] = serial_number

    def on_deactivate(self):
        """ Disconnect from hardware on deactivation. """
        for name, serial_number in self._serial_numbers.items():
            self._dll.CC_ClearMessageQueue(serial_number)
            self._dll.CC_StopPolling(serial_number)
            self._dll.CC_Close(serial_number)

    def get_position(self, name):
        """ Get the position in real work unit of the motor """
        serial_number = self._serial_numbers[name]
        position = self._dll.CC_GetPosition(serial_number)
        real_unit = ct.c_double()
        self._dll.CC_GetRealValueFromDeviceUnit(serial_number, position, ct.byref(real_unit), 0)
        return real_unit.value

    def set_position(self, name, value):
        """ Set the position in real work unit of an axis """
        serial_number = self._serial_numbers[name]
        device_unit = ct.c_int()
        self._dll.CC_GetDeviceUnitFromRealValue(serial_number, ct.c_double(value), ct.byref(device_unit), 0)
        self._dll.CC_MoveToPosition(serial_number, device_unit)

    def home(self, name):
        """ Send a home instruction to a motor """
        serial_number = self._serial_numbers[name]
        self._dll.CC_Home(serial_number)

