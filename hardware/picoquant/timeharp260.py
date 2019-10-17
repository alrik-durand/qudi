# -*- coding: utf-8 -*-
"""
This file contains the Qudi hardware module for the TimeHarp260.

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

import ctypes
import numpy as np
import time
from qtpy import QtCore
import os

from core.module import Base
from core.configoption import ConfigOption
from core.util.modules import get_main_dir
from core.util.mutex import Mutex
from interface.slow_counter_interface import SlowCounterInterface
from interface.slow_counter_interface import SlowCounterConstraints
from interface.slow_counter_interface import CountingMode
from interface.fast_counter_interface import FastCounterInterface
from core.interface import interface_method

# =============================================================================
# Wrapper around the TH260Lib64.DLL. The current file is based on the header files
# 'thdefin.h', 'thlib.h' and 'errorcodesTH.h'. The 'thdefin.h' contains all the
# constants and 'thlib.h' contains all the functions exported within the dll
# file. 'errorcodesTH.h' contains the possible error messages of the device.
#
# The wrappered commands are based on the PHLib Version 3.0. For further
# information read the manual
#       'THLib - Programming Library for Custom Software Development'
# which can be downloaded from the PicoQuant homepage.
# =============================================================================


class TimeHarp260(Base, SlowCounterInterface, FastCounterInterface):
    """ Hardware class to control the TimeHarp 260 from PicoQuant.
    """



    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)


    def on_activate(self):
        """ Activate and establish the connection to Timeharp and initialize.
        """
        self.meas_run = False

    def on_deactivate(self):
        """ Deactivates and disconnects the device.
        """
        self.meas_run = False


    """
    # =========================================================================
    # Establish the connection and initialize the device or disconnect it.
    # =========================================================================
    """



    def start(self, acq_time):
        """ Start acquisition for 'acq_time' ms.

        @param int acq_time: acquisition time in ms. The value must be
                             be within the range [ACQTMIN,ACQTMAX].
        """
        if not(self.ACQTMIN <= acq_time <= self.ACQTMAX):
            self.log.error('TimeHarp start: No measurement could be started.\n'
                           'The acquisition time must be within the range [{0},{1}] '
                           'ms, but a value of {2} has been passed.'
                           ''.format(self.ACQTMIN, self.ACQTMAX, acq_time))
        else:
            self.check(self._dll.TH260_StartMeas(self._deviceID, int(acq_time)))




    # =========================================================================
    #  Higher Level function, which should be called directly from Logic
    # =========================================================================

    # =========================================================================
    #  Functions for the SlowCounter Interface
    # =========================================================================

    def set_up_clock(self, clock_frequency=None, clock_channel=None):
        """ Set here which channel you want to access of the TimeHarp.

        @param float clock_frequency: Sets the frequency of the clock. That frequency will not be taken. It is not
                                      needed, and argument will be omitted.
        @param string clock_channel: This is the physical channel of the clock. It is not needed, and
                                     argument will be omitted.

        @return int: error code (0:OK, -1:error)
        """
        return 0

    def set_up_counter(self, counter_channels=0, sources=None, clock_channel=None, counter_buffer=None):
        """ Set the card into slow counting mode

        @param string counter_channels : Set the actual channel which you want to
                                       read out. Default it is 0. It can
                                       also be 1.
        @param string sources : is not needed, arg will be omitted.
        @param string clock_channel: is not needed, arg will be omitted.

        @return int: error code (0:OK, -1:error)
        """
        return 0

    def get_counter_channels(self):
        """ Return one counter channel
        """
        return ['Ctr0']

    @interface_method
    def get_constraints(self):
        """ Useless function becaused I did not understand registers """
        pass

    @get_constraints.register('SlowCounterInterface')
    def get_constraints_slow(self):
        """ Get hardware limits

        @return SlowCounterConstraints: constraints class for slow counter

        """
        constraints = SlowCounterConstraints()
        constraints.max_detectors = 1
        constraints.min_count_frequency = 1e-3
        constraints.max_count_frequency = 10e9
        constraints.counting_mode = [CountingMode.CONTINUOUS]
        return constraints

    def get_counter(self, samples=None):
        """ Returns the current counts per second of the counter.

        @param int samples: if defined, number of samples to read in one go

        @return float: the photon counts per second (second and best method for count rate !)
        """
        return np.zeros((1, 1))

    def close_counter(self):
        """ Closes the counter and cleans up afterwards. Actually, you do not
        have to do anything with the TimeHarp. Therefore this command will do
        nothing and is only here for SlowCounterInterface compatibility.

        @return int: error code (0:OK, -1:error)
        """
        self.meas_run = False


    def close_clock(self):
        """ Closes the clock and cleans up afterwards.. Actually, you do not
        have to do anything with the TimeHarp. Therefore this command will do
        nothing and is only here for SlowCounterInterface compatibility.

        @return int: error code (0:OK, -1:error)
        """
        return 0

    """
    # =========================================================================
    #  Functions for the FastCounter Interface
    # =========================================================================
    """

    # FIXME: The interface connection to the fast counter must be established!

    def configure(self, fast_bin_width_s, record_length_s, number_of_gates=0):
        """ Configuration of the fast counter.

        @params int bin_width_ns: Length of a single time bin in the time trace histogram
                      in nanoseconds.
        @params int record_length_ns: Total length of the time trace/each single gate in
                          nanoseconds.
        @params int number_of_gates: Number of gates in the pulse sequence. Ignore for
                         ungated counter.
        @return int tuple (3) (bin width (sec), record length (sec), number of gates)
        """

        return fast_bin_width_s, record_length_s, number_of_gates

    @get_constraints.register('FastCounterInterface')
    def get_constraints_fast(self):
        """ Retrieve the hardware constrains of the Fast counting device
        for the fast_counter_interface.

        @return dict: dict with keys being the constraint names as string and
                      items are the definition for the constaints.
        """
        constraints = dict()
        # the unit of those entries are seconds per bin. In order to get the
        # current bin_width in seconds use the get_bin_width method.
        n_powers = 21
        bin_list = []
        for i in range(n_powers):
            bin_list.append(25*1e-12 * 2 ** i)

        constraints['hardware_binwidth_list'] = bin_list
        return constraints

    def get_status(self):
        """ Receives the current status of the Fast Counter and outputs it as
        return value.
        0 = not configured
        1 = idle
        2 = running
        3 = paused
        -1 = error state
        """
        return 1

    def pause_measure(self):
        """ Pauses the current measurement if the fast counter is in running state.
        """
        self.meas_run = False

    def continue_measure(self):
        """ Continues the current measurement if the fast counter is in pause state.
        """
        self.meas_run = True

    def is_gated(self):
        """ Boolean return value indicates if the fast counter is a gated counter
        (TRUE) or not (FALSE).
        """
        return False

    def get_binwidth(self):
        """ Returns the width of a single time bin in the time trace in seconds
        """
        return 1

    def get_data_trace(self, channel=0):
        """ Polls the current time_trace data from the fast counter and returns it
        as a numpy array (dtype = int64). The binning specified by calling
        configure() must be taken care of in this hardware class. A possible
        overflow of the histogram bins must be caught here and taken care of.
          - If the counter is NOT gated it will return a 1D-numpy-array with
            return array[time_bin_index].
          - If the counter is gated it will return a 2D-numpy-array with
            return array[gate_index, time_bin_index]
        """

        return np.zeros(10)

    def start_measure(self):
        """ Start the fast counter. """
        pass

    def stop_measure(self):
        """ Stop the fast counter. """
        pass
