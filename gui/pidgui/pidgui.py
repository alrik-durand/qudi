# -*- coding: utf-8 -*-

"""
This file contains a gui for the pid controller logic.

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
import os
import pyqtgraph as pg

from core.module import Connector, ConfigOption
from gui.colordefs import QudiPalettePale as palette
from gui.guibase import GUIBase
from qtpy import QtCore
from qtpy import QtWidgets
from qtpy import uic


class MainWindow(QtWidgets.QMainWindow):
    """ Create the Main Window based on the *.ui file. """

    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_pid_control.ui')

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        self.show()


class PIDGui(GUIBase):
    """ This is the main class for graphically interacting with a process
    """
    _modclass = 'pidgui_2'
    _modtype = 'gui'

    ## declare connectors
    pidlogic = Connector(interface='PIDLogic')

    sigStart = QtCore.Signal()
    sigStop = QtCore.Signal()

    _fields = []
    _interval = ConfigOption('interval', 0)  # 0 = show all
    _last_index = 0
    _data = {}
    _link = None

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        """ Definition and initialisation of the GUI

        """
        self. logic = self.pidlogic()
        self._fields = self._logic.get_fields()
        for field in self._fields:
            self._data[field] = []
        self.get_data()

        self._init_window()
        self._init_axis()

              


        self._link = {
            'button': [
                ('start', self.start),
                ('stop', self.stop),
            ],
            'checkbox': [],
            'box': []
        }

        # checkbox
        if 'enabled' in self._fields:
            self._link['checkbox'].append(('enabled', 'enabled'))

        # number
        possible_fields = ('kp', 'kd', 'ki', 'setpoint')
        for field in possible_fields:
            if field in self._fields:
                self._link['box'].append(field)



        for item in self._link['button']:
            name, func = item
            self._mw.getattr('{}_Action'.format(name)).triggered.connect(func)

    def _init_window(self):
        """ Create the main window
        """
        self._mw = MainWindow()
        self._mw.centralwidget.hide()
        self._mw.setDockNestingEnabled(True)
        self._pw = self._mw.trace_PlotWidget

    def _init_axis(self):
        title = "Process value over time"
        left_axis = {'text': 'Process', 'units': ''}
        right_axis = None
        bottom_axis = {'text': 'Time', 'units': 's'}


    def _update_view_from_model(self):
        """ Update the view data from the logic data
        """

        for name in self._link['checkbox']:
            self._update_view('{}_Checkbox'.format(name), 'checkbox', self._data[name][-1])

        for name in self._link['input']:
            self._update_view('{}_Box'.format(name), 'box', self._data[name][-1])

    def _update_view(self, identifier, nature, value):
        """ Update a view field """
        view = self._mw.getattr(identifier)
        view.blockSignals(True)
        if nature == 'checkbox':
            view.setChecked(value)
        else:
            view.setValue(value)
        view.blockSignals(False)

    def start(self):
        """ Start to update the plotted data automatically
        """

    def on_deactivate(self):
        """ Deactivate the module properly.
        """
        self._mw.close()

    def get_data(self):
        """ Get new data from the logic

        @return bool: True if new data is present
        """
        updated = False
        for field in self._fields:
            new = self._logic.get_data(field, self._last_index)
            self._data[field] += new
            if new:
                updated = True
        return updated
