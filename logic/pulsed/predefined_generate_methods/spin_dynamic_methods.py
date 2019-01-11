import numpy as np

from logic.pulsed.pulse_objects import PulseBlock, PulseBlockEnsemble
from logic.pulsed.pulse_objects import PredefinedGeneratorBase


class Generator(PredefinedGeneratorBase):
    """

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def generate_robledo(self, name='robledo'):
        if self.wait_time < self.laser_delay + self.rabi_period / 2:
            print('Wait time is too small for this pi pulse and laser delay')

        block = PulseBlock(name='robledo')
        block.append(self._get_sync_element())
        block.append(self._get_idle_element(length=self.laser_delay, increment=0))
        block.append(self._get_laser_element(length=self.laser_length, increment=0))
        block.append(
            self._get_idle_element(length=self.wait_time - self.laser_delay - self.rabi_period / 2, increment=0))
        block.append(self._get_mw_element(length=self.rabi_period / 2, increment=0))
        block.append(self._get_idle_element(length=self.laser_delay, increment=0))
        block.append(self._get_laser_element(length=self.laser_length, increment=0))
        block.append(self._get_idle_element(length=self.wait_time - block[0].init_length_s - self.laser_delay,
                                            increment=0))

        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)

        block_ensemble.append((block.name, 0))

        block_ensemble.measurement_information['alternating'] = False
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = np.array([0, 1])
        block_ensemble.measurement_information['units'] = ('', '')
        block_ensemble.measurement_information['labels'] = ('Pulse', 'Integrated PL')
        block_ensemble.measurement_information['number_of_lasers'] = 2
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=[block])

        return [block], [block_ensemble], []
