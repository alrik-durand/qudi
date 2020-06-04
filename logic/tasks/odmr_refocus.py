# -*- coding: utf-8 -*-
"""
Optimizer refocus task with laser on.

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

from logic.generic_task import InterruptableTask
import time


class Task(InterruptableTask):
    """ This task pauses pulsed measurement, run laser_on, does a poi refocus then goes back to the pulsed acquisition.

    It uses poi manager refocus duration as input.

    Example:
        tasks:
            odmr_refocus:
                module: 'odmr_refocus'
                needsmodules:
                    poi_manager: 'poimanagerlogic'
                    optimizer_logic: 'optimizerlogic'
                    odmr_logic: 'odmrlogic'
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._poi_manager = self.ref['poi_manager']
        self._optimizer_logic = self.ref['optimizer_logic']
        self._odmr = self.ref['odmr_logic']
        self._was_running = None

    def startTask(self):
        """ Stop odmr, do refocus """

        self._was_running = self._odmr.module_state() == 'locked'
        if self._was_running:
            self._odmr.stop_odmr_scan()

        self.wait_for_idle()
        self._poi_manager.optimise_poi_position()

    def runTaskStep(self):
        """ Wait for refocus to finish. """
        time.sleep(1)
        return self._optimizer_logic.module_state() != 'idle'

    def pauseTask(self):
        """ pausing a refocus is forbidden """
        pass

    def resumeTask(self):
        """ pausing a refocus is forbidden """
        pass

    def cleanupTask(self):
        """ go back to odmr acquisition """
        if self._was_running:
            time.sleep(0.5)
            self._odmr.continue_odmr_scan()

    def checkExtraStartPrerequisites(self):
        """ Check whether anything we need is locked. """
        return self._optimizer_logic.module_state() == 'idle'

    def checkExtraPausePrerequisites(self):
        """ pausing a refocus is forbidden """
        return False

    def wait_for_idle(self, timeout=20):
        """ Function to wait for the measurement to be idle

        @param timeout: the maximum time to wait before causing an error (in seconds)
        """
        counter = 0
        while self._odmr.module_state() != 'idle' and counter < timeout:
            time.sleep(0.1)
            counter += 0.1
        if counter >= timeout:
            self.log.warning('Measurement is too long to stop, continuing anyway')
