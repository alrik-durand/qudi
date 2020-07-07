# -*- coding: utf-8 -*-

"""
This file contains the QuDi main GUI for pulsed measurements.

QuDi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

QuDi is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with QuDi. If not, see <http://www.gnu.org/licenses/>.

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

import numpy as np
import os
import pyqtgraph as pg

from qtpy import QtCore, QtWidgets, uic

from gui.guibase import GUIBase
from core.connector import Connector
from core.util import units

from gui.colordefs import QudiPalettePale as palette
from gui.fitsettings import FitSettingsDialog


class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_timetrace.ui')
        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)


class Main(GUIBase):
    """ This is the GUI module for timetrace analysis """

    logic = Connector(interface='TimetraceLogic')

    def on_activate(self):
        """ Initialize, connect and configure GUI."""
        self._mw = MainWindow()
        self._fsd = FitSettingsDialog(self.logic().fit_container)
        self._activate_ui()
        self._connect_inputs()
        self.show()

    def on_deactivate(self):
        """ Deactivate the GUI. """
        self._mw.close()

    def show(self):
        """ Make main window visible and put it above all other windows. """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()

    def _connect_inputs(self):
        """ Connect inputs to logic """
        self._mw.param_1_rebinnig_spinBox.editingFinished.connect(self.settings_changed)
        self._mw.param_2_start_DSpinBox.editingFinished.connect(self.settings_changed)
        self._mw.param_3_width_DSpinBox.editingFinished.connect(self.settings_changed)
        self._mw.param_4_origin_DSpinBox.editingFinished.connect(self.settings_changed)
        self.ta_start_line.sigPositionChangeFinished.connect(self.settings_changed)
        self.ta_end_line.sigPositionChangeFinished.connect(self.settings_changed)
        self.ta_origin_line.sigPositionChangeFinished.connect(self.settings_changed)
        self._mw.timetrace_fit_pushButton.clicked.connect(self.fit_clicked)

        self.logic().sigSettingsUpdated.connect(self.settings_updated)
        self.logic().sigDataUpdated.connect(self.update_window)


    def _activate_ui(self):
        """ Configure the plots """
        # Configure the full timetrace plot display:
        self.ta_start_line = pg.InfiniteLine(pos=0, pen={'color': palette.c3, 'width': 1}, movable=True)
        self.ta_end_line = pg.InfiniteLine(pos=0, pen={'color': palette.c3, 'width': 1}, movable=True)
        self.ta_origin_line = pg.InfiniteLine(pos=0, pen={'color': palette.c4, 'width': 1}, movable=True)
        self.ta_full_image = pg.PlotDataItem(np.arange(10), np.zeros(10), pen=palette.c1)
        self._mw.full_timetrace_PlotWidget.addItem(self.ta_full_image)
        self._mw.full_timetrace_PlotWidget.addItem(self.ta_start_line)
        self._mw.full_timetrace_PlotWidget.addItem(self.ta_end_line)
        self._mw.full_timetrace_PlotWidget.addItem(self.ta_origin_line)
        self._mw.full_timetrace_PlotWidget.setLabel(axis='bottom', text='time', units='s')
        self._mw.full_timetrace_PlotWidget.setLabel(axis='left', text='events', units='#')

        # Configure the window plot display:
        self.ta_window_image = pg.PlotDataItem(np.arange(10), np.zeros(10), pen=palette.c1)
        self._mw.window_PlotWidget.addItem(self.ta_window_image)
        self._mw.window_PlotWidget.setLabel(axis='bottom', text='time', units='s')
        self._mw.window_PlotWidget.setLabel(axis='left', text='Photoluminescence', units='c/s')

        self._mw.window_PlotWidget.showAxis('right')
        self._mw.window_PlotWidget.getAxis('right').setLabel('events', units='#', color=palette.c1.name())

        self._mw.window_PlotWidget_ViewBox = pg.ViewBox()
        self._mw.window_PlotWidget.scene().addItem(self._mw.window_PlotWidget_ViewBox)
        self._mw.window_PlotWidget.getAxis('right').linkToView(self._mw.window_PlotWidget_ViewBox)
        self._mw.window_PlotWidget_ViewBox.setXLink(self._mw.window_PlotWidget)

        def updateSecondAxis():
            sweeps = self.logic().master().elapsed_sweeps
            bin_width = self.logic().master().fast_counter_settings['bin_width']
            rebinning = self.logic().settings['rebinning']
            factor = (sweeps * (bin_width * rebinning))
            if sweeps == 0:
                return
            view_rect = self._mw.window_PlotWidget.viewRect()
            y_range = np.array([view_rect.bottom(), view_rect.top()]) * factor
            self._mw.window_PlotWidget_ViewBox.setRange(yRange=y_range, padding=0)

        updateSecondAxis()
        self._mw.window_PlotWidget_ViewBox.sigRangeChanged.connect(updateSecondAxis)

        self.ta_window_image_fit = pg.PlotDataItem(pen=palette.c3)

        self._mw.fit_method_comboBox.setFitFunctions(self._fsd.currentFits)

        # Initialize from logic values
        self.settings_updated(self.logic().settings)
        self.update_window()

    @QtCore.Slot(str, np.ndarray, object, str)
    def fit_data_updated(self, fit_method, fit_data, result, fit_type):
        """

        @param str fit_method:
        @param numpy.ndarray fit_data:
        @param object result:
        @param str fit_type: 'pulses' 'pulses_alt' or 'timetrace'
        @return:
        """
        # Get formatted result string
        if fit_method == 'No Fit':
            formatted_fitresult = 'No Fit'
        else:
            try:
                formatted_fitresult = units.create_formatted_output(result.result_str_dict)
            except:
                formatted_fitresult = 'This fit does not return formatted results'

        # block signals.
        # Clear text widget and show formatted result string.
        # Update plot and fit function selection ComboBox.
        # Unblock signals.

        self._mw.fit_method_comboBox.blockSignals(True)
        self._mw.fit_result_textBrowser.clear()
        self._mw.fit_result_textBrowser.setPlainText(formatted_fitresult)
        if fit_method:
            self._mw.fit_method_comboBox.setCurrentFit(fit_method)
        self.ta_window_image_fit.setData(x=fit_data[0], y=fit_data[1])
        if fit_method == 'No Fit' and self.ta_window_image_fit in self._mw.window_PlotWidget.items():
            self._mw.window_PlotWidget.removeItem(self.ta_window_image_fit)
        elif fit_method != 'No Fit' and self.ta_window_image_fit not in self._mw.window_PlotWidget.items():
            self._mw.window_PlotWidget.addItem(self.ta_window_image_fit)
        self._mw.fit_method_comboBox.blockSignals(False)

        return

    @QtCore.Slot()
    def settings_changed(self):
        """ Change logic model from GUI """
        settings_dict = dict()
        settings_dict['rebinning'] = self._mw.param_1_rebinnig_spinBox.value()
        # Check if the signal has been emitted by a dragged line in the laser plot
        if self.sender().__class__.__name__ == 'InfiniteLine':
            start = self.ta_start_line.value()
            end = self.ta_end_line.value()
            settings_dict['start'] = start if start <= end else end
            settings_dict['end'] = end if end >= start else start
            settings_dict['origin'] = self.ta_origin_line.value()
        else:
            settings_dict['start'] = self._mw.param_2_start_DSpinBox.value()
            settings_dict['end'] = settings_dict['start'] + self._mw.param_3_width_DSpinBox.value()
            settings_dict['origin'] = self._mw.param_4_origin_DSpinBox.value()

        self.logic().set_settings(settings_dict)
        return

    @QtCore.Slot(dict)
    def settings_updated(self, settings_dict):
        """ Change GUI from logic

        @param (dict) settings_dict: dictionary with parameters to update
        """
        # block signals
        self._mw.param_1_rebinnig_spinBox.blockSignals(True)
        self._mw.param_2_start_DSpinBox.blockSignals(True)
        self._mw.param_3_width_DSpinBox.blockSignals(True)
        self._mw.param_4_origin_DSpinBox.blockSignals(True)
        self.ta_start_line.blockSignals(True)
        self.ta_end_line.blockSignals(True)
        self.ta_origin_line.blockSignals(True)

        if 'start' in settings_dict:
            self._mw.param_2_start_DSpinBox.setValue(settings_dict['start'])
            self.ta_start_line.setValue(settings_dict['start'])
        if 'end' in settings_dict and 'start' in settings_dict:
            self._mw.param_3_width_DSpinBox.setValue(settings_dict['end']-settings_dict['start'])
            self.ta_end_line.setValue(settings_dict['end'])
        if 'origin' in settings_dict:
            self._mw.param_4_origin_DSpinBox.setValue(settings_dict['origin'])
            self.ta_origin_line.setValue(settings_dict['origin'])
        if 'rebinning' in settings_dict:
            index = self._mw.param_1_rebinnig_spinBox.setValue(settings_dict['rebinning'])

        # unblock signals
        self._mw.param_1_rebinnig_spinBox.blockSignals(False)
        self._mw.param_2_start_DSpinBox.blockSignals(False)
        self._mw.param_3_width_DSpinBox.blockSignals(False)
        self._mw.param_4_origin_DSpinBox.blockSignals(False)
        self.ta_start_line.blockSignals(False)
        self.ta_end_line.blockSignals(False)
        self.ta_origin_line.blockSignals(False)

        self.update_window()

    @QtCore.Slot()
    def update_window(self):
        """ Update the timetrace data from logic """
        bin_width = self.logic().master().fast_counter_settings['bin_width']
        y_data = self.logic().master().raw_data
        x_data = np.arange(y_data.size, dtype=float) * bin_width
        self.ta_full_image.setData(x=x_data, y=y_data)

        x_data, y_data = self.logic().get_data()
        if len(y_data) > 1:
            self.ta_window_image.setData(x=x_data, y=y_data)

    @QtCore.Slot()
    def fit_clicked(self):
        pass
