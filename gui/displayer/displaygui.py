# -*- coding: utf-8 -*-
"""
This file contains the Qudi console GUI module.

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

from core.configoption import ConfigOption
from core.connector import Connector
from core.util.units import ScaledFloat
from gui.guibase import GUIBase
from qtpy import QtWidgets
from qtpy.QtWidgets import QLabel
from qtpy import QtCore
from qtpy import uic

class DisplayMainWindow(QtWidgets.QMainWindow):
    """ Helper class for window loaded from UI file.
    """
    def __init__(self):
        """ Create the switch GUI window.
        """
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_displaygui.ui')

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        self.show()

class DisplayGui(GUIBase):
    """ A grephical interface to mofe switches by hand and change their calibration.

    displayer:
        module.Class: 'displayer.displaygui.DisplayGui'
        connect:
            displaylogic : 'displaylogic'
    """

    # declare connectors
    displaylogic = Connector(interface='DisplayLogic')
    _refreshing_time = ConfigOption('refreshing_time', 1000)

    def on_activate(self):
        """Create all UI objects and show the window.
        """
        self._displaylogic = self.displaylogic()
        self._mw = DisplayMainWindow()

        # For each switch that the logic has, add a widget to the GUI to show its state
        self._hw = []
        self._values = []
        i = 0
        for label, displayer in self._displaylogic.display.items():
            self._mw.layout.addWidget(QLabel('{} :'.format(label)), i, 0)
            self._hw.append(displayer)
            self._values.append(QLabel(str('{:.2r}{}'.format(ScaledFloat(self._hw[i].get_process_value()),
                                                         self._hw[i].get_process_unit()[0]))))
            self._mw.layout.addWidget(self._values[i], i, 1)
            i += 1

        self.updateValues = QtCore.QTimer()
        self.updateValues.setSingleShot(False)
        self.updateValues.timeout.connect(self.update_values)
        self.updateValues.start(self._refreshing_time)

        self.show()

    def show(self):
        """Make sure that the window is visible and at the top.
        """
        self._mw.show()

    def on_deactivate(self):
        """ Hide window and stop ipython console.
        """
        self.saveWindowPos(self._mw)
        self._mw.close()

    def update_values(self):

        for i in range(len(self._hw)):
            self._values[i].setText(str('{:.2r}{}'.format(ScaledFloat(self._hw[i].get_process_value()),
                                                         self._hw[i].get_process_unit()[0])))

