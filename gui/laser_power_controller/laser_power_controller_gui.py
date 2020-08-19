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
import os
import pyqtgraph as pg

from core.connector import Connector
from gui.guibase import GUIBase
from interface.simple_laser_interface import ControlMode, ShutterState, LaserState
from qtpy import QtCore
from qtpy import QtWidgets
from qtpy import uic


class MainWindow(QtWidgets.QMainWindow):
    """ Create the Main Window based on the *.ui file. """

    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'main.ui')

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        self.show()


class Main(GUIBase):
    """ GUI module to control one or multiple laser power

     This module can be connected to one or multiple logic modules

     power_controller_gui:
        module.Class: 'laser_power_controller.laser_power_controller_gui.Main'
        connect:
            logic: 'green_power_controller'
     """

    logic = Connector(interface='LaserPowerController')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self._mw = None

    def on_activate(self):
        """ Definition and initialisation of the GUI """

        self._mw = MainWindow()

        self._mw.label.setStyleSheet("QLabel{{background-color : {}}}".format(self.logic().color))

    def on_deactivate(self):
        """ Deactivate the module properly. """
        self._mw.close()

    def show(self):
        """ Make window visible and put it above all other windows. """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()

