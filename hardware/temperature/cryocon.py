# -*- coding: utf-8 -*-

"""
This hardware module implement the pid interfaces to interact with a Cryo-Con

This module have been developed with model 22C
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

import time
import visa
from core.module import Base
from core.configoption import ConfigOption
import numpy as np

from interface.process_interface import ProcessInterface
from interface.pid_controller_interface import PIDControllerInterface


    """ Main class for the Cryo-Con hardware

    Cryocon is a temperature controller with a screen and buttons to regulate one or multiple channels. This module adds
    control via Qudi with the PIDControllerInterface.

    Tested with models :
     - 22B

    Example config:

    cryocon:
        module.Class: 'temperature.cryocon.Cryocon'
        ip_address: '192.168.1.222'
        main_channel: 'B'

    """

    _modtype = 'cryocon'
    _modclass = 'hardware'

    _ip_address = ConfigOption('ip_address')
    _ip_port = ConfigOption('port', 5000)
    _timeout = ConfigOption('timeout', 5)
    _main_channel = ConfigOption('main_channel', 'A')

    _inst = None

    _stop_wait = True

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """
        self.open_resource()

    def open_resource(self):
        """ Open a new visa connection """
        rm = visa.ResourceManager()
        try:
            address = 'TCPIP::{}::{}::SOCKET'.format(self._ip_address, self._ip_port)
            self._inst = rm.open_resource(address, timeout=self._timeout*1000,
                                          write_termination='\n', read_termination='\n')
        except visa.VisaIOError:
            self.log.error('Could not connect to hardware. Please check the wires and the address.')
            raise visa.VisaIOError

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.
        """
        try:
            self._inst.close()
        except visa.VisaIOError:
            self.log.warning('Crycon connexion has not been closed properly.')

    def get_temperature(self, channel=None):
        """ Cryocon function to get one temperature """
        channel = channel if channel is not None else self._main_channel
        try:
            text = 'INPUT? {}'.format(channel)
            temperature = float(self._query(text))
        except:
            temperature = np.NaN
        return temperature

    def _query(self, text):
        """ Helper function to send query and deal with errors """
        try:
            response = self._inst.query(text)
        except visa.VisaIOError:
            self.log.warning('Cryocon connexion lost, automatic attempt to reconnect...')
            self.open_resource()
            self._inst.query(text)
        return response

    def set_temperature(self, temperature, channel=None, turn_on=False):
        """ Function to set the temperature setpoint """
        channel = channel if channel is not None else self._main_channel
        loop = 1 if channel == 'A' else 2
        text = 'loop {}:setp {}'.format(loop, temperature)
        try:
            self._query(text)
        except:
            self.log.error('Cryocon temperature could not be set because of a connexion error.')
            return
        if turn_on:
            self.control()

    def get_setpoint_temperature(self, channel=None):
        """ Return the main channel set point temperature"""
        channel = channel if channel is not None else self._main_channel
        loop = 1 if channel == 'A' else 2
        try:
            text = 'loop {}:setp?'.format(loop)
            setpoint = float(self._query(text)[:-2])
        except:
            setpoint = np.NaN
        return setpoint

    def stop(self):
        """  Function to stop the heating of the Cryocon """""
        self._query('stop')

    def control(self):
        """ Function to turn the heating on """
        self._query('control')

    # ProcessInterface methods

    def get_process_value(self):
        """ Get measured value of the temperature """
        return self.get_temperature()

    def get_process_unit(self):
        """ Return the unit of measured temperature """
        return 'K', 'Kelvin'

    # ProcessControlInterface methods

# PID controller interface

    def get_control_value(self):
        """ Get the value of the controlled process variable """
        return self.get_setpoint_temperature()

    def get_control_unit(self):
        """ Return the unit that the value is set in as a tuple of ('abreviation', 'full unit name') """
        return 'W', 'Watt'

    def get_control_limit(self):
        """ Return limits within which the controlled value can be set as a tuple of (low limit, high limit)
        """
        return 0, 350

    def get_extra(self):
        pass

    # Script helper methods

    def wait_for_temperature(self, temperature, delta=0.1, timeout=60*60):
        """ Set the temperature and wait until the setpoint temperature is reached

        @param temperature: The new setpoint
        @param delta: The error margin between the measured value and the setpoint to stop
        @param timeout: The maximum time to wait
        @return (bool): True if successful, False if timeout

        Warning, this pausing function can be usefull but can also cause Qudi to not respond if executed from the
        manager.
        """
        self.set_temperature(temperature, turn_on=True)
        start_time = time.time()
        while time.time() - start_time < timeout and not self._stop_wait:
            current_temperature = self.get_temperature()
            if temperature - delta < current_temperature < temperature + delta:
                        return True
            time.sleep(1)
        return False
