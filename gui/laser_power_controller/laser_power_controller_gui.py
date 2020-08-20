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


class LaserWidget(QtWidgets.QWidget):
    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'widget.ui')
        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)


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
        self.widgets = []

    def on_activate(self):
        """ Definition and initialisation of the GUI """

        self._mw = MainWindow()

        widget = LaserWidget()
        widget.color_label.setStyleSheet("QLabel{{background-color : {}}}".format(self.logic().color))
        widget.label.setText(self.logic().name)
        switch_state = self.logic().get_switch_state()
        if switch_state is None:
            widget.checkBox.setEnabled(False)
        else:
            widget.checkBox.setChecked(switch_state)
        widget.powerSpinBox.setValue(self.logic().get_power_setpoint())

        slider_powers = self._compute_slider_powers(self.logic().power_max, self.logic().power_min)
        widget.slider.setMaximum(len(slider_powers)-1)

        def update_from_slider(index):
            widget.powerSpinBox.setValue(slider_powers[index])

        widget.slider.sliderMoved.connect(update_from_slider)

        self._mw.verticalLayout.addWidget(widget)
        self.widgets.append(widget)


        #

    def on_deactivate(self):
        """ Deactivate the module properly. """
        self._mw.close()

    def show(self):
        """ Make window visible and put it above all other windows. """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()

    def _compute_slider_powers(self, maxi=None, mini=None, decimal=1, decade=4):
        maxi = maxi if maxi is not None else self.logic().power_max
        mini = mini if mini is not None else self.logic().power_min

        current = maxi
        finals = [current]
        for i in range(decade):
            if current < mini:
                break
            power = np.floor(np.log10(current))
            number = int(current / 10 ** power * 10 ** decimal) / 10 ** decimal
            while number >= 1:
                finals.append(number * 10 ** power)
                number -= 1 / 10 ** decimal
            finals.append(number * 10 ** power)
            current = finals[-1] - 1 / 10 ** decimal * 10 ** power

        finals = np.array(finals)
        finals = finals[finals > mini]
        finals = np.append(finals, mini)
        finals = np.flip(finals)
        return finals

