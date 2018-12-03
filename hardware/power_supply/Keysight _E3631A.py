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
import visa

from core.module import Base, ConfigOption




class E3631A(Base):
    """ Hardware module for Keysight E3631A.

    Example config :
    powermeter:
        module.Class: 'powermeter.PM100D.PM100D'
        address: 'USB0::0x1313::0x8078::P0013645::INSTR'

    This module needs the ThorlabsPM100 package from PyPi, this package is not included in the environment
    To add install it, type :
    pip install ThorlabsPM100
    in the Anaconda prompt after aving activated qudi environment
    """
    _modclass = 'powermeter'
    _modtype = 'hardware'

    _address = ConfigOption('address', missing='error')
    _timeout = ConfigOption('timeout', 1)
    _power_meter = None

    def on_activate(self):
        """ Startup the module """

        rm = visa.ResourceManager()
        try:
            self._inst = rm.open_resource(self._address, timeout=self._timeout)
        except:
            self.log.error('Could not connect to hardware. Please check the wires and the address.')

        self.model = self._inst.query("*IDN?")
        self._inst.write("INST P6V")

        #self._inst.write("OUTP ON")

    def on_deactivate(self):
        """ Stops the module """
        self._inst.write("OUTP OFF")
        self._inst.close()

