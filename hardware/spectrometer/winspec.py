# -*- coding: utf-8 -*-
"""
This module contains fake a spectrometer camera.

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
import comtypes.client as ctc
import win32com.client as w32c
import time
from ctypes import byref, pointer, c_long, c_float, c_bool

from core.module import Base
from interface.science_camera_interface import ScienceCameraInterface
from interface.science_camera_interface import ReadMode, Constraints, ImageAdvancedParameters, ShutterState

# Winspec uses a COM library for external scripting. It's a bit like a DLL but with a unique identifier declared
# so that windows find the library
COM_ERROR = False
try:
    ctc.GetModule(('{1A762221-D8BA-11CF-AFC2-508201C10000}', 3, 11))  # Winspec unique id
    import comtypes.gen.WINX32Lib as WinSpecLib
except:  # todo: add clause
    COM_ERROR = True  # Let's store the error to print it at activation


class Main(Base, ScienceCameraInterface):
    """ This module interface with Winspec to interface the hardware as a camera and grating spectrometer

    Example config for copy-paste:

    winspec:
        module.Class: 'spectrometer.winspec.Main'
    """

    def on_activate(self):
        """ Activate module """

        if COM_ERROR:
            self.log.error('Connexion to Winspec failed. \
                            On windows 7, starting Winspec ONCE as administrator can help.')
            return

        w32c.pythoncom.CoInitialize()
        self._exp_setup = w32c.Dispatch("WinX32.ExpSetup")
        self._build_constraints()

    def on_deactivate(self):
        """ Deactivate module """
        if self.module_state() == 'locked':
            self.stop_acquisition()

    def get_constraints(self):
        """ Returns all the fixed parameters of the hardware which can be used by the logic.

        @return (Constraints): An object of class Constraints containing all fixed parameters of the hardware
        """
        return self._constraints

    def _get(self, parameter_number):
        """ Function that query the library to get parameters value

        @param (int) parameter_number: Parameter associated constant as WinSpecLib.EXP_SOMEPARAM

        @return (int|float): The current value"""
        value, status = self._exp_setup.GetParam(parameter_number)
        if status == 0:
            return value
        else:
            self.log.error('Error while getting the {} parameter.'.format(parameter_number))

    def _set(self, parameter_number, value):
        """ Function that query the library to set parameters value

        @param (int) parameter_number: Parameter associated constant as WinSpecLib.EXP_SOMEPARAM
        @param (int): The value to set """
        status = self._exp_setup.SetParam(parameter_number, value)
        if status != 0:
            self.log.error('Error while setting the parameter {} with value {}.'.format(parameter_number, value))

    def _build_constraints(self):
        """ Internal method that build the constraints once at initialisation

         This makes multiple call to the DLL, so it will be called only once by on_activate
         """
        constraints = Constraints()
        constraints.name = "Winspec"
        constraints.width, constraints.height = self._get_image_size()
        constraints.pixel_size_width, constraints.pixel_size_height = self._get_pixel_size()
        constraints.internal_gains = self._get_available_gains()
        constraints.readout_speeds = self._get_available_speeds()
        constraints.trigger_modes = self._get_available_trigger_modes()
        constraints.has_shutter = self._has_shutter()
        constraints.read_modes = [ReadMode.FVB]
        if constraints.height > 1:
            constraints.read_modes.extend([ReadMode.IMAGE])
        constraints.has_cooler = True
        constraints.temperature.min, constraints.temperature.max = self._get_temperature_range()
        constraints.temperature.step = .5

        self._constraints = constraints

    def get_constraints(self):
        """ Returns all the fixed parameters of the hardware which can be used by the logic.

        @return (Constraints): An object of class Constraints containing all fixed parameters of the hardware
        """
        return self._constraints

    ##############################################################################
    #                                     Basic functions
    ##############################################################################
    def start_acquisition(self):
        """ Starts the acquisition """
        self._doc_file = w32c.Dispatch("WinX32.DocFile")
        self._doc_files = w32c.Dispatch("WinX32.DocFiles")
        self._exp_setup = w32c.Dispatch("WinX32.ExpSetup")
        status = self._exp_setup.Start(self._doc_file)[0]
        return status  # todo: check

    def _wait_for_acquisition(self):
        """ Internal function, can be used to wait till acquisition is finished """
        while not self.get_ready_state():
            time.sleep(0.1)

    def abort_acquisition(self):
        """ Aborts the acquisition """
        pass  # todo...(no mannual)

    def get_ready_state(self):
        """ Get the status of the camera, to know if the acquisition is finished or still ongoing.

        @return (bool): True if the camera is ready, False if an acquisition is ongoing
        """
        is_running = self._get(WinSpecLib.EXP_RUNNING)
        return not is_running

    def get_acquired_data(self):
        """ Return an array of last acquired data.

               @return: Data in the format depending on the read mode.

               Depending on the read mode, the format is :
               'FVB' : 1d array
               'MULTIPLE_TRACKS' : list of 1d arrays
               'IMAGE' 2d array of shape (width, height)
               'IMAGE_ADVANCED' 2d array of shape (width, height)

               Each value might be a float or an integer.
               """
        width = self.get_constraints().width
        if self.get_read_mode() == ReadMode.FVB:
            height = 1
        elif self.get_read_mode() == ReadMode.IMAGE:
            height = self.get_constraints().height

        data_pointer = c_float()
        data = np.array(self._doc_file.GetFrame(1, data_pointer))

        if self.get_read_mode() == ReadMode.FVB:
            return np.array(data)
        else:
            return np.reshape(np.array(data), (width, height)).transpose()

    def _get_xaxis(self):
        """ Function that return the x axis in meter computed by WinSpec

        @return np.array(float): A 1d array of the wavelength of each pixel in meter

        WinSpec doesn't actually store the wavelength information as an array but instead calculates it every time
        it plot using the calibration information stored with the spectrum.
        """
        #doc_file = w32c.Dispatch("WinX32.DocFile")
        calibration = self._doc_file.GetCalibration()
        if calibration.Order != 2:
            self.log.error('Cannot handle current WinSpec wavelength calibration.')

        p = np.array([calibration.PolyCoeffs(2),calibration.PolyCoeffs(1), calibration.PolyCoeffs(0)])
        axis = np.polyval(p, range(1, 1 + self.get_constraints().width)) * 1e-9  # WinSpec talks in nm
        return axis

    ##############################################################################
    #                           Read mode functions
    ##############################################################################
    def get_read_mode(self):
        """ Getter method returning the current read mode used by the camera.

        @return (ReadMode): Current read mode
        """
        value = self._get(WinSpecLib.EXP_ROIMODE)
        if value == 0:
            return ReadMode.FVB
        elif value == 1:
            return ReadMode.IMAGE

    def set_read_mode(self, value):
        """ Setter method setting the read mode used by the camera.

         @param (ReadMode) value: read mode to set
         """
        if value not in self.get_constraints().read_modes:
            self.log.error('read_mode not supported')
            return

        conversion_dict = {ReadMode.FVB: 0,
                           ReadMode.IMAGE: 1}

        n_mode = conversion_dict[value]
        self._set(WinSpecLib.EXP_ROIMODE, n_mode)

    def get_readout_speed(self):
        """  Get the current readout speed (in Hz)

        @return (float): the readout_speed (Horizontal shift) in Hz
        """
        return self._readout_speed  # No getter in the DLL

    def set_readout_speed(self, value):
        """ Set the readout speed (in Hz)

        @param (float) value: horizontal readout speed in Hz
        """
        pass

    def get_active_tracks(self):
        """ Getter method returning the read mode tracks parameters of the camera.

        @return (list):  active tracks positions [(start_1, end_1), (start_2, end_2), ... ]
        """
        pass

    def set_active_tracks(self, value):
        """ Setter method for the active tracks of the camera.

        @param (list) value: active tracks positions  as [(start_1, end_1), (start_2, end_2), ... ]
        """
        pass

    def get_image_advanced_parameters(self):
        """ Getter method returning the image parameters of the camera.

        @return (ImageAdvancedParameters): Current image advanced parameters

        Should only be used while in IMAGE_ADVANCED mode
        """
        pass

    def set_image_advanced_parameters(self, value):
        """ Setter method setting the read mode image parameters of the camera.

        @param (ImageAdvancedParameters) value: Parameters to set

        Should only be used while in IMAGE_ADVANCED mode
        """
        pass

    def get_exposure_time(self):
        """ Get the exposure time in seconds

        @return (float) : exposure time in s
        """
        return self._get(WinSpecLib.EXP_EXPOSURE)

    def set_exposure_time(self, value):
        """ Set the exposure time in seconds

        @param (float) value: desired new exposure time
        """
        self._set(WinSpecLib.EXP_EXPOSURE, value)

    def get_gain(self):
        """ Get the gain

        @return (float): exposure gain
        """
        return 1

    def set_gain(self, value):
        """ Set the gain

        @param (float) value: New gain, value should be one in the constraints internal_gains list.
        """
        pass

    ##############################################################################
    #                           Trigger mode functions
    ##############################################################################
    def get_trigger_mode(self):
        """ Getter method returning the current trigger mode used by the camera.

        @return (str): current trigger mode
        """
        return 'INTERNAL'

    def set_trigger_mode(self, value):
        """ Setter method for the trigger mode used by the camera.

        @param (str) value: trigger mode (must be compared to a dict)
        """
        pass

    ##############################################################################
    #                           Shutter mode functions
    ##############################################################################
    def get_shutter_state(self):
        """ Getter method returning the shutter state.

        @return (ShutterState): The current shutter state
        """
        pass

    def set_shutter_state(self, value):
        """ Setter method setting the shutter state.

        @param (ShutterState) value: the shutter state to set
        """
        pass

    ##############################################################################
    #                           Temperature functions
    ##############################################################################
    def get_cooler_on(self):
        """ Getter method returning the cooler status

        @return (bool): True if the cooler is on
        """
        return True

    def set_cooler_on(self, value):
        """ Setter method for the the cooler status

        @param (bool) value: True to turn it on, False to turn it off
        """
        pass

    def get_temperature(self):
        """ Getter method returning the temperature of the camera.

        @return (float): temperature (in Kelvin)
        """
        return self._get(WinSpecLib.EXP_ACTUAL_TEMP) + 273.15

    def get_temperature_setpoint(self):
        """ Getter method for the temperature setpoint of the camera.

        @return (float): Current setpoint in Kelvin
        """
        return self._get(WinSpecLib.EXP_TEMPERATURE) + 273.15

    def set_temperature_setpoint(self, value):
        """ Setter method for the the temperature setpoint of the camera.

        @param (float) value: New setpoint in Kelvin
        """
        constraints = self.get_constraints().temperature
        if not(constraints.min < value < constraints.max):
            self.log.error('Temperature {} K is not in the validity range.'.format(value))
            return
        temperature = int(round(value - 273.15))
        self._set(WinSpecLib.EXP_TEMPERATURE, temperature)

    ##############################################################################
    #               Internal functions, for constraints preparation
    ##############################################################################
    def _get_image_size(self):
        """ Returns the sensor size in pixels (width, height)

        @return tuple(int, int): number of pixel in width and height
        """
        x = self._get(WinSpecLib.EXP_XDIMDET)
        y = self._get(WinSpecLib.EXP_YDIMDET)
        return x, y

    def _get_pixel_size(self):
        """ Get the physical pixel size (width, height) in meter

        @return tuple(float, float): physical pixel size in meter
        """
        x = self._get(WinSpecLib.EXP_CELL_X_SIZE)
        y = self._get(WinSpecLib.EXP_CELL_Y_SIZE)
        return x, y  #todo: check unit and EXP_X_GAP_SIZE

    def _get_temperature_range(self):
        """ Get the temperature minimum and maximum of the camera, in K

        @return tuple(float, float): The minimum minimum and maximum allowed for the setpoint in K """
        return 0, 300  #todo

    def _get_available_gains(self):
        """ Return a list of the possible preamplifier gains

        @return (list(float)): A list of the gains supported by the camera
        """
        return [1.]  #todo

    def _get_available_speeds(self):
        """ Return a list of the possible readout speeds

        @return (list(float)): A list of the readout speeds supported by the camera
        """
        return [0]  # todo

    def _get_available_trigger_modes(self):
        """ Return a list of the trigger mode available to the camera

        @return list(str): A list of the trigger mode available to the dll """
        modes = ['INTERNAL']
        return modes

    def _has_shutter(self):
        """ Return if the camera have a mechanical shutter installed

        @return (bool): True if the camera have a shutter
        """
        return False