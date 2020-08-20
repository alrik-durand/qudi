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
import math
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


def find_nearest_index(array, value):
    """ Find the index of the closest value in an array. """
    idx = np.searchsorted(array, value, side="left")
    if idx > 0 and (idx == len(array) or math.fabs(value - array[idx-1]) < math.fabs(value - array[idx])):
        return idx-1
    else:
        return idx


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
        widget.slider_powers = self._compute_slider_powers(self.logic().power_max, self.logic().power_min)
        widget.slider.setMaximum(len(widget.slider_powers)-1)

        self.update_switch_logic_to_gui(self.logic, widget)
        self.logic().sigNewSwitchState.connect(lambda: self.update_switch_logic_to_gui(self.logic, widget))

        self.update_power_logic_to_gui(self.logic, widget)
        self.logic().sigNewPower.connect(lambda: self.update_power_logic_to_gui(self.logic, widget))

        widget.slider.sliderMoved.connect(lambda i: self.update_power_slider_gui_to_logic(self.logic, widget))
        widget.powerSpinBox.editingFinished.connect(lambda: self.update_power_gui_to_logic(self.logic, widget))
        widget.checkBox.stateChanged.connect(lambda: self.update_switch_gui_to_logic(self.logic, widget))

        self._mw.verticalLayout.addWidget(widget)
        self.widgets.append(widget)

    def update_switch_logic_to_gui(self, logic, widget):
        """"""
        switch_state = logic().get_switch_state()
        if switch_state is None:
            widget.checkBox.setEnabled(False)
        else:
            widget.checkBox.blockSignals(True)
            widget.checkBox.setChecked(switch_state)
            widget.checkBox.blockSignals(False)

    def update_switch_gui_to_logic(self, logic, widget):
        logic().set_switch_state(widget.checkBox.isChecked())

    def update_power_logic_to_gui(self, logic, widget):
        widget.powerSpinBox.blockSignals(True)
        widget.slider.blockSignals(True)
        widget.powerSpinBox.setValue(logic().get_power_setpoint())
        if not widget.slider.isSliderDown():
            widget.slider.setValue(find_nearest_index(widget.slider_powers, logic().get_power_setpoint()))
        widget.powerSpinBox.blockSignals(False)
        widget.slider.blockSignals(False)

    def update_power_slider_gui_to_logic(self, logic, widget):
        logic().set_power(widget.slider_powers[widget.slider.value()])

    def update_power_gui_to_logic(self, logic, widget):
        logic().set_power(widget.powerSpinBox.value())

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

