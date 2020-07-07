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

    def on_activate(self):
        """ Initialisation performed during activation of the module. """
        self.fit_container = self.fitlogic().make_fit_container('timetrace', '1d')
        self.master().sigMeasurementDataUpdated.connect(self.sigDataUpdated)

    def on_deactivate(self):
        """ Deactivation """

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
