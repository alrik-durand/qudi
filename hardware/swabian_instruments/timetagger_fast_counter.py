# -*- coding: utf-8 -*-
"""
A hardware module for communicating with the fast counter FPGA.

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

from interface.fast_counter_interface import FastCounterInterface
import numpy as np
import TimeTagger as tt
from core.module import Base
from core.configoption import ConfigOption
import os


class TimeTaggerFastCounter(Base, FastCounterInterface):
    """ Hardware class to controls a Time Tagger from Swabian Instruments.

    Example config for copy-paste:

    fastcounter_timetagger:
        module.Class: 'swabian_instruments.timetagger_fast_counter.TimeTaggerFastCounter'
        timetagger_channel_apd_0: 1
        timetagger_channel_apd_1: 2
        timetagger_channel_detect: 3
        timetagger_channel_sequence: 4
        timetagger_sum_channels: True
        gated: True
    """

    _channel_apd_0 = ConfigOption('timetagger_channel_apd_0', missing='error')
    _channel_apd_1 = ConfigOption('timetagger_channel_apd_1', missing='error')
    _channel_detect = ConfigOption('timetagger_channel_detect', missing='error')
    _channel_sequence = ConfigOption('timetagger_channel_sequence', missing='error')
    _sum_channels = ConfigOption('timetagger_sum_channels', True, missing='warn')
    _gated = ConfigOption('gated', True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._tagger = None
        self._bin_width = None
        self._channel_apd = None
        self.status_variable = None
        self.pulsed = None
        self._channel_combined = None

    def on_activate(self):
        """ Connect and configure the access to the FPGA.
        """
        self._tagger = tt.createTimeTagger()
        self._tagger.reset()
        self._bin_width = 1e-9

        if self._sum_channels:
            # _channel_combined needs to be kept alive from the garbage collector
            self._channel_combined = tt.Combiner(self._tagger, channels=[self._channel_apd_0, self._channel_apd_1])
            self._channel_apd = self._channel_combined.getChannel()
        else:
            self._channel_apd = self._channel_apd_0
        self.status_variable = 0

    def get_constraints(self):
        """ Retrieve the hardware constrains from the Fast counting device.

        @return dict: dict with keys being the constraint names as string and
                      items are the definition for the constaints.
        """

        constraints = dict()
        minimal_binwidth = 1e-12
        powers_of_10 = 10 ** np.array(np.arange(10)) * minimal_binwidth
        binwidth_list = np.sort(np.concatenate([powers_of_10, 2 * powers_of_10, 5 * powers_of_10]))
        constraints['hardware_binwidth_list'] = list(binwidth_list)
        return constraints

    def on_deactivate(self):
        """ Deactivate the hardware. """
        if self.module_state() == 'locked':
            self.pulsed.stop()
        self.pulsed.clear()
        self.pulsed = None

    def configure(self, bin_width_s, record_length_s, number_of_gates=0):

        """ Configuration of the fast counter.

        @param float bin_width_s: Length of a single time bin in the time trace
                                  histogram in seconds.
        @param float record_length_s: Total length of the timetrace/each single
                                      gate in seconds.
        @param int number_of_gates: optional, number of gates in the pulse
                                    sequence. Ignore for not gated counter.

        @return tuple(binwidth_s, gate_length_s, number_of_gates):
                    binwidth_s: float the actual set binwidth in seconds
                    gate_length_s: the actual set gate length in seconds
                    number_of_gates: the number of gated, which are accepted
        """
        self._bin_width = bin_width_s
        record_length_in_bin = 1 + int(record_length_s / bin_width_s)
        number_of_gates_used = number_of_gates if self._gated else 1

        print(int(np.round(self._bin_width * 1e12)), int(record_length_in_bin), number_of_gates_used)

        self.pulsed = tt.TimeDifferences(
            tagger=self._tagger,
            click_channel=self._channel_apd,
            start_channel=self._channel_detect,
            next_channel=self._channel_detect,
            sync_channel=tt.CHANNEL_UNUSED,
            binwidth=int(np.round(self._bin_width * 1e12)),  # hardware talks in picoseconds
            n_bins=int(record_length_in_bin),
            n_histograms=number_of_gates_used)

        self.pulsed.stop()
        self.status_variable = 1

        return bin_width_s, record_length_s, number_of_gates

    def start_measure(self):
        """ Start the fast counter. """
        self.module_state.lock()
        self.pulsed.clear()
        self.pulsed.start()
        self.status_variable = 2
        return 0

    def stop_measure(self):
        """ Stop the fast counter. """
        if self.module_state() == 'locked':
            self.pulsed.stop()
            self.module_state.unlock()
        self.status_variable = 1
        return 0

    def pause_measure(self):
        """ Pauses the current measurement.

        Fast counter must be initially in the run state to make it pause.
        """
        if self.module_state() == 'locked':
            self.pulsed.stop()
            self.status_variable = 3
        return 0

    def continue_measure(self):
        """ Continues the current measurement.

        If fast counter is in pause state, then fast counter will be continued.
        """
        if self.module_state() == 'locked':
            self.pulsed.start()
            self.status_variable = 2
        return 0

    def is_gated(self):
        """ Check the gated counting possibility.

        Boolean return value indicates if the fast counter is a gated counter
        (TRUE) or not (FALSE).
        """
        return bool(self._gated)

    def get_data_trace(self):
        """ Polls the current timetrace data from the fast counter.

        @return numpy.array: 2 dimensional array of dtype = int64. This counter
                             is gated the the return array has the following
                             shape:
                                returnarray[gate_index, timebin_index]

        The binning, specified by calling configure() in forehand, must be taken
        care of in this hardware class. A possible overflow of the histogram
        bins must be caught here and taken care of.
        """
        info_dict = {'elapsed_sweeps': self.pulsed.getCounts(),
                     'elapsed_time': None}
        data = self.pulsed.getData()
        if not self._gated:
            data = data[0]
        return np.array(data, dtype='int64'), info_dict

    def get_status(self):
        """ Receives the current status of the Fast Counter and outputs it as
            return value.

        0 = unconfigured
        1 = idle
        2 = running
        3 = paused
        -1 = error state
        """
        return self.status_variable

    def get_binwidth(self):
        """ Returns the width of a single timebin in the timetrace in seconds. """
        return self._bin_width

