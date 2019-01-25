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
from sklearn.model_selection import ParameterGrid
import random
import numpy as np

class Task(InterruptableTask):
    """ This task is used to acquire a pulsed experiment in a interruptable context

    it needs :
        - 'pulsed_master' : pulsed_measurement_logic
        - 'laser' : laser to control power
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._master = self.ref['pulsed_master']
        self._generator = self.ref['pulsed_master'].sequencegeneratorlogic()
        self._measurement = self.ref['pulsed_master'].pulsedmeasurementlogic()
        self._laser = self.ref['laser']

    def get_generation_parameter(self, param):
        """ Helper method to get a generation parameter """
        return self._generator._generation_parameters[param]

    def check_config_key(self, key, default, possible_values=None):
        """ Helper method to check is a key is defined in config and set a default value if not """
        if key not in self.config or self.config[key] is None or \
            (possible_values is not None and self.config[key] not in possible_values):
            self.config[key] = default

    def startTask(self):
        """ Method called when the task is tarted

        1. Check the parameters in config
        2. Create the parameter grid

        """

        self._was_running =  self._measurement.module_state() == 'locked'
        self._was_loaded = self._generator.loaded_asset
        self._was_power = self._laser.get_power_setpoint()

        self.check_config_key('wait_time', [self.get_generation_parameter('wait_time')])
        self.check_config_key('laser_length', [self.get_generation_parameter('laser_length')])
        self.check_config_key('laser_delay', [self.get_generation_parameter('laser_delay')])
        self.check_config_key('power', [self._laser.get_power_setpoint()])
        parameters = ['wait_time', 'laser_length', 'laser_delay', 'power']
        param_grid = dict([(key, self.config[key]) for key in parameters])
        param_grid['elapsed_time'] = [0]
        param_grid['elapsed_photon_count'] = [0]

        self._list = list(ParameterGrid(param_grid))

        duration_modes = ['same_time', 'same_photon_count', 'same_sweeps']
        self.check_config_key('duration_mode', 'same_time', possible_values=duration_modes)
        self.check_config_key('switch_time', 5*60)

        self.check_config_key('max_time', None)

        self._start_time = time.time()

        self._time_since_last_swtich = 0
        self._current_row = 0

        self._random_key = random.randint(0, 1e9) # key to prevent collision in pulsed saved data

        self.activate_row()


    def runTaskStep(self):
        """ The main loop of the task

        Check if it's time to switch row or stop task. Else continue
        """
        if self._time_since_last_swtich > self.config['switch_time']:
            self.go_to_next_row()

        self._time_since_last_swtich += 0.1
        time.sleep(0.1)
        if self.config['max_time'] is not None and time.time() - self._start_time > self.config['max_time']:
            return False
        else:
            return True  # continue

    def get_key(self, row_number):
        """ Helper function to get unique key for each row """
        return '{:d}_{:d}'.format(self._random_key, row_number)

    def get_current_row(self):
        """ Helper function to get current row object """
        return self._list[self._current_row]

    def stop_current_row(self):
        """ Method to stop the current row acquisition """
        self._measurement.stop_pulsed_measurement(self.get_key(self._current_row))
        self.get_current_row()['elapsed_time'] = self.get_current_row()['elapsed_time'] + self._time_since_last_swtich
        self.get_current_row()['elapsed_sweeps'] = self._measurement.elapsed_sweeps
        self.get_current_row()['elapsed_photon_count'] = self._measurement.raw_data.sum()
        self._time_since_last_swtich = 0

    def go_to_next_row(self):
        """ Method  to stop current row and start next """
        self.stop_current_row()

        properties = {'same_time': 'elapsed_time',
                      'same_photon_count': 'elapsed_photon_count',
                      'same_sweeps': 'elapsed_sweeps'}
        array = np.array([row[properties[self.config['duration_mode']]] for row in self._list])
        next = np.argmin(array)
        self._current_row = next
        self.activate_row()

    def activate_row(self):
        """ Method to create pulsed sequence for current row and measurement settings """
        self.wait_for_idle()
        self.make_sequence('robledo', **self.get_current_row())
        self._measurement._invoke_settings_from_sequence = True
        self._laser.set_power(self.get_current_row()['power'])
        self._measurement.start_pulsed_measurement(self.get_key(self._current_row))

    def make_sequence(self, name, wait_time, laser_delay, laser_length, **_):
        """ Build, sample and load the current row ensemble """
        self._master.set_generation_parameters(wait_time=wait_time)
        self._master.set_generation_parameters(laser_delay=laser_delay)
        self._master.set_generation_parameters(laser_length=laser_length)
        self._master.generate_predefined_sequence(generator_method_name=name, kwarg_dict={})
        self._master.sample_ensemble(name)
        self._master.load_ensemble(name)

    def pauseTask(self):
        """ Pause the acquisition in a way that can be resumed even if user change stuff in pulsed module"""
        self.stop_current_row()

    def resumeTask(self):
        """ Resume paused measurement """
        self.activate_row()

    def cleanupTask(self):
        """ End of task, let's stop save the stuff.

        We have to start/stop/save every one for now.

        """
        if self._measurement.module_state != 'idle':
            self.stop_current_row()

        for i, row in enumerate(self._list):
            self.wait_for_idle()
            self._current_row = i
            self.activate_row()
            self.stop_current_row()
            self._measurement.save_measurement_data(tag=self.name)

        if self._was_loaded[1] == 'PulseBlockEnsemble':
            self._generator.load_ensemble(self._was_loaded[0])
        self._laser.set_power(self._was_power)
        if self._was_running:
            self._measurement.start_pulsed_measurement()

    def wait_for_idle(self, timeout=10):
        """ Function to wait for the measurement to be idle

        @param timeout: the maximum time to wait before causing an error (in seconds)
        """
        counter = 0
        while self._measurement.module_state() != 'idle' and counter < timeout:
            time.sleep(0.1)
            counter += 0.1


    # def checkExtraStartPrerequisites(self):
    #     """ Check whether anything we need is locked. """
    #     return True
    #
    #
    # def checkExtraPausePrerequisites(self):
    #     """ pausing a refocus is forbidden """
    #     return True
    #
