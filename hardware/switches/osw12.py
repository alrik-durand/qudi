# -*- coding: utf-8 -*-
"""
Control for a Thorlabs OWS12 MEMS Fiber-Optic Switch through the serial interface.

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

import visa
import time
from core.module import Base
from core.configoption import ConfigOption
from core.util.mutex import Mutex
from interface.switch_interface import SwitchInterface


class OSW12(Base, SwitchInterface):
    """ This class is implements communication with Thorlabs OSW12(22) fibered switch.

    Description of the hardware provided by Thorlabs:
        Thorlabs offers a line of bidirectional fiber optic switch kits that include a MEMS optical switch with an
        integrated control circuit that offers a USB 2.0 interface for easy integration into your optical system.
        Choose from 1x2 or 2x2 MEMS modules with any of the following operating wavelengths:
        480 - 650 nm, 600 - 800 nm, 750 - 950 nm, 800 - 1000 nm, 970 - 1170 nm, or 1280 - 1625 nm.
        These bidirectional switches have low insertion loss and excellent repeatability.

    Example config for copy-paste:

    fibered_switch:
        module.Class: 'switches.osw12.OSW12'
        interface: 'ASRL1::INSTR'
    """
    # name of the serial interface where the hardware is connected.
    # Use e.g. the Keysight IO connections expert to find the device.
    serial_interface = ConfigOption('interface', 'ASRL1::INSTR')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lock = Mutex()
        self._resource_manager = None
        self._instrument = None

    def on_activate(self):
        """ Prepare module, connect to hardware.
        """
        self._resource_manager = visa.ResourceManager()
        self._instrument = self._resource_manager.open_resource(
            self.serial_interface,
            baud_rate=115200,
            write_termination='\n',
            read_termination='\r\n',
            timeout=10,
            send_end=True
        )

    def on_deactivate(self):
        """ Disconnect from hardware on deactivation.
        """
        self._instrument.close()
        self._resource_manager.close()

    @property
    def name(self):
        """ Name of the hardware as string.

        @return str: The name of the hardware
        """
        return 'MEMS Fiber-Optic Switch'

    @property
    def available_states(self):
        """ Names of the states as a dict of tuples.

        The keys contain the names for each of the switches. The values are tuples of strings
        representing the ordered names of available states for each switch.

        @return dict: Available states per switch in the form {"switch": ("state1", "state2")}
        """
        return {'switch': ("1", "2")}

    def get_state(self, switch):
        """ Query state of single switch by name

        @param str switch: name of the switch to query the state for
        @return str: The current switch state
        """
        for attempt in range(3):
            try:
                response = self._instrument.query('S?').strip()
            except visa.VisaIOError:
                self.log.debug('Hardware query raised VisaIOError, trying again...')
            else:
                return response
        raise Exception('Hardware did not respond after 3 attempts. Visa error')

    def set_state(self, switch, state):
        """ Set state of single switch by name

        @param str switch: name of the switch to change
        @param str state: name of the state to set
        """
        self._instrument.write('S {}'.format(state))
        time.sleep(0.1)

        # FIXME: For some reason first returned value is not updated yet, let's clear it.
        _ = self.states
