# -*- coding: utf-8 -*-
"""
This file contains the Qudi hardware dummy for camera rich interface.

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

from core.module import Base
from core.configoption import ConfigOption
from interface.camera_rich_interface import CameraRichInterface


class CameraRichDummy(Base, CameraRichInterface):
    """ Dummy hardware class to emulate a rich camera

    Example config for copy-paste:

    camera_rich_dummy:
        module.Class: 'dummy.camera_rich_dummy.CameraRichDummy'

    """
    _width = ConfigOption('width', 1024)
    _height = ConfigOption('height', 256)
    _exposure = 1
    _temperature = 20
    _readout_rate = 1e6

    def on_activate(self):
        """ Initialisation performed during activation of the module. """
        pass

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module. """
        pass

    def get_camera_constraints(self):
        """ Return the constrains of the physical hardware."""
        constraints = dict()
        constraints['readout_rates'] = [1e3, 1e6]

        return constraints

    def get_name(self):
        """ Retrieve an identifier of the camera that the GUI can print

        @return string: name for the camera
        """
        return 'Dummy fancy camera 3000'

    def get_size(self):
        """ Retrieve size of the image in pixel

        @return tuple: Size (width, height)
        """
        return self._width, self._height

    def start_acquisition(self):
        """ Start a single acquisition

        @return bool: Success ?
        """
        self.run()
        self.stop()
        return True

    def stop_acquisition(self):
        """ Stop/abort acquisition

        @return bool: Success ?
        """
        self.stop()
        return True

    def set_exposure(self, exposure):
        """ Set the exposure time in seconds

        @param float time: desired new exposure time

        @return float: setted new exposure time
        """
        self._exposure = exposure
        return self._exposure

    def set_readout_rate(self, readout_rate):
        """ Set the readout rate of the camera """
        if readout_rate in self.get_camera_constraints()['readout_rates']:
            self._readout_rate = readout_rate
        return self._readout_rate

    def set_temperature(self, temperature):
        """ Set the temperature setpoint """
        self._temperature = temperature

    def set_obtu_behaviour(self, obtu_behaviour):
        pass

    def set_gain(self, gain):
        """ Set the gain

        @param float gain: desired new gain

        @return float: new exposure gain
        """
        pass

    def set_acquisition_mode(self, acquisition_mode):
        pass

    def set_binning_x(self, bin_x):
        pass

    def set_binning_y(self, bin_y):
        pass

    def set_region_of_interest(self, x1, y1, x2, y2):
        pass

    def set_multi_spec(self, ):
        pass

    def set_background_mode(self, bg_mode):
        pass

    ###############################################

    def get_exposure(self):
        """ Get the exposure time in seconds

        @return float exposure time
        """
        pass

    def get_readout_rate(self, readout_rate):
        pass

    def get_temperature(self, temperature):
        pass

    def get_obtu_behaviour(self, obtu_behaviour):
        pass

    def get_gain(self):
        """ Get the gain

        @return float: exposure gain
        """
        pass

    def get_acquisition_mode(self, acquisition_mode):
        pass

    def get_binning_x(self, bin_x):
        pass

    def get_binning_y(self, bin_y):
        pass

    def get_region_of_interest(self, x1, y1, x2, y2):
        pass

    def get_multi_spec(self, ):
        pass

    def get_background_mode(self, bg_mode):
        pass

    def get_camera_status(self, spectrometer_status):
        pass

    def get_acquired_data(self):
        """ Return an array of last acquired image.

        @return numpy array: image data in format [[row],[row]...]

        Each pixel might be a float, integer or sub pixels
        """
        pass

    def get_ready_state(self):
        """ Is the camera ready for an acquisition ?

        @return bool: ready ?
        """
        return self.module_state() == 'idle'



