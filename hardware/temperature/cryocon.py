# -*- coding: utf-8 -*-

"""
This hardware module implement the pid interfaces to interact with a Cryo-Con

This module have been developed with model 22C
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

import socket
from core.module import Base, ConfigOption

# from interface.process_interface import ProcessInterface


class SocketInstrument:
    """ General class for a socket instrument, this should go elsewhere ! """
    def __init__(self, host, port):
        """ Initialise the connection with the instrument """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        self.sock = sock

    def write(self, cmd):
        """Sends a command over the socket"""
        cmd_string = cmd + '\n'
        sent = self.sock.sendall(cmd_string.encode())
        if sent != None:
            raise RuntimeError('Transmission failed')

    def query(self, cmd):
        """sends the question and receives the answer"""
        self.write(cmd)
        answer = self.sock.recv(2048)  # 2000
        return answer[:-2]

    def close(self):
        self.sock.close()


class Cryocon(Base):
    """
    Main class for the Cryo-Con hardware
    """

    _modtype = 'cryocon'
    _modclass = 'hardware'

    _ip_address = ConfigOption('ip_address')
    _ip_port = ConfigOption('port', 5000)

    _socket = None


    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """
        self._socket = SocketInstrument(self._ip_address, self._ip_port)

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.
        """
        if self._socket:
            self._socket.close()

    def get_process_value(self):
        """ Get measured value of the temperature """
        temperature_a = float(self._socket.query('INPUT? A'))
        temperature_b = float(self._socket.query('INPUT? B'))
        return temperature_a, temperature_b

    def get_process_unit(self):
        """ Return the unit of measured temperature """
        return 'K', 'Kelvin'

    def stop(self):
            self._socket.write('stop')

    def control(self):
        self._socket.write('control')

    def set_control_value(self, loop=1, temperature=4):
        self._socket.write('loop {}:setp {}'.format(loop, temperature))




