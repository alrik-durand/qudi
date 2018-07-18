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

    _active_fields = []
    _logged_fields = []
    _left_axis_text = ConfigOption('left_axis_text', 'Process value')
    _left_axis_unit = ConfigOption('left_axis_unit', '')
    _legend = ConfigOption('legend', [''])

    _logic = None
    # GUI
    _link = None

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        """ Definition and initialisation of the GUI

        """
        self._logic = self.pidlogic()

        # Get data info
        fields = self._logic.get_fields()
        self._active_fields = fields['active']
        self._logged_fields = fields['logged']

        # Prepare UI
        self._init_window()
        self._init_axis()
        self._logic.sigUpdate.connect(self._update_view_from_model)

        # We construct a dictionary that link Qt object to their logic getter/setter
        self._link = {
            'button': [
                ('start', self.start),
                ('stop', self.stop),
            ],
            'checkbox': [],
            'box': [
                ('timestep', self._logic.timestep)
            ]
        }

        # Let's add some features to the dic if they are used
        # Sometimes the getter/stter is not a signle function, so we use anonymous function (lambda)

        if 'enabled' in self._active_fields:
            self._link['checkbox'].append(('enabled', lambda value=None: self._logic.parameter('enabled', value)))

        possible_fields = ('kp', 'kd', 'ki', 'setpoint')
        for field in possible_fields:
            if field in self._active_fields:
                self._link['box'].append((field, lambda value=None: self.logic.parameter(field, value)))

        # Now let's connect things

        for item in self._link['button']:
            name, func = item
            self._mw.getattr('{}_Action'.format(name)).triggered.connect(func)

        for item in self._link['box']:
            name, func = item
            qt_object = self._mw.getattr('{}_Box'.format(name))
            qt_object.editingFinished.connect(lambda: func(qt_object.value()))

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

        self._pw = self._mw.process_PlotWidget

        self._pw.setLabel('left', self._left_axis_text, unit=self._left_axis_unit)
        self._pw.setLabel('bottom', 'Time', units='s')

        self._curves = []

        for curve in self._legend:
            self._curves.append(
                pg.PlotDataItem(pen=pg.mkPen(palette.c1), symbol=None, name=curve))

    def _update_view_from_model(self):
        """ Update the view data from the logic data
        """

        for item in self._link['checkbox']:
            name, func = item
            self._update_view('{}_Checkbox'.format(name), 'checkbox', func())






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

    def update_data(self):
        """ Function called when the logic emits an update signal """
        new = self.get_data()
        if new:
            self._update_view_from_model()

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
                self._last_index =
        return updated
