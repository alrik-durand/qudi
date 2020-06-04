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
import time
import visa

from core.module import Base
from core.configoption import ConfigOption
from interface.process_control_interface import ProcessControlInterface


class K33600A(Base, ProcessControlInterface):
    """ Hardware module for waveform generator Keysight 33600A.
    Example config :
        waveform_gene:
            module.Class: 'awg.waveform_generator_keysight_33600A'
            address: 'ASRL9::INSTR'
    """

    _address = ConfigOption('address', missing='error')
    _voltage_max = ConfigOption('voltage_max', 4)

    
    def on_activate(self):

       rm = visa.ResourceManager()
       try:
            self._inst = rm.open_resource(self._address)
       except visa.VisaIOError:
            self.log.error('Could not connect to hardware. Please check the wires and the address.')


    def on_deactivate(self):
        """ Stops the module """
        self._inst.close()

        
    def _write(self, cmd):
        """ Function to write command to hardware"""
        self._inst.write(cmd)
        time.sleep(.01)

    def _query(self, cmd):
        """ Function to query hardware"""
        return self._inst.query(cmd)

    def set_control_value(self, value):
        """ Set control value, here heating power.
            @param flaot value: control value
        """
        self._write("SOURce1:VOLTage {}".format(value))
        return value

    def get_control_value(self):
        """ Get current control value, here heating power
            @return float: current control value
        """
        return 0

    def get_control_unit(self):
        """ Get unit of control value.
            @return tuple(str): short and text unit of control value
        """
        return 'V', 'Volt'

    def get_control_limit(self):
        """ Get minimum and maximum of control value.
            @return tuple(float, float): minimum and maximum of control value
        """
        return 0, 4
