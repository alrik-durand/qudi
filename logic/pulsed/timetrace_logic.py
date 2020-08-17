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

from qtpy import QtCore
from collections import OrderedDict
import numpy as np
import copy
import time
import datetime
import matplotlib.pyplot as plt

from core.connector import Connector
from core.statusvariable import StatusVar
from core.util import units
from logic.generic_logic import GenericLogic

from core.util.curve_methods import get_window, rebin_xy


class TimetraceLogic(GenericLogic):
    """ This is the logic module for the analysis of the raw timetrace """
    master = Connector(interface='PulsedMasterLogic')
    fitlogic = Connector(interface='FitLogic')
    savelogic = Connector(interface='SaveLogic')

    time_series = Connector(interface='TimeSeriesReaderLogic', optional=True)

    settings = StatusVar(default={'start': 0, 'end': 0, 'origin': 0, 'rebinning': 0})

    sigSettingsUpdated = QtCore.Signal(dict)
    sigDataUpdated = QtCore.Signal()
    sigFitUpdated = QtCore.Signal()

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        # for fit:
        self.fit_container = None  # Fit container
        self.fit_result = None
        self.signal_fit_data = np.empty((2, 0), dtype=float)  # The x,y data of the fit result

    def on_activate(self):
        """ Initialisation performed during activation of the module. """
        self.fit_container = self.fitlogic().make_fit_container('timetrace', '1d')
        self.fit_container.set_units(['s', 'c/s'])
        if 'fits' in self._statusVariables and isinstance(self._statusVariables.get('fits'), dict):
            self.fit_container.load_from_dict(self._statusVariables['fits'])

        self.master().sigMeasurementDataUpdated.connect(self.sigDataUpdated)

    def on_deactivate(self):
        """ Deactivation """
        if len(self.fit_container.fit_list) > 0:
            self._statusVariables['fits'] = self.fit_container.save_to_dict()

    def get_data(self):
        """ Compute the analysed timetrace out of the raw timetrace """

        binwidth = self.master().fast_counter_settings['bin_width']
        y_data = self.master().raw_data
        x_data = np.arange(y_data.size, dtype=float) * binwidth

        start = self.settings['start']
        stop = self.settings['end']
        origin = self.settings['origin']
        x_data, y_data = get_window(x_data, y_data, start, stop)
        factor = self.master().elapsed_sweeps * (binwidth * self.settings['rebinning'])
        if factor == 0:
            data = (np.zeros([0, 1], dtype='float'), np.zeros([0, 0], dtype='int64'))
        else:
            x_data, y_data = rebin_xy(x_data, y_data, self.settings['rebinning'], do_average=False)
            data = (x_data - origin, y_data / factor)
        return data

    @QtCore.Slot(dict)
    def set_settings(self, settings_dict=None, **kwargs):
        """ Apply new timetrace analysis settings.

        Either accept a settings dictionary as positional argument or keyword arguments.
        If both are present both are being used by updating the settings_dict with kwargs.
        The keyword arguments take precedence over the items in settings_dict if there are
        conflicting names.
        """
        # Determine complete settings dictionary
        if not isinstance(settings_dict, dict):
            settings_dict = kwargs
        else:
            settings_dict.update(kwargs)

        for key in settings_dict:
            if key in ['start', 'end', 'origin', 'rebinning']:
                self.settings[key] = settings_dict[key]
        self.sigSettingsUpdated.emit(self.settings)

    @QtCore.Slot(str)
    def do_fit(self, fit_method):
        """ Performs the chosen fit on the measured data.

        @param (str) fit_method: name of the fit method to use

        @return (2D numpy.ndarray, result object): the resulting fit data and the fit result object
        """
        self.fit_container.set_current_fit(fit_method)

        data = self.get_data()
        x_fit, y_fit, result = self.fit_container.do_fit(data[0], data[1])
        fit_data = np.array([x_fit, y_fit])

        self.signal_fit_data = fit_data
        self.fit_result = copy.deepcopy(self.fit_container.current_fit_result)
        self.sigFitUpdated.emit()
        return fit_data, self.fit_container.current_fit_result

    def save(self, tag=None):
        """ Save the current data """
        # Save just the raw file with usual logic
        self.master().save_measurement_data(tag=None, save_laser_pulses=False, save_pulsed_measurement=False,
                                            save_figure=False)
        filepath = self.savelogic().get_path_for_module('Timetrace')
        timestamp = datetime.datetime.now()
        filelabel = tag

        data = OrderedDict()
        data_x, data_y = self.get_data()
        data['x'] = data_x
        data['y'] = data_y

        parameters = OrderedDict()
        parameters['bin_width'] = self.master().fast_counter_settings['bin_width']
        parameters['bin_width_rebinned'] = self.master().fast_counter_settings['bin_width'] * self.settings['rebinning']
        parameters['start'] = self.settings['start']
        parameters['end'] = self.settings['end']
        parameters['origin'] = self.settings['origin']
        parameters['rebinning'] = self.settings['rebinning']
        parameters['sweeps'] = self.master().elapsed_sweeps
        parameters['elapsed_time'] = self.master().elapsed_time

        # Prepare the figure to save as a "data thumbnail"
        plt.style.use(self.savelogic().mpl_qd_style)
        fig, ax = plt.subplots()
        ax.set_ylabel('Signal [c/s]')

        # scale the x_axis for plotting
        max_val = np.max(np.abs(data_x))
        scaled_float = units.ScaledFloat(max_val)
        x_axis_scaled = data_x / scaled_float.scale_val
        ax.set_xlabel('Time [{}s]'.format(scaled_float.scale))

        ax.plot(x_axis_scaled, data_y, '.-', label='Data')

        if self.signal_fit_data.size != 0:
            x_axis_fit_scaled = self.signal_fit_data[0] / scaled_float.scale_val
            ax.plot(x_axis_fit_scaled, self.signal_fit_data[1], marker='None', label='Fit')

            # add then the fit result to the plot:

            # Parameters for the text plot:
            # The position of the text annotation is controlled with the
            # relative offset in x direction and the relative length factor
            # rel_len_fac of the longest entry in one column
            rel_offset = 0.02
            rel_len_fac = 0.011
            entries_per_col = 24

            # create the formatted fit text:
            if hasattr(self.fit_result, 'result_str_dict'):
                result_str = units.create_formatted_output(self.fit_result.result_str_dict)
            else:
                result_str = ''
            # do reverse processing to get each entry in a list
            entry_list = result_str.split('\n')
            # slice the entry_list in entries_per_col
            chunks = [entry_list[x:x + entries_per_col] for x in range(0, len(entry_list), entries_per_col)]

            is_first_column = True  # first entry should contain header or \n

            for column in chunks:

                max_length = max(column, key=len)  # get the longest entry
                column_text = ''

                for entry in column:
                    column_text += entry + '\n'

                column_text = column_text[:-1]  # remove the last new line

                heading = ''
                if is_first_column:
                    heading = 'Fit results:'

                column_text = heading + '\n' + column_text

                ax.text(1.00 + rel_offset, 0.99, column_text,
                         verticalalignment='top',
                         horizontalalignment='left',
                         transform=ax.transAxes,
                         fontsize=12)

                # the rel_offset in position of the text is a linear function
                # which depends on the longest entry in the column
                rel_offset += rel_len_fac * len(max_length)

                is_first_column = False

        self.savelogic().save_data(data, timestamp=timestamp, parameters=parameters, filepath=filepath,
                                   filelabel=filelabel, plotfig=fig)
