# -*- coding: utf-8 -*-

"""
This file contains the Qudi GUI for polarization measurement.

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
from core.util import units
from core.gui import connect_trigger_to_function
from core.gui import connect_view_to_model
from gui.colordefs import QudiPalettePale as palette
from gui.guibase import GUIBase
from qtpy import QtCore
from qtpy import QtWidgets
from qtpy import uic
from gui.fitsettings import FitSettingsDialog


class MainWindow(QtWidgets.QMainWindow):
    """ Create the Main Window based on the *.ui file. """

    def __init__(self, **kwargs):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'polarization_gui.ui')

        # Load it
        super().__init__(**kwargs)
        uic.loadUi(ui_file, self)
        self.show()


class Gui(GUIBase):
    """ Main class for this module - GUI of polarization measurement
    """

    logic = Connector(interface='PolarizationLogic')

    _mw = None
    main_curve = None
    _fsd = None

    def on_activate(self):

        self._mw = MainWindow()
        self._mw.centralwidget.hide()
        self._mw.setDockNestingEnabled(True)

        self.init_plot()

        self.update_module_state()

        # Connecting user interactions
        connect_trigger_to_function(self, self._mw.run_Action, 'triggered', self.logic().run)
        connect_trigger_to_function(self, self._mw.stop_Action, 'triggered', self.logic().abort, QtCore.Qt.DirectConnection)
        connect_trigger_to_function(self, self._mw.actionSave, 'triggered', self.logic().save)

        connect_view_to_model(self, self._mw.resolution_SpinBox, self.logic(), 'resolution')
        connect_view_to_model(self, self._mw.time_per_point_SpinBox, self.logic(), 'time_per_point')
        connect_view_to_model(self, self._mw.background_time_doubleSpinBox, self.logic(), 'background_time')
        connect_view_to_model(self, self._mw.background_doubleSpinBox, self.logic(), 'background_value')
        connect_view_to_model(self, self._mw.background_time_doubleSpinBox, self.logic(), 'background_time')

        connect_trigger_to_function(self, self._mw.measure_background_pushButton, 'clicked', self.logic().take_background)

        # Handling signals from the logic
        connect_trigger_to_function(self, self.logic().sigDataUpdated, None,  self.update_data)
        connect_trigger_to_function(self, self.logic().sigFitUpdated, None, self.update_fit)
        connect_trigger_to_function(self, self.logic().sigStateChanged, None, self.update_module_state)

        # Fit settings dialog
        self._fsd = FitSettingsDialog(self.logic().fc)
        self._fsd.sigFitsUpdated.connect(self._mw.fit_param_fit_func_ComboBox.setFitFunctions)
        self._fsd.applySettings()
        self._mw.actionFit_settings.triggered.connect(self._fsd.show)
        self._mw.do_fit_PushButton.clicked.connect(self.do_fit)

    def show(self):
        """Make window visible and put it above all other windows.
        """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()
        return

    def on_deactivate(self):
        """ Deactivate the module """
        # disconnect signals automatically :)
        self._mw.close()

    def init_plot(self):
        """ Draw the polar plot at activation """
        self._mw.plotWidget.setLabel('left', 'Fluorescence', units='counts/s')
        self._mw.plotWidget.setLabel('bottom', 'Fluorescence', units='counts/s')
        self._mw.plotWidget.setAspectLocked()
        self._mw.plotWidget.addLine(x=0, pen=0.2)
        self._mw.plotWidget.addLine(y=0, pen=0.2)
        for power in np.arange(2, 6):
            r = 10 ** power
            circle = pg.QtGui.QGraphicsEllipseItem(-r, -r, r * 2, r * 2)
            circle.setPen(pg.mkPen(0.2))
            # self._mw.plotWidget.addItem(circle)
            r = 5 * r
            circle = pg.QtGui.QGraphicsEllipseItem(-r, -r, r * 2, r * 2)
            circle.setPen(pg.mkPen(0.1))
            # self._mw.plotWidget.addItem(circle)
        #
        # self._pw.setLabel('bottom', 'Angle', units='')

        self.main_curve = pg.PlotDataItem(pen=pg.mkPen(palette.c1), symbol='o',
                                          symbolPen=palette.c1,
                                          symbolBrush=palette.c1,
                                          symbolSize=7)
        self._mw.plotWidget.addItem(self.main_curve)

        self.fit_curve = pg.PlotDataItem(pen=pg.mkPen(palette.c3))
        self._mw.plotWidget.addItem(self.fit_curve)

    def update_data(self):
        """ The function that grabs the data and sends it to the plot. """
        theta, r = self.logic().get_data(unit='radian')
        x = r * np.cos(theta)
        y = r * np.sin(theta)
        if len(y) > 0:
            self.main_curve.setData(x=x, y=y)

    def update_fit(self):
        """ Function that grabs the fit result and plot it """
        if self.logic().fit_curve is None or self.logic().fit_result is None:
            self.fit_curve.setData(x=[], y=[])
            return

        if hasattr(self.logic().fit_result, 'result_str_dict'):
            formatted_results = units.create_formatted_output(self.logic().fit_result.result_str_dict)
            self._mw.fit_param_results_TextBrowser.setPlainText(formatted_results)

        theta, r = self.logic().get_fit_data(unit='radian')
        x = r * np.cos(theta)
        y = r * np.sin(theta)
        if len(y) > 0:
            self.fit_curve.setData(x=x, y=y)

    def update_module_state(self):
        """ Enable and disable buttons and editing when logic module state changes"""
        active = self.logic().module_state() == 'locked'
        self._mw.run_Action.setEnabled(not active)
        self._mw.stop_Action.setEnabled(active and not self.logic().stop_requested)
        self._mw.actionSave.setEnabled(not active)
        self._mw.resolution_SpinBox.setEnabled(not active)
        self._mw.time_per_point_SpinBox.setEnabled(not active)
        self._mw.measure_background_pushButton.setEnabled(not active)

    def do_fit(self):
        """ Command logic to do the fit with the chosen fit function. """
        fit_function = self._mw.fit_param_fit_func_ComboBox.getCurrentFit()[0]
        self.logic().do_fit(fit_function)
