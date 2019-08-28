# -*- coding: utf-8 -*-

"""
This hardware module implement the camera spectrometer interface to use an Andor Camera.
It use a dll to interface with instruments via USB (only available physical interface)
This module does aim at replacing Solis.

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

from enum import Enum
from ctypes import *
import numpy as np

from core.module import Base, ConfigOption

from interface.camera_interface import CameraInterface
# from interface.setpoint_controller_interface import SetpointControllerInterface
from interface.spectrometer_interface import SpectrometerInterface


class ReadMode(Enum):
    FVB = 0
    MULTI_TRACK = 1
    RANDOM_TRACK = 2
    SINGLE_TRACK = 3
    IMAGE = 4


class AcquisitionMode(Enum):
    SINGLE_SCAN = 1
    ACCUMULATE = 2
    KINETICS = 3
    FAST_KINETICS = 4
    RUN_TILL_ABORT = 5


class TriggerMode(Enum):
    INTERNAL = 0
    EXTERNAL = 1
    EXTERNAL_START = 6
    EXTERNAL_EXPOSURE = 7
    SOFTWARE_TRIGGER = 10
    EXTERNAL_CHARGE_SHIFTING = 12


ERROR_DICT = {
    20001: "DRV_ERROR_CODES",
    20002: "DRV_SUCCESS",
    20003: "DRV_VXNOTINSTALLED",
    20004: "DRV_ERROR_SCAN",
    20005: "DRV_ERROR_CHECK_SUM",
    20006: "DRV_ERROR_FILELOAD",
    20007: "DRV_ERROR_VXD_INIT",
    20008: "DRV_ERROR_VXD_INIT",
    20009: "DRV_ERROR_ADDRESS",
    20010: "DRV_ERROR_PAGELOCK",
    20011: "DRV_ERROR_PAGE_UNLOCK",
    20012: "DRV_ERROR_BOARDTEST",
    20013: "DRV_ERROR_ACK",
    20014: "DRV_ERROR_UP_FIFO",
    20015: "DRV_ERROR_PATTERN",
    20017: "DRV_ACQUISITION_ERRORS",
    20018: "DRV_ACQ_BUFFER",
    20019: "DRV_ACQ_DOWNFIFO_FULL",
    20020: "DRV_PROC_UNKNOWN_INSTRUCTION",
    20021: "DRV_ILLEGAL_OP_CODE",
    20022: "DRV_KINETIC_TIME_NOT_MET",
    20023: "DRV_ACCUM_TIME_NOT_MET",
    20024: "DRV_NO_NEW_DATA",
    20025: "PCI_DMA_FAIL",
    20026: "DRV_SPOOLERROR",
    20027: "DRV_SPOOLSETUPERROR",
    20029: "SATURATED",
    20033: "DRV_TEMPERATURE_CODES",
    20034: "DRV_TEMP_OFF",
    20035: "DRV_TEMP_NOT_STABILIZED",
    20036: "DRV_TEMP_STABILIZED",
    20037: "DRV_TEMP_NOT_REACHED",
    20038: "DRV_TEMP_OUT_RANGE",
    20039: "DRV_TEMP_NOT_SUPPORTED",
    20040: "DRV_TEMP_DRIFT",
    20049: "DRV_GENERAL_ERRORS",
    20050: "DRV_COF_NOTLOADED",
    20051: "DRV_COF_NOTLOADED",
    20052: "DRV_FPGAPROG",
    20053: "DRV_FLEXERROR",
    20054: "DRV_GPIBERROR",
    20055: "ERROR_DMA_UPLOAD",
    20064: "DRV_DATATYPE",
    20065: "DRV_DRIVER_ERRORS",
    20066: "DRV_P1INVALID",
    20067: "DRV_P2INVALID",
    20068: "DRV_P3INVALID",
    20069: "DRV_P4INVALID",
    20070: "DRV_INIERROR",
    20071: "DRV_COERROR",
    20072: "DRV_ACQUIRING",
    20073: "DRV_IDLE",
    20074: "DRV_TEMPCYCLE",
    20075: "DRV_NOT_INITIALIZED",
    20076: "DRV_P5INVALID",
    20077: "DRV_P6INVALID",
    20078: "DRV_INVALID_MODE",
    20079: "DRV_INVALID_FILTER",
    20080: "DRV_I2CERRORS",
    20081: "DRV_DRV_I2CDEVNOTFOUND",
    20082: "DRV_I2CTIMEOUT",
    20083: "P7_INVALID",
    20089: "DRV_USBERROR",
    20090: "DRV_IOCERROR",
    20091: "DRV_NOT_SUPPORTED",
    20093: "DRV_USB_INTERRUPT_ENDPOINT_ERROR",
    20094: "DRV_RANDOM_TRACK_ERROR",
    20095: "DRV_INVALID_TRIGGER_MODE",
    20096: "DRV_LOAD_FIRMWARE_ERROR",
    20097: "DRV_DIVIDE_BY_ZERO_ERROR",
    20098: "DRV_INVALID_RINGEXPOSURES",
    20099: "DRV_BINNING_ERROR",
    20115: "DRV_ERROR_MAP",
    20116: "DRV_ERROR_UNMAP",
    20117: "DRV_ERROR_MDL",
    20118: "DRV_ERROR_UNMDL",
    20119: "DRV_ERROR_BUFFSIZE",
    20121: "DRV_ERROR_NOHANDLE",
    20130: "DRV_GATING_NOT_AVAILABLE",
    20131: "DRV_FPGA_VOLTAGE_ERROR",
    20100: "DRV_INVALID_AMPLIFIER",
    20101: "DRV_INVALID_COUNTCONVERT_MODE"
}


class AndorCameraSpectrometer(Base, CameraInterface, SpectrometerInterface):
    """ Hardware class for Andors Ixon Ultra 897

    Example config for copy-paste:

    andor_ultra_camera:
        module.Class: 'camera.andor.iXon897_ultra.IxonUltra'
        dll_location: 'C:\\camera\\andor.dll' # path to library file
        default_exposure: 1.0
        default_read_mode: 'IMAGE'
        default_temperature: -70
        default_cooler_on: True
        default_acquisition_mode: 'SINGLE_SCAN'
        default_trigger_mode: 'INTERNAL'

    """

    _modtype = 'camera'
    _modclass = 'hardware'

    _dll_location = ConfigOption('dll_location', missing='error')
    _default_exposure = ConfigOption('default_exposure', 1.0)
    _default_read_mode = ConfigOption('default_read_mode', 'IMAGE')
    _default_temperature = ConfigOption('default_temperature', -70)
    _default_cooler_on = ConfigOption('default_cooler_on', True)
    _default_acquisition_mode = ConfigOption('default_acquisition_mode', 'SINGLE_SCAN')
    _default_trigger_mode = ConfigOption('default_trigger_mode', 'INTERNAL')
    _camera_name = ConfigOption('camera_name', 'Unconfigured Andor camera', missing='warn')

    _dll = None
    _exposure = _default_exposure
    _temperature = _default_temperature
    _cooler_on = _default_cooler_on
    _read_mode = _default_read_mode
    _acquisition_mode = _default_acquisition_mode
    _gain = 0
    _width = 0
    _height = 0
    _last_acquisition_mode = None  # useful if config changes during acq
    _supported_read_mode = ReadMode  # TODO: read this from camera, all readmodes are available for iXon Ultra
    _max_cooling = -100
    _live = False
    _shutter = "closed"
    _trigger_mode = _default_trigger_mode
    _scans = 1  # TODO get from camera
    _acquiring = False
    _tracks = [None]

    def on_activate(self):
        """ Initialisation performed during activation of the module.
         """
        self._dll = cdll.LoadLibrary(self._dll_location)
        self._dll.Initialize()
        self._width, self._height = self._get_detector_size()
        self._set_read_mode(self._read_mode)
        self._set_trigger_mode(self._trigger_mode)
        self._set_exposuretime(self._exposure)
        self._set_acquisition_mode(self._acquisition_mode)
        self._set_cooler(self._cooler_on)
        self._set_temperature(self._temperature)

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.
        """
        self.stop_acquisition()
        self._set_shutter(0, 0, 0.1, 0.1)
        self._shut_down()
        self._dll = None

    def get_name(self):
        """ Retrieve an identifier of the camera that the GUI can print

        @return string: name for the camera
        """
        return self._camera_name

    def get_size(self):
        """ Retrieve size of the image in pixel

        @return tuple: Size (width, height)
        """
        return self._width, self._height

    def support_live_acquisition(self):
        """ Return whether or not the camera can take care of live acquisition

        @return bool: True if supported, False if not
        """
        return False

    def start_live_acquisition(self):
        """ Start a continuous acquisition

        @return bool: Success ?
        """
        if self.support_live_acquisition():
            self._live = True
            self._acquiring = False
            return True
        return False

    def start_single_acquisition(self):
        """ Start a single acquisition - camera interface

        @return bool: Success ?
        """
        if self._shutter == 'closed':
            msg = self._set_shutter(0, 1, 0.1, 0.1)
            if msg == 'DRV_SUCCESS':
                self._shutter = 'open'
            else:
                self.log.error('shutter did not open.{0}'.format(msg))

        if self._live:
            return False
        else:
            if self._read_mode != 'IMAGE':
                self._set_read_mode('IMAGE')
            self._acquiring = True
            msg = self._start_acquisition()
            if msg != "DRV_SUCCESS":
                return False

            self._acquiring = False
            return True

    def stop_acquisition(self):
        """ Stop/abort live or single acquisition

        @return bool: Success ?
        """
        msg = self._abort_acquisition()
        if msg == "DRV_SUCCESS":
            self._live = False
            self._acquiring = False
            return True
        else:
            return False

    def get_acquired_data(self):
        """ Return an array of last acquired image.

        @return numpy array: image data in format [[row],[row]...]

        Each pixel might be a float, integer or sub pixels
        """

        width = self._width
        height = self._height

        if self._read_mode == 'IMAGE':
            if self._acquisition_mode == 'SINGLE_SCAN':
                dim = width * height
            elif self._acquisition_mode == 'KINETICS':
                dim = width * height * self._scans
            elif self._acquisition_mode == 'RUN_TILL_ABORT':
                dim = width * height
            else:
                self.log.error('Your acquisition mode is not covered currently')
        elif self._read_mode == 'SINGLE_TRACK' or self._read_mode == 'FVB':
            if self._acquisition_mode == 'SINGLE_SCAN':
                dim = width
            elif self._acquisition_mode == 'KINETICS':
                dim = width * self._scans
        else:
            self.log.error('Your acquisition mode is not covered currently')

        dim = int(dim)
        image_array = np.zeros(dim)
        cimage_array = c_int * dim
        cimage = cimage_array()

        # this will be a bit hacky
        if self._acquisition_mode == 'RUN_TILL_ABORT':
            error_code = self._dll.GetOldestImage(pointer(cimage), dim)
        else:
            error_code = self._dll.GetAcquiredData(pointer(cimage), dim)
        if ERROR_DICT[error_code] != 'DRV_SUCCESS':
            self.log.warning('Couldn\'t retrieve an image. {0}'.format(ERROR_DICT[error_code]))
        else:
            self.log.debug('image length {0}'.format(len(cimage)))
            for i in range(len(cimage)):
                # could be problematic for 'FVB' or 'SINGLE_TRACK' readmode
                image_array[i] = cimage[i]

        if self._read_mode == 'IMAGE':
            image_array = np.reshape(image_array, (self._width, self._height))
        elif self._read_mode == 'SINGLE_TRACK' or self._read_mode == 'FVB':
            pass
        self._cur_image = image_array
        return image_array

    def set_exposure(self, exposure):
        """ Set the exposure time in seconds

        @param float time: desired new exposure time

        @return bool: Success?
        """
        msg = self._set_exposuretime(exposure)
        if msg == "DRV_SUCCESS":
            self._exposure = exposure
            return True
        else:
            return False

    def get_exposure(self):
        """ Get the exposure time in seconds

        @return float exposure time
        """
        self._get_acquisition_timings()
        return self._exposure

    # not sure if the distinguishing between gain setting and gain value will be problematic for
    # this camera model. Just keeping it in mind for now.
    #TODO: Not really funcitonal right now.
    def set_gain(self, gain):
        """ Set the gain

        @param float gain: desired new gain

        @return float: new exposure gain
        """
        n_pre_amps = self._get_number_preamp_gains()
        msg = ''
        if (gain >= 0) & (gain < n_pre_amps):
            msg = self._set_preamp_gain(gain)
        else:
            self.log.warning('Choose gain value between 0 and {0}'.format(n_pre_amps-1))
        if msg == 'DRV_SUCCESS':
            self._gain = gain
        else:
            self.log.warning('The gain wasn\'t set. {0}'.format(msg))
        return self._gain

    def get_gain(self):
        """ Get the gain

        @return float: exposure gain
        """
        self._gain = self._get_preamp_gain()
        return self._gain

    def get_ready_state(self):
        """ Is the camera ready for an acquisition ?

        @return bool: ready ?
        """
        status = c_int()
        self._get_status(status)
        if ERROR_DICT[status.value] == 'DRV_IDLE':
            return True
        else:
            return False


# non interface functions regarding camera interface
    def _abort_acquisition(self):
        error_code = self._dll.AbortAcquisition()
        return ERROR_DICT[error_code]

    def _shut_down(self):
        error_code = self._dll.ShutDown()
        return ERROR_DICT[error_code]

    def _start_acquisition(self):
        error_code = self._dll.StartAcquisition()
        self._dll.WaitForAcquisition()
        return ERROR_DICT[error_code]

# setter functions

    def _set_shutter(self, typ, mode, closingtime, openingtime):
        """
        @param int typ:   0 Output TTL low signal to open shutter
                          1 Output TTL high signal to open shutter
        @param int mode:  0 Fully Auto
                          1 Permanently Open
                          2 Permanently Closed
                          4 Open for FVB series
                          5 Open for any series
        """
        typ, mode, closingtime, openingtime = c_int(typ), c_int(mode), c_float(closingtime), c_float(openingtime)
        error_code = self._dll.SetShutter(typ, mode, closingtime, openingtime)

        return ERROR_DICT[error_code]

    def _set_exposuretime(self, time):
        """
        @param float time: exposure duration
        @return string answer from the camera
        """
        error_code = self._dll.SetExposureTime(c_float(time))
        return ERROR_DICT[error_code]

    def _set_read_mode(self, mode):
        """
        @param string mode: string corresponding to certain ReadMode
        @return string answer from the camera
        """
        check_val = 0

        if hasattr(ReadMode, mode):
            n_mode = getattr(ReadMode, mode).value
            n_mode = c_int(n_mode)
            error_code = self._dll.SetReadMode(n_mode)
            if mode == 'IMAGE':
                self.log.debug("widt:{0}, height:{1}".format(self._width, self._height))
                msg = self._set_image(1, 1, 1, self._width, 1, self._height)
                if msg != 'DRV_SUCCESS':
                    self.log.warning('{0}'.format(ERROR_DICT[error_code]))
        if ERROR_DICT[error_code] != 'DRV_SUCCESS':
            self.log.warning('Readmode was not set: {0}'.format(ERROR_DICT[error_code]))
            check_val = -1
        else:
            self._read_mode = mode

        return check_val

    def _set_trigger_mode(self, mode):
        """
        @param string mode: string corresponding to certain TriggerMode
        @return string: answer from the camera
        """
        check_val = 0
        if hasattr(TriggerMode, mode):
            n_mode = c_int(getattr(TriggerMode, mode).value)
            self.log.debug('Input to function: {0}'.format(n_mode))
            error_code = self._dll.SetTriggerMode(n_mode)
        else:
            self.log.warning('{0} mode is not supported'.format(mode))
            check_val = -1
        if ERROR_DICT[error_code] != 'DRV_SUCCESS':
            check_val = -1
        else:
            self._trigger_mode = mode

        return check_val

    def _set_image(self, hbin, vbin, hstart, hend, vstart, vend):
        """
        This function will set the horizontal and vertical binning to be used when taking a full resolution image.
        Parameters
        @param int hbin: number of pixels to bin horizontally
        @param int vbin: number of pixels to bin vertically. int hstart: Start column (inclusive)
        @param int hend: End column (inclusive)
        @param int vstart: Start row (inclusive)
        @param int vend: End row (inclusive).

        @return string containing the status message returned by the function call
        """
        hbin, vbin, hstart, hend, vstart, vend = c_int(hbin), c_int(vbin),\
                                                 c_int(hstart), c_int(hend), c_int(vstart), c_int(vend)

        error_code = self._dll.SetImage(hbin, vbin, hstart, hend, vstart, vend)
        msg = ERROR_DICT[error_code]
        if msg == 'DRV_SUCCESS':
            self._hbin = hbin.value
            self._vbin = vbin.value
            self._hstart = hstart.value
            self._hend = hend.value
            self._vstart = vstart.value
            self._vend = vend.value
            self._width = int((self._hend - self._hstart + 1) / self._hbin)
            self._height = int((self._vend - self._vstart + 1) / self._vbin)
        else:
            self.log.error('Call to SetImage went wrong:{0}'.format(msg))
        return ERROR_DICT[error_code]

    def _set_output_amplifier(self, typ):
        """
        @param c_int typ: 0: EMCCD gain, 1: Conventional CCD register
        @return string: error code
        """
        error_code = self._dll.SetOutputAmplifier(typ)
        return ERROR_DICT[error_code]

    def _set_preamp_gain(self, index):
        """
        @param c_int index: 0 - (Number of Preamp gains - 1)
        """
        error_code = self._dll.SetPreAmpGain(index)
        return ERROR_DICT[error_code]

    def _get_number_hs_speed(self, channel=0, typ=0):
        """ Return the number of horizontal shift speed on a given channel

        @param (int) channel: The AD channel (zero if only one)
        @param (int) typ: output amplification (0 = electron multiplication, 1 = conventional)
        @return (int): The number of horizontal shift speed available
        """
        channel = c_int(channel)
        typ = c_int(typ)
        speeds = c_int()
        self._dll.GetNumberHSSpeeds(channel, typ, byref(speeds))
        return speeds.value

    def _get_hs_speed(self, channel=0, typ=0, index=0):
        """ Return the speed associated with a given index in MHz

        @param (int) channel: The AD channel (zero if only one)
        @param (int) typ: output amplification (0 = electron multiplication, 1 = conventional)
        @param (int) index: The index of the speed
        @return (float): The speed in MHz

        As your Andor system is capable of operating at more than one horizontal shift speed this function will
         return the actual speeds available. The value returned is in MHz.
        """
        channel = c_int(channel)
        typ = c_int(typ)
        index = c_int(index)
        speed = c_float()
        self._dll.GetHSSpeed(channel, typ, index, byref(speed))
        return speed.value

    def _set_hs_speed(self, typ=0, index=0):
        """ Set the horizontal shift speed based on a given index

        @param (int) typ: output amplification (0 = electron multiplication, 1 = conventional)
        @param (int) index: The index of the speed
        return(bool): Sucess ?

        This function will set the speed at which the pixels are shifted into the output node during the readout phase
         of an acquisition. Typically your camera will be capable of operating at several horizontal shift speeds.
        To get the actual speed that an index corresponds to use the GetHSSpeed function.
        """
        typ = c_int(typ)
        index = c_int(index)
        error_code = self._dll.SetHSSpeed(typ, index)
        if ERROR_DICT[error_code] == 'DRV_SUCCESS':
            return True
        else:
            self.log.error('Could not set the horizontal shift speed : {}'.format(ERROR_DICT[error_code]))
            return False

    def _set_temperature(self, temp):
        if 20 > temp > self._max_cooling:
            self._temperature = temp
            temp = c_int(temp)
            error_code = self._dll.SetTemperature(temp)
        return ERROR_DICT[error_code]

    def _set_acquisition_mode(self, mode):
        """ Function to set the acquisition mode
        @param mode:
        @return:
        """
        check_val = 0
        if hasattr(AcquisitionMode, mode):
            n_mode = c_int(getattr(AcquisitionMode, mode).value)
            error_code = self._dll.SetAcquisitionMode(n_mode)
        else:
            self.log.warning('{0} mode is not supported'.format(mode))
            check_val = -1
        if ERROR_DICT[error_code] != 'DRV_SUCCESS':
            check_val = -1
        else:
            self._acquisition_mode = mode

        return check_val

    def _set_cooler(self, state):
        self._cooler_on = state
        if state:
            error_code = self._dll.CoolerON()
        else:
            error_code = self._dll.CoolerOFF()

        return ERROR_DICT[error_code]

    def _set_frame_transfer(self, bool):
        acq_mode = self._acquisition_mode

        if (acq_mode == 'SINGLE_SCAN') | (acq_mode == 'KINETIC'):
            self.log.debug('Setting of frame transfer mode has no effect in acquisition '
                           'mode \'SINGLE_SCAN\' or \'KINETIC\'.')
            return -1
        else:
            if bool:
                rtrn_val = self._dll.SetFrameTransferMode(1)
            else:
                rtrn_val = self._dll.SetFrameTransferMode(0)

        if ERROR_DICT[rtrn_val] == 'DRV_SUCCESS':
            return 0
        else:
            self.log.warning('Could not set frame transfer mode:{0}'.format(ERROR_DICT[rtrn_val]))
            return -1

# getter functions
    def _get_status(self, status):
        error_code = self._dll.GetStatus(byref(status))
        return ERROR_DICT[error_code]

    def _get_detector(self, nx_px, ny_px):
        error_code = self._dll.GetDetector(byref(nx_px), byref(ny_px))
        return ERROR_DICT[error_code]

    def _get_detector_size(self):
        nx_px, ny_px = c_int(), c_int()
        self._get_detector(nx_px, ny_px)
        return nx_px.value, ny_px.value

    def _get_camera_serialnumber(self, number):
        """ Gives serial number parameters
        """
        error_code = self._dll.GetCameraSerialNumber(byref(number))
        return ERROR_DICT[error_code]

    def _get_acquisition_timings(self):
        exposure = c_float()
        accumulate = c_float()
        kinetic = c_float()
        error_code = self._dll.GetAcquisitionTimings(byref(exposure),
                                               byref(accumulate),
                                               byref(kinetic))
        self._exposure = exposure.value
        self._accumulate = accumulate.value
        self._kinetic = kinetic.value
        return ERROR_DICT[error_code]

    # def _get_oldest_image(self):
    #     """ Return an array of last acquired image.
    #
    #     @return numpy array: image data in format [[row],[row]...]
    #
    #     Each pixel might be a float, integer or sub pixels
    #     """
    #
    #     width = self._width
    #     height = self._height
    #
    #     if self._read_mode == 'IMAGE':
    #         if self._acquisition_mode == 'SINGLE_SCAN':
    #             dim = width * height / self._hbin / self._vbin
    #         elif self._acquisition_mode == 'KINETICS':
    #             dim = width * height / self._hbin / self._vbin * self._scans
    #     elif self._read_mode == 'SINGLE_TRACK' or self._read_mode == 'FVB':
    #         if self._acquisition_mode == 'SINGLE_SCAN':
    #             dim = width
    #         elif self._acquisition_mode == 'KINETICS':
    #             dim = width * self._scans
    #
    #     dim = int(dim)
    #     image_array = np.zeros(dim)
    #     cimage_array = c_int * dim
    #     cimage = cimage_array()
    #     error_code = self._dll.GetOldestImage(pointer(cimage), dim)
    #     if ERROR_DICT[error_code] != 'DRV_SUCCESS':
    #         self.log.warning('Couldn\'t retrieve an image')
    #     else:
    #         self.log.debug('image length {0}'.format(len(cimage)))
    #         for i in range(len(cimage)):
    #             # could be problematic for 'FVB' or 'SINGLE_TRACK' readmode
    #             image_array[i] = cimage[i]
    #
    #     image_array = np.reshape(image_array, (int(self._width/self._hbin), int(self._height/self._vbin)))
    #     return image_array

    def _get_number_amp(self):
        """
        @return int: Number of amplifiers available
        """
        n_amps = c_int()
        self._dll.GetNumberAmp(byref(n_amps))
        return n_amps.value

    def _get_number_preamp_gains(self):
        """
        Number of gain settings available for the pre amplifier

        @return int: Number of gains available
        """
        n_gains = c_int()
        self._dll.GetNumberPreAmpGains(byref(n_gains))
        return n_gains.value

    def _get_preamp_gain(self, index=0):
        """ Get the gain associated with a given index

        @return (float): The gain of the given index

        Warning: This function does not give the current preamp gain. In fact no function does this. This module
        has to keep track of the last sent value.
        """
        index = c_int(index)
        gain = c_float()
        self._dll.GetPreAmpGain(index, byref(gain))
        return gain.value

    def _get_temperature(self):
        temp = c_int()
        self._dll.GetTemperature(byref(temp))
        return temp.value

    def _get_temperature_f(self):
        """
        Status of the cooling process + current temperature
        @return: (float, str) containing current temperature and state of the cooling process
        """
        temp = c_float()
        error_code = self._dll.GetTemperatureF(byref(temp))

        return temp.value, ERROR_DICT[error_code]

    def _get_size_of_circular_ring_buffer(self):
        index = c_long()
        error_code = self._dll.GetSizeOfCircularBuffer(byref(index))
        if ERROR_DICT[error_code] != 'DRV_SUCCESS':
            self.log.error('Can not retrieve size of circular ring '
                           'buffer: {0}'.format(ERROR_DICT[error_code]))
        return index.value

    def _get_number_new_images(self):
        first = c_long()
        last = c_long()
        error_code = self._dll.GetNumberNewImages(byref(first), byref(last))
        msg = ERROR_DICT[error_code]
        pass_returns = ['DRV_SUCCESS', 'DRV_NO_NEW_DATA']
        if msg not in pass_returns:
            self.log.error('Can not retrieve number of new images {0}'.format(ERROR_DICT[error_code]))
        return first.value, last.value

    def _set_single_track(self, centre, height):
        centre = c_int(centre)
        height = c_int(height)
        error_code = self._dll.SetSingleTrack(centre, height)
        msg = ERROR_DICT[error_code]
        pass_returns = ['DRV_SUCCESS']
        if msg not in pass_returns:
            self.log.error('Can not set single track : {}'.format(msg))
            return False
        return True

    def set_tracks(self, tracks):
        if tracks is None:
            self._tracks = []
        else:
            self._tracks = tracks

        if len(self._tracks) == 1:
            self._set_single_track(*self._tracks[0])

        if len(self._tracks) > 1:
            self.log.error('Multi track not supported yet')

    # not working properly (only for n_scans = 1)
    # def _get_images(self, first_img, last_img, n_scans):
    #     """ Return an array of last acquired image.
    #
    #     @return numpy array: image data in format [[row],[row]...]
    #
    #     Each pixel might be a float, integer or sub pixels
    #     """
    #
    #     width = self._width
    #     height = self._height
    #
    #     # first_img, last_img = self._get_number_new_images()
    #     # n_scans = last_img - first_img
    #     dim = width * height * n_scans
    #
    #     dim = int(dim)
    #     image_array = np.zeros(dim)
    #     cimage_array = c_int * dim
    #     cimage = cimage_array()
    #
    #     first_img = c_long(first_img)
    #     last_img = c_long(last_img)
    #     size = c_ulong(width * height)
    #     val_first = c_long()
    #     val_last = c_long()
    #     error_code = self._dll.GetImages(first_img, last_img, pointer(cimage),
    #                                     size, byref(val_first), byref(val_last))
    #     if ERROR_DICT[error_code] != 'DRV_SUCCESS':
    #         self.log.warning('Couldn\'t retrieve an image. {0}'.format(ERROR_DICT[error_code]))
    #     else:
    #         for i in range(len(cimage)):
    #             # could be problematic for 'FVB' or 'SINGLE_TRACK' readmode
    #             image_array[i] = cimage[i]
    #
    #     self._cur_image = image_array
    #     return image_array

# interface functions regarding setpoint interface
    def get_enabled(self):
        """ setpoint_controller_interface : get if the cooling is on """
        return self._cooler_on

    def set_enabled(self, enabled):
        """ setpoint_controller_interface : set if the cooling is on """
        self._set_cooler(enabled)

    def get_process_value(self):
        """ process_interface : Get measured value of the temperature """
        return self._get_temperature()

    def get_process_unit(self):
        """ process_interface : Return the unit of measured temperature """
        return '°C', 'Degrees Celsius'

    def set_setpoint(self, value):
        """ 'setpoint_interface' : set the setpoint temperature for the camera """
        self._set_temperature(value)

    def get_setpoint(self):
        """ 'setpoint_interface' : get the setpoint temperature for the camera """
        return self._temperature()

    def get_setpoint_unit(self):
        """ setpoint_interface : Return the unit of setpoint temperature """
        return self.get_process_unit()

    def get_setpoint_limits(self):
        """ setpoint_interface : Return the limits for the setpoint temperature """
        return self._max_cooling, 20.

# interface functions regarding spectrometer interface

    def recordSpectrum(self):
        """ Record a spectrum and return it """
        if len(self._tracks) == 0 and self._read_mode != 'FVB':
            self._set_read_mode('FVB')
        elif len(self._tracks) == 1 and self._read_mode != 'SINGLE_TRACK':
            self._set_read_mode('SINGLE_TRACK')

        self._start_acquisition()
        data = self.get_acquired_data()
        return data

    def setExposure(self, exposureTime):
        """ SpectrometerInterface : set exposure in seconds """
        self.set_exposure(exposureTime)

    def getExposure(self):
        """ SpectrometerInterface : get exposure in seconds """
        return self.get_exposure()

# helper function for scripts to take an image
    def record_image(self):
        """ Record a spectrum and return it """
        self._set_read_mode('IMAGE')
        self.start_single_acquisition()
        data = self.get_acquired_data()
        return data
