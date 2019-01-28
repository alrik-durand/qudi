# -*- coding: utf-8 -*-
"""
Confocal-refocus task.

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
    """ This task does a confocal focus optimisation.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._poi_manager = self.ref['poi_manager']
        self._laser = self.ref['laser']
        self._was_power = None
        self.check_config_key('power', 300e-6)
        self._power = self.config['power']

    def startTask(self):
        """ Get position from scanning device and do the refocus """
        self._was_power = self._laser.get_power_setpoint()
        self._laser.set_power(self._power)
        self._poi_manager.optimise_poi(poikey=self._poi_manager._current_poi_key)

    def runTaskStep(self):
        """ Wait for refocus to finish. """
        time.sleep(0.1)
        return self._poi_manager._optimizer_logic.module_state() != 'idle'

    def pauseTask(self):
        """ pausing a refocus is forbidden """
        pass

    def resumeTask(self):
        """ pausing a refocus is forbidden """
        pass

    def cleanupTask(self):
        """ nothing to clean up """
        self._laser.set_power(self._was_power)

    def checkExtraStartPrerequisites(self):
        """ Check whether anything we need is locked. """
        return self._poi_manager._optimizer_logic.module_state() == 'idle'

    def checkExtraPausePrerequisites(self):
        """ pausing a refocus is forbidden """
        return False

