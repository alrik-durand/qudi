"""

Hardware module to interface a Rohde & Schwarz power supply HMP2030

This file is adapted from the pi3diamond project distributed under GPL V3 licence.
Created by Helmut Fedder <helmut@fedder.net>. Adapted by someone else.

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

import visa

from core.module import Base
from core.configoption import ConfigOption
from interface.process_control_interface import ProcessControlInterface


class PowerSupply(Base, ProcessControlInterface):

    _address = ConfigOption('address', missing='error')

    _voltage_max_1 = ConfigOption('voltage_max_1', 32)
    _current_max_1 = ConfigOption('current_max_1', 5)
    _voltage_max_2 = ConfigOption('voltage_max_2', 32)
    _current_max_2 = ConfigOption('current_max_2', 5)
    _voltage_max_3 = ConfigOption('voltage_max_3', 32)
    _current_max_3 = ConfigOption('current_max_3', 5)

    _model = None
    _inst = None

    def on_activate(self):
        """ Startup the module """

        rm = visa.ResourceManager()
        try:
            self._inst = rm.open_resource(self._address)
        except visa.VisaIOError:
            self.log.error('Could not connect to hardware. Please check the wires and the address.')

        self._model = self._inst.query('*IDN?').split(',')[1]
        self.log.info('Connected to {}.'.format(self._model))

        self._set_over_voltage(self._voltage_max_1, 1)
        self._set_over_current(self._current_max_1, 1)
        self._set_over_voltage(self._voltage_max_2, 2)
        self._set_over_current(self._current_max_2, 2)
        self._set_over_voltage(self._voltage_max_3, 3)
        self._set_over_current(self._current_max_3, 3)
        self._set_channel(1)
        self._set_voltage(0)
        self._set_on()

    def on_deactivate(self):
        """ Stops the module """
        self._set_all_off()
        self._inst.close()

    def _set_channel(self, channel):
        """sets the channel 1, 2 or 3"""
        if channel in [1, 2, 3]:
            self._inst.write('INST OUPT {}'.format(channel))
        else:
            self.log.error('Wrong channel number. Chose 1, 2 or 3.')
    
    def _get_channel(self):
        """ query the selected channel"""
        channel = int(self._inst.query('INST:NSEL?'))
        return channel
    
    def _get_status_channel(self, channel):
        """ Gets the current status of the selected channel (CC or CV)"""
        state = int(self._inst.query('STAT:QUES:INST:ISUM{}:COND?'.format(channel)))
        status = 'CC' if state == 1 else 'CV'
        return status
    
    def _set_voltage(self, value, channel=None):
        """ Sets the voltage to the desired value"""
        if channel is not None:
            self._set_channel(channel)
        mini, maxi = self.get_control_limit(channel=channel)
        if mini <= value <= maxi:
            self._inst.write("VOLT {}".format(value))
        else:
            self.log.error('Voltage value {} out of range'.format(value))
    
    def _get_voltage(self, channel=None):
        """ Get the measured the voltage """
        if channel is not None:
            self._set_channel(channel)
        voltage = float(self._inst.query('MEAS:VOLT?'))
        return voltage
        
    def _set_current(self, value, channel=None):
        """ Sets the current to the desired value """

        mini, maxi = self._get_control_limit_current(channel=channel)
        if mini <= value <= maxi:
            self._inst.write("CURR {}".format(value))
        else:
            self.log.error('Current value {} out of range'.format(value))
    
    def _get_current(self, channel=None):
        """ Get the measured the current  """
        if channel is not None:
            self._set_channel(channel)
        current = float(self._inst.query('MEAS:CURR?'))
        return current
    
    def _set_on(self, channel=None):
        """ Turns the output from the chosen channel on """
        if channel is not None:
            self._set_channel(channel)
        self._inst.write('OUTP ON')

    def _set_off(self, channel=None):
        """ Turns the output from the chosen channel off """
        if channel is not None:
            self._set_channel(channel)
        self._inst.write('OUTP OFF')
            
    def _set_all_off(self):
        """ Stops the output of all channels """
        self._set_off(1)
        self._set_off(2)
        self._set_off(3)
    
    def _reset(self):
        """ Reset the whole system"""
        self._inst.write('*RST')  # resets the device
        self._inst.write('SYST:REM')  # sets the instrument to remote control
        
    def _beep(self):
        """ gives an acoustical signal from the device """
        self._inst.write('SYST:BEEP')
        
    def _error_list(self):
        """ Get all errors from the error register """
        error = str(self._inst.query('SYST:ERR?'))
        return error

    def _set_over_voltage(self, maxi, channel=None):
        """ Sets the over voltage protection for a selected channel"""
        if channel is not None:
            self._set_channel(channel)
        self._inst.write('VOLT:PROT {}'.format(maxi))

    def _set_over_current(self, maxi, channel=None):
        """ Sets the over current protection for a selected channel"""
        if channel is not None:
            self._set_channel(channel)
        self._inst.write('FUSE ON')
        self._inst.write('CURR {}'.format(maxi))

# Interface methods

    def set_control_value(self, value, channel=1):
        """ Set control value

            @param (float) value: control value
            @param (int) channel: channel to control
        """
        if channel is not None:
            self._set_channel(channel)
        mini, maxi = self.get_control_limit(channel)
        if mini <= value <= maxi:
            self._inst.write("VOLT {}".format(value))
        else:
            self.log.error('Voltage value {} out of range'.format(value))

    def get_control_value(self):
        """ Get current control value, here heating power

            @return float: current control value
        """
        return float(self._inst.query("VOLT?").split('\r')[0])

    def get_control_unit(self):
        """ Get unit of control value.

            @return tuple(str): short and text unit of control value
        """
        return 'V', 'Volt'

    def get_control_limit(self, channel=None):
        """ Get minimum and maximum of control value.

            @return tuple(float, float): minimum and maximum of control value
        """
        if channel is None:
            channel = self._get_channel()
        maxi = 0
        maxi = self._voltage_max_1 if channel == 1 else maxi
        maxi = self._voltage_max_2 if channel == 2 else maxi
        maxi = self._voltage_max_3 if channel == 3 else maxi
        return 0, maxi
