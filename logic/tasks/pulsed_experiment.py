# -*- coding: utf-8 -*-
"""
Pulsed experiment task

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
    """ This task is used to acquire a pulsed experiment in a interruptable context

    it needs :
        - pulsed_measurement_logic
    """

    _was_running = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def startTask(self):

        if self.ref['pulsed_measurement_logic'].module_state() != 'idle':
            self._was_running = True
            self.ref['pulsed_measurement_logic'].stop_pulsed_measurement()
        while self.ref['pulsed_measurement_logic'].module_state() != 'idle':
            time.sleep(0.1)

        self.ref['pulsed_measurement_logic'].start_pulsed_measurement()

    def runTaskStep(self):
        """ Wait for refocus to finish. """
        time.sleep(0.1)
        return self.ref['optimizer'].isstate('locked')

    def pauseTask(self):
        """ pausing a refocus is forbidden """
        pass

    def resumeTask(self):
        """ pausing a refocus is forbidden """
        pass

    def cleanupTask(self):
        """ End of task, let's stop save the stuff

        """
        self.ref['pulsed_measurement_logic'].stop_pulsed_measurement()
        self.ref['pulsed_measurement_logic'].save_measurement_data(tag=self.name)

        if self._was_running:
            self.ref['pulsed_measurement_logic'].start_pulsed_measurement()

    def checkExtraStartPrerequisites(self):
        """ Check whether anything we need is locked. """
        if 'min_time' in self.config and self.config['min_time'] > 0:
            return True
        else:
            self.log.error('Parameter min_time not set or invalid, please set a valid minimum time')
        return

    def checkExtraPausePrerequisites(self):
        """ pausing a refocus is forbidden """
        return True

