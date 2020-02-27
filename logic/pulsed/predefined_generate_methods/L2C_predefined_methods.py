# -*- coding: utf-8 -*-

"""
This file contains the Qudi Predefined Methods for sequence generator - L2C version

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
from logic.pulsed.pulse_objects import PulseBlock, PulseBlockEnsemble, PulseSequence
from logic.pulsed.pulse_objects import PredefinedGeneratorBase
from core.util.helpers import csv_2_list

"""
General Pulse Creation Procedure:
=================================
- Create at first each PulseBlockElement object
- add all PulseBlockElement object to a list and combine them to a
  PulseBlock object.
- Create all needed PulseBlock object with that idea, that means
  PulseBlockElement objects which are grouped to PulseBlock objects.
- Create from the PulseBlock objects a PulseBlockEnsemble object.
- If needed and if possible, combine the created PulseBlockEnsemble objects
  to the highest instance together in a PulseSequence object.
"""


class L2CPredefinedGenerator(PredefinedGeneratorBase):
    """

    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    ################################################################################################
    #                             Generation methods for waveforms                                 #
    ################################################################################################
    def generate_t1_l2c(self, name='T1', tau_start=1.0e-6, tau_step=1.0e-6, num_of_points=50):
        """

        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # get tau array for measurement ticks
        tau_array = tau_start + np.arange(num_of_points) * tau_step

        # create the elements
        end_delay_element = self._get_idle_element(length=self.wait_time, increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length, increment=0)
        delay_element = self._get_delay_gate_element()

        tau_element = self._get_idle_element(length=tau_start, increment=tau_step)
        t1_block = PulseBlock(name=name)
        t1_block.append(tau_element)
        t1_block.append(laser_element)

        delay_block = PulseBlock(name='delay')
        delay_block.append(delay_element)

        laser_on_block = PulseBlock(name='laser_on')
        laser_on_block.append(laser_element)

        end_delay = PulseBlock(name='end_delay')
        end_delay.append(end_delay_element)

        created_blocks.append(t1_block)
        created_blocks.append(delay_block)
        created_blocks.append(laser_on_block)
        created_blocks.append(end_delay)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
        self._add_trigger(created_blocks=created_blocks, block_ensemble=block_ensemble)
        block_ensemble.append((delay_block.name, 0))
        block_ensemble.append((laser_on_block.name, 0))
        block_ensemble.append((t1_block.name, num_of_points - 1))
        block_ensemble.append((delay_block.name, 0))
        block_ensemble.append((end_delay.name, 0))

        # add metadata to invoke settings later on
        number_of_lasers = 1 + num_of_points
        block_ensemble.measurement_information['alternating'] = False
        block_ensemble.measurement_information['laser_ignore_list'] = list([0])
        block_ensemble.measurement_information['controlled_variable'] = tau_array
        block_ensemble.measurement_information['units'] = ('s', '')
        block_ensemble.measurement_information['labels'] = ('Tau', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = number_of_lasers
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks) - self.wait_time
        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_t1_exponential_l2c(self, name='T1_exp', tau_start=1.0e-6, tau_end=100.0e-6, num_of_points=50):
        """

        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # get tau array for measurement ticks
        if tau_start == 0.0:
            tau_array = np.geomspace(1e-9, tau_end, num_of_points - 1)
            tau_array = np.insert(tau_array, 0, 0.0)
        else:
            tau_array = np.geomspace(tau_start, tau_end, num_of_points)

        # create the elements
        end_delay_element = self._get_idle_element(length=self.wait_time, increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length, increment=0)
        delay_element = self._get_delay_gate_element()

        t1_block = PulseBlock(name=name)
        for tau in tau_array:
            tau_element = self._get_idle_element(length=tau, increment=0.0)
            t1_block.append(tau_element)
            t1_block.append(laser_element)

        delay_block = PulseBlock(name='delay')
        delay_block.append(delay_element)

        laser_on_block = PulseBlock(name='laser_on')
        laser_on_block.append(laser_element)

        end_delay = PulseBlock(name='end_delay')
        end_delay.append(end_delay_element)

        created_blocks.append(t1_block)
        created_blocks.append(delay_block)
        created_blocks.append(laser_on_block)
        created_blocks.append(end_delay)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
        self._add_trigger(created_blocks=created_blocks, block_ensemble=block_ensemble)
        block_ensemble.append((delay_block.name, 0))
        block_ensemble.append((laser_on_block.name, 0))
        block_ensemble.append((t1_block.name, num_of_points - 1))
        block_ensemble.append((delay_block.name, 0))
        block_ensemble.append((end_delay.name, 0))

        # add metadata to invoke settings later on
        number_of_lasers = 1 + num_of_points
        block_ensemble.measurement_information['alternating'] = False
        block_ensemble.measurement_information['laser_ignore_list'] = list([0])
        block_ensemble.measurement_information['controlled_variable'] = tau_array
        block_ensemble.measurement_information['units'] = ('s', '')
        block_ensemble.measurement_information['labels'] = ('Tau', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = number_of_lasers
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks) - self.wait_time
        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

