# -*- coding: utf-8 -*-

"""
This file contains the Qudi Interfuse between a scanner/confocal logic and a slow counter.

---

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
from interface.slow_counter_interface import SlowCounterInterface
from interface.slow_counter_interface import SlowCounterConstraints
from interface.slow_counter_interface import CountingMode

from core.module import Connector, ConfigOption
from logic.generic_logic import GenericLogic
from interface.simple_laser_interface import SimpleLaserInterface, ControlMode, ShutterState, LaserState


class LaserAomInterfuse(GenericLogic, SlowCounterInterface):
    """ This interfuse use the last line read from the scanner to emulate a slow counter.
    """

    _modclass = 'ScannerSlowCounterInterfuse'
    _modtype = 'interfuse'

    # connector to the scanner
    scanner = Connector(interface='ConfocalLogic')


    def on_activate(self):
        """ Activate module.
        """
        self._scanner = self.scanner()


    def on_deactivate(self):
        """ Deactivate module.
        """
        pass

    def get_constraints(self):
        """ Return a constraints class for the slow counter."""
        # TODO: logic does not have a getter nor change event for now
        constraints = SlowCounterConstraints()
        constraints.min_count_frequency = self._scanner._clock_frequency
        constraints.max_count_frequency = self._scanner._clock_frequency
        constraints.counting_mode = [CountingMode.CONTINUOUS]
        return constraints

    def set_up_clock(self):
        """  Configure the clock, no need here. Return zero for ok """
        return 0

    def set_up_counter(self):
        """  Configure the counter, no need here. Return zero for ok """
        return 0

    def _load_buffer(self):
        """ Read the last line from the scanner and add it to buffer """



    def get_counter(self, samples=None):
        """ Returns the current counts per second of the counter.

        @param int samples: if defined, number of samples to read in one go (for oversampling)

        """

        count_data = np.empty([samples], dtype=np.uint32)

        get_scanner_count_channels()

        count_data = np.array(
            [self._simulate_counts(samples) + i * self.mean_signal
                for i, ch in enumerate(self.get_counter_channels())]
            )

        time.sleep(1 / self._clock_frequency * samples)
        return count_data

    def get_counter_channels(self):
        """ Returns the list of counter channel names.
        @return tuple(str): channel names
        """
        return self._scanner.get_scanner_count_channels()

    def close_counter(self):
        """ Closes the counter and cleans up afterwards, no need here. Return zero for ok """
        return 0

    def close_clock(self,power=0):
        return 0
