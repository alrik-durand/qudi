# -*- coding: utf-8 -*-
"""
Aggregate multiple switches.

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

from core.configoption import ConfigOption
from logic.generic_logic import GenericLogic
from collections import OrderedDict
from qtpy import QtCore


class ProcessMonitorLogic(GenericLogic):
    """ Logic module to monitor one or multiple process value hardware.

    process_monitor_logic:
        module.Class: 'monitor_logic.ProcessMonitorLogic'
        connect:
            process_1: 'processdummy_1'
            process_2: 'processdummy_2'
        names: ['Temperature', 'Humidity']
    """

    _refreshing_time = ConfigOption('refreshing_time', 1)

    def __init__(self, config, **kwargs):
        """ Create logic object

          @param dict config: configuration in a dict
          @param dict kwargs: additional parameters as a dict
        """
        super().__init__(config=config, **kwargs)

        # dynamic number of 'in' connectors depending on config
        if 'connect' in config:
            for connector in config['connect']:
                self.connectors[connector] = OrderedDict()
                self.connectors[connector]['class'] = 'ProcessInterface'
                self.connectors[connector]['object'] = None

    def on_activate(self):
        """ Prepare logic module for work.
        """
        self.updateValues = QtCore.QTimer()
        self.updateValues.setSingleShot(False)
        self.updateValues.timeout.connect(self.update_values)
        self.updateValues.start(self._refreshing_time)

    def on_deactivate(self):
        """ Deactivate modeule.
        """


