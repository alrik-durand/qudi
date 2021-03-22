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
import visa

from core.module import Base
from core.configoption import ConfigOption


class NewportAgUc8(Base):
    """ This hardware interface with a Newport Agilis Controller AG-UC8

    Example config for copy-paste:

    agilis_motor:
        module.Class: 'motor.newport_ag_uc8.NewportAgUc8'
        interface: 'COM6'

    """
    interface = ConfigOption('interface', 'COM3', missing='error')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._rm = None
        self._inst = None
        self._active_channel = None
        self._delay = 0.01

    def on_activate(self):
        """ Module activation method """
        self._rm = visa.ResourceManager()
        try:
            self._inst = self._rm.open_resource(self.interface, baud_rate=921600, write_termination='\r\n',
                                                read_termination='\r\n',
                                                timeout=2, send_end=True)
            version = self._inst.query('VE', delay=self._delay)
            self.log.debug('Connected to : {}'.format(version))
        except visa.VisaIOError:
            self.log.error('Could not connect to device')
        self._active_channel = int(self._inst.query('CC?', delay=self._delay)[-1])

    def on_deactivate(self):
        """ Disconnect from hardware on deactivation. """
        self._inst.close()
        self._rm.close()

    def set_channel(self, channel):
        """ Set the current active channel """
        if channel not in [1, 2, 3, 4]:
            return self.log.error('Channel {} is not correct.'.format(channel))
        if channel != self._active_channel:
            self._inst.write('CC{}'.format(channel))
            self._active_channel = channel

    def move(self, channel, axis, number_of_steps):
        """ Move a given number of steps on a given channel and axis """
        self.set_channel(channel)
        if axis not in [1,2]:
            return self.log.error('Axis {} is not correct.'.format(axis))
        if number_of_steps < -2147483648 or number_of_steps > 2147483647:
            return self.log.error('Number of steps {} out of range.'.format(number_of_steps))

        self._inst.write('{} PR {}'.format(axis, number_of_steps))

    def stop(self, axis):
        if axis not in [1, 2]:
            return self.log.error('Axis {} is not correct.'.format(axis))
        self._inst.write("{} ST".format(axis))

    def get_status(self, axis):
        status = int(self._inst.query('{} TS'.format(axis), delay=self._delay)[-1])
        status_dict = { 0: "Ready (not moving).",
                        1: "Stepping (currently executing a `move_relative` command).",
                        2: "Jogging (currently executing a `jog` command with command"
                           "parameter different than 0).",
                        3: "Moving to limit (currently executing `measure_current_position`, "
                           "`move_to_limit`, or `move_absolute` command).",}
        return status, status_dict

