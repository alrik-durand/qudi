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

import requests

from core.module import Base
from core.configoption import ConfigOption
from interface.switch_interface import SwitchInterface


class SpdtSwitch(Base, SwitchInterface):
    """ This class is implements communication with Minicricuit RC-xSPDT-Axx hardware

    This hardware controls one or multiple switch via SMA cables. It can connect either port 1 or port 2 to a COM port.
    This type of hardware can automatize the change of cabling configuration for SMA, BNC, etc. cables.

    It has been tested with :
        - RC-4SPDT-A26

    This module use the web api running on the hardware. Interfacing with dll via USB is supported by hardware but not
    implemented in this module (yet).

    Example config for copy-paste:

    spdt_switch:
        module.Class: 'switches.minicircuit_RC_SPDT.SpdtSwitch'
        http_address: 'http://192.168.1.10/' # 'http://ADDRESS:PORT/PWD;'
        number_of_switch: 4
    """

    _http_address = ConfigOption('http_address', missing='error')
    _number_of_switch = ConfigOption('number_of_switch', missing='error')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self._model = None

    def on_activate(self):
        """ Module activation method """
        try:
            self._model = self._get('MN?', split=True)
            self.log.info('Connected to {}'.format(self._model))
        except requests.exceptions.RequestException:
            self.log.error('Can not connect to hardware. Check cables and config address.')

    def on_deactivate(self):
        """ Disconnect from hardware on deactivation. """
        pass

    def _get(self, command, split=False):
        """ Send a command via the web api and return the result

        @param (str) command: The command to send to hardware
        @param (bool) split: Wheter to return only the part after the "=" in the response or full text.

        @return (str): The result of the web request as text
        """
        url = '{}{} '.format(self._http_address, command)  # the space at the end prevent request from removing "?"
        response = requests.get(url, timeout=1).text
        if split:
            response = response.split('=')[1]
        return response

    def _get_all_states(self):
        """ Use SWPORT? command to get the state of all ports """
        binary_state = int(self._get('SWPORT?'))
        states = [bool(binary_state >> i & 1) for i in range(self._number_of_switch)]
        return states

    def _set_state(self, switchNumber, value):
        """ Set the value (True/False) for a given index """
        self._get('SET{}={}'.format(chr(65+switchNumber), int(value)))

    # Start of SwitchInterface
    def getNumberOfSwitches(self):
        """ Gives the number of switches connected to this hardware.

          @return int: number of swiches on this hardware
        """
        return int(self._number_of_switch)

    def getSwitchState(self, switchNumber=0):
        """ Get the state of the switch.

          @param (int) switchNumber: index of switch

          @return bool: True if connected to 1, False is connected to 2
        """
        return self._get_all_states()[switchNumber]

    def getCalibration(self, switchNumber, state):
        """ Get calibration parameter for switch.

        Function not used by this module
        """
        return 0

    def setCalibration(self, switchNumber, state, value):
        """ Set calibration parameter for switch.

        Function not used by this module
        """
        return True

    def switchOn(self, switchNumber):
        """ Set the state to on (channel 1)

          @param int switchNumber: number of switch to be switched

          @return bool: True if succeeds, False otherwise
        """
        try:
            self._set_state(switchNumber, True)
            return True
        except:
            return False

    def switchOff(self, switchNumber):
        """ Set the state to off (channel 2)

          @param int switchNumber: number of switch to be switched

          @return bool: True if suceeds, False otherwise
        """
        try:
            self._set_state(switchNumber, False)
            return True
        except:
            return False

    def getSwitchTime(self, switchNumber):
        """ Give switching time for switch.

          @param int switchNumber: number of switch

          @return float: time needed for switch state change
        """
        return 25e-3  # typ. 25 ms
