# -*- coding: utf-8 -*-
"""
This file contains the Qudi hardware module for the TimeHarp260.

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

import ctypes
import numpy as np
import time
from qtpy import QtCore
import os

from core.module import Base, ConfigOption
from core.util.modules import get_main_dir
from core.util.mutex import Mutex
from interface.slow_counter_interface import SlowCounterInterface
from interface.slow_counter_interface import SlowCounterConstraints
from interface.slow_counter_interface import CountingMode
from interface.fast_counter_interface import FastCounterInterface

# =============================================================================
# Wrapper around the TH260Lib64.DLL. The current file is based on the header files
# 'thdefin.h', 'thlib.h' and 'errorcodesTH.h'. The 'thdefin.h' contains all the
# constants and 'thlib.h' contains all the functions exported within the dll
# file. 'errorcodesTH.h' contains the possible error messages of the device.
#
# The wrappered commands are based on the PHLib Version 3.0. For further
# information read the manual
#       'THLib - Programming Library for Custom Software Development'
# which can be downloaded from the PicoQuant homepage.
# =============================================================================

class TimeHarp260(Base, SlowCounterInterface, FastCounterInterface):
    """ Hardware class to control the TimeHarp 260 from PicoQuant.
    """

    _deviceID = ConfigOption('deviceID', 0, missing='warn')
    _mode = ConfigOption('mode', 0, missing='warn')
    _dll_name = ConfigOption('dll', 'th260lib64')

    _count_channel = ConfigOption('count_channel', 0)
    _input_CFD_discriminator = ConfigOption('input_CFD_discriminator', -50)
    _input_CFD_zero_cross = ConfigOption('input_CFD_zero_cross', -10)
    _input_channel_offset = ConfigOption('input_channel_offset', 0)
    _sync_CFD_discriminator = ConfigOption('sync_CFD_discriminator', -50)
    _sync_CFD_zero_cross = ConfigOption('sync_CFD_zero_cross', -10)
    _sync_div = ConfigOption('sync_div', 1)
    _sync_channel_offset = ConfigOption('sync_channel_offset', 0)
    _PS_TO_S = 1e-12

    sigStart = QtCore.Signal()

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        self.error_code = self._create_errorcode()
        self._set_constants()

        # the library can communicate with 8 devices:
        self.connected_to_device = False

        # Load the timeharp library file th260lib64.dll from the folder
        self._dll = ctypes.cdll.LoadLibrary(self._dll_name)

        # locking for thread safety
        self.threadlock = Mutex()
        self.meas_run = False

    def on_activate(self):
        """ Activate and establish the connection to Timeharp and initialize.
        """
        self.open_connection()
        self.initialize(self._mode)

        self._photon_source2 = None  # for compatibility reasons with second APD
        self.exposure_time = 0.1     # default value of the scanner
        self._lencode = self.MAXLENCODE        # histogram length code. set to maximum value

        self.set_input_channel_enable(self._count_channel, 1)  # counting channel activated
        self.set_input_CFD(self._count_channel, self._input_CFD_discriminator, self._input_CFD_zero_cross)
        self.set_input_channel_offset(self._count_channel, self._input_channel_offset)

        self.set_sync_CFD(self._sync_CFD_discriminator, self._sync_CFD_zero_cross)
        self.set_sync_div(self._sync_div)
        self.set_sync_channel_offset(self._sync_channel_offset)

        # On activation, set binning is set to the default value : 21
        # which is the worst resolution (52us), adapted for slow counting and scans (no timing goal)
        # We change this value for fast counting measurements in the configure for fast counting
        # in case of a come back to slow counting, we put back 21

        self.set_binning(21)
        self._slow_or_fast='slow'
        self._base_resolution_s = self._PS_TO_S*self.get_base_resolution()
        self.set_hist_len(self._lencode)

        self.sigStart.connect(self.start_measure)
        self.result = []
        self._data_trace = None

        self._fast_bin_width_s = None
        self._fast_record_length_s = None
        self._fast_number_of_gates = None


    def on_deactivate(self):
        """ Deactivates and disconnects the device.
        """

        self.close_connection()

    def _create_errorcode(self):
        """ Create a dictionary with the errorcode for the device.

        @return dict: errorcode in a dictionary

        The errorcode is extracted of TH260Lib64  Ver. 3.0. The
        errorcode can be also extracted by calling the get_error_string method
        with the appropriate integer value.
        """

        maindir = get_main_dir()

        filename = os.path.join(maindir, 'hardware', 'picoquant', 'errorcodesTH.h')
        try:
            with open(filename) as f:
                content = f.readlines()
        except:
            self.log.error('No file "errorcodesTH.h" could be found in the '
                           'Picoquant hardware directory!')

        errorcode = {}
        for line in content:
            if '#define ERROR' in line:
                errorstring, errorvalue = line.split()[-2:]
                errorcode[int(errorvalue)] = errorstring

        return errorcode

    def _set_constants(self):
        """ Set the constants (max and min values) for the Timeharp260 device.

        These setting are taken from thdefin.h
        You can find it at the official PicoQuant repo :
        https://github.com/PicoQuant/TH260-Demos/blob/master/Windows/th260defin.h
        """

        self.MODE_HIST = 0
        self.MODE_T2 = 2
        self.MODE_T3 = 3

        self.TDCODEMIN = 0
        self.TDCODEMAX = 7

        # in mV:
        self.ZCMIN = -40
        self.ZCMAX = 0
        self.DISCRMIN = -1200
        self.DISCRMAX = 0
        # self.PHR800LVMIN = -1600
        # self.PHR800LVMAX = 2400

        # in ps:
        self.OFFSETMIN = 0
        self.OFFSETMAX = 2000000
        self.SYNCOFFSMIN = -99999
        self.SYNCOFFSMAX	= 99999

        # in ms:
        self.ACQTMIN = 1
        self.ACQTMAX = 36000000
        self.TIMEOUT = 80               # the maximal device timeout for a readout request

        # in ns:
        self.HOLDOFFMAX = 25500

        self.BINSTEPSMAX = 22
        self.HISTCHAN = 32768	        # number of histogram channels 2^16
        self.TTREADMAX = 131072         # 128K event records (2^17)

        self.MAXLENCODE = 5
        self.STOPCNTMIN = 1
        self.STOPCNTMAX = 4294967295
        self.TRIGOUTMIN = 0             #for TH260_SetTriggerOutput, 0=off
        self.TRIGOUTMAX = 16777215      #in unit of 100ns

    def check(self, func_val):
        """ Check routine for the received error codes.

        @param int func_val : return error code of the called function.

        @return int: pass the error code further so that other functions have
                     the possibility to use it.

        Each called function in the dll has an 32-bit return integer, which
        indicates, whether the function was called and finished successfully
        (then func_val = 0) or if any error has occured (func_val < 0). The
        errorcode, which corresponds to the return value can be looked up in
        the file 'errorcodesTH.h'.
        """

        if not func_val == 0:
            self.log.error('Error in TimeHarp with errorcode {0}:\n'
                        '{1}'.format(func_val, self.error_code[func_val]))
        return func_val

    """
    # =========================================================================
    # These two function below can be accessed without connection to device.
    # =========================================================================
    """

    def get_version(self):
        """ Get the software/library version of the device.

        @return string: string representation of the
                        Version number of the current library
        """
        buf = ctypes.create_string_buffer(16)   # at least 8 byte
        self.check(self._dll.TH260_GetLibraryVersion(ctypes.byref(buf)))
        return buf.value  # .decode() converts byte to string

    def get_error_string(self, errcode):
        """ Get the string error code from the Timeharp Device.

        @param int errcode: errorcode from 0 and below.

        @return byte: byte representation of the string error code.

        The stringcode for the error is the same as it is extracted from the
        errorcodes.h header file. Note that errcode should have the value 0
        or lower, since interger bigger 0 are not defined as error.
        """

        buf = ctypes.create_string_buffer(80)   # at least 40 byte
        self.check(self._dll.TH260_GetErrorString(ctypes.byref(buf), errcode))
        return buf.value.decode() # .decode() converts byte to string

    """
    # =========================================================================
    # Establish the connection and initialize the device or disconnect it.
    # =========================================================================
    """

    def open_connection(self):
        """ Open a connection to this device.
        """

        buffer = ctypes.create_string_buffer(16)   # at least 8 byte
        returned = self.check(self._dll.TH260_OpenDevice(self._deviceID, ctypes.byref(buffer)))
        self._serial = buffer.value.decode()   # .decode() converts byte to string
        if returned >= 0:
            self.connected_to_device = True
            self.log.info('Connection to the TimeHarp 260 established')

    def initialize(self, mode):
        """ Initialize the device with one of the three possible modes.

        @param int mode:    0: histogramming
                            2: T2
                            3: T3
        """
        mode = int(mode)    # for safety reasons, convert to integer
        self._mode = mode

        if not ((mode != self.MODE_HIST) or (mode != self.MODE_T2) or
                (mode != self.MODE_T3)):
            self.log.error('Timeharp: Mode for the device could not be set. '
                           'It must be {0}=Histogram-Mode, {1}=T2-Mode or '
                           '{2}=T3-Mode, but a parameter {3} was '
                           'passed.'.format(
                            self.MODE_HIST,
                            self.MODE_T2,
                            self.MODE_T3,
                            mode))
        else:
            self.check(self._dll.TH260_Initialize(self._deviceID, mode))

    def close_connection(self):
        """ Close the connection to the device.
        """
        self.connected_to_device = False
        self.check(self._dll.TH260_CloseDevice(self._deviceID))
        self.log.info('Connection to the TimeHarp 260 closed.')

    """
    # =========================================================================
    # All functions below can be used if the device was successfully called.
    # =========================================================================
    """
    def get_hardware_info(self):
        """ Retrieve the device hardware information.

        @return string tuple(3): (Model, Partnum, Version)
        """

        model = ctypes.create_string_buffer(32)     # at least 16 byte
        version = ctypes.create_string_buffer(16)   # at least 8 byte
        part_number = ctypes.create_string_buffer(16)   # at least 8 byte
        self.check(self._dll.TH260_GetHardwareInfo(self._deviceID, ctypes.byref(model),
                                                   ctypes.byref(part_number), ctypes.byref(version)))

        # the .decode() function converts byte objects to string objects
        return model.value.decode(), part_number.value.decode(), version.value.decode()

    def get_serial_number(self):
        """ Retrieve the serial number of the device.

        @return string: serial number of the device
        """

        serialnum = ctypes.create_string_buffer(16)   # at least 8 byte
        self.check(self._dll.TH260_GetSerialNumber(self._deviceID, ctypes.byref(serialnum)))
        return serialnum.value.decode()  # .decode() converts byte to string

    def get_features(self):
        """ Retrieve the possible features of the device.

        @return int: a bit pattern indicating the feature.
        """
        features = ctypes.c_int32()
        self.check(self._dll.TH260_GetFeatures(self._deviceID, ctypes.byref(features)))
        return features.value

    def get_base_resolution(self):
        """ Retrieve the base resolution of the device.

        @return double: the base resolution of the device
        """

        resolution = ctypes.c_double()
        bin_steps = ctypes.c_int()
        self.check(self._dll.TH260_GetBaseResolution(self._deviceID, ctypes.byref(resolution), ctypes.byref(bin_steps)))
        return resolution.value

    def get_number_of_input_channels(self):
        """ Retrieve the number of input channels

        @return int: the number of input channels
        """
        number_of_channels = ctypes.c_int()
        self.check(self._dll.TH260_GetNumOfInputChannels(self._deviceID, ctypes.byref(number_of_channels)))
        return number_of_channels.value

    def set_timing_mode(self, timing_mode):
        """ Should be for TH260 P only
        FIX ME : this function doesn't work
        """
        timing_mode = int(timing_mode)    # for safety reasons, convert to integer
        if timing_mode not in (0, 1):
            self.log.error('TimeHarp: Timing_mode does not exist.\nTiming_mode has '
                           'to be 0 to 1 but {0} was passed.'.format(timing_mode))
            return

        self.check(self._dll.TH260_SetTimingMode(self._deviceID, timing_mode))

    def set_sync_div(self, div):
        """ Synchronize the divider of the device.

        @param int div: input rate divider applied at channel 0 (1,2,4, or 8)
        """
        if not ((div != 1) or (div != 2) or (div != 4) or (div != 8)):
            self.log.error('TimeHarp: Invalid sync divider.\n'
                           'Value must be 1, 2, 4 or 8 but a value of {0} was '
                           'passed.'.format(div))
            return
        else:
            self.check(self._dll.TH260_SetSyncDiv(self._deviceID, div))

    def set_sync_CFD(self, level, zero_cross):
        """ Set the Constant Fraction Discriminators (CFD).

        @param int level: CFD discriminator level in millivolts
        @param int zero_cross: CFD zero cross in millivolts
        """

        level = int(level)
        zero_cross = int(zero_cross)

        if not (self.DISCRMIN <= level <= self.DISCRMAX):
            self.log.error('TimeHarp: Invalid CFD level.\nValue must be '
                           'within the range [{0},{1}] millivolts but a value of '
                           '{2} has been '
                           'passed.'.format(self.DISCRMIN, self.DISCRMAX, level))
            return
        if not (self.ZCMIN <= zero_cross <= self.ZCMAX):
            self.log.error('TimeHarp: Invalid CFD zero cross.\nValue must be '
                           'within the range [{0},{1}] millivolts but a value of '
                           '{2} has been '
                           'passed.'.format(self.ZCMIN, self.ZCMAX, zero_cross))
            return

        self.check(self._dll.TH260_SetSyncCFD(self._deviceID, level, zero_cross))

    def set_sync_channel_offset(self, offset):
        """ Set the offset of the synchronization.

        @param int offset: offset (time shift) in ps for that channel. That
                           value must lie within the range of SYNCOFFSMIN and
                           SYNCOFFSMAX.
        """
        offset = int(offset)
        if not (self.SYNCOFFSMIN <= offset <= self.SYNCOFFSMAX):
            self.log.error('TimeHarp: Invalid Synchronization offset.\nValue '
                           'must be within the range [{0},{1}] ps but a value of '
                           '{2} has been passed.'.format(
                            self.SYNCOFFSMIN, self.SYNCOFFSMAX, offset))
        else:
            self.check(self._dll.TH260_SetSyncChannelOffset(self._deviceID, offset))

    def set_input_CFD(self, channel, level, zero_cross):
        """ Set the Constant Fraction Discriminators for the Timeharp.

        @param int channel: id (0 or 1) of the input channel
        @param int level: CFD discriminator level in millivolts
        @param int zero_cross: CFD zero cross in millivolts
        """
        channel = int(channel)
        level = int(level)
        zero_cross = int(zero_cross)
        if channel not in (0, 1):
            self.log.error('TimeHarp: Channel does not exist.\nChannel has '
                           'to be 0 to 1 but {0} was passed.'.format(channel))
            return
        if not (self.DISCRMIN <= level <= self.DISCRMAX):
            self.log.error('TimeHarp: Invalid CFD level.\nValue must be '
                           'within the range [{0},{1}] millivolts but a value of '
                           '{2} has been '
                           'passed.'.format(self.DISCRMIN, self.DISCRMAX, level))
            return
        if not (self.ZCMIN <= zero_cross <= self.ZCMAX):
            self.log.error('TimeHarp: Invalid CFD zero cross.\nValue must be '
                           'within the range [{0},{1}] millivolts but a value of '
                           '{2} has been '
                           'passed.'.format(self.ZCMIN, self.ZCMAX, zero_cross))
            return

        self.check(self._dll.TH260_SetInputCFD(self._deviceID, channel, level, zero_cross))

    def set_input_channel_offset(self, channel, offset):
        """ Set an offset time.

        @param int channel : id (0 or 1) of the input channel
        @param int offset: offset in ps (only possible for histogramming and T3
                           mode!). Value must be within [OFFSETMIN,OFFSETMAX].
        """

        channel = int(channel)
        if channel not in (0, 1):
            self.log.error('TimeHarp: Channel does not exist.\nChannel has '
                           'to be 0 to 1 but {0} was passed.'.format(channel))
            return

        if not (self.OFFSETMIN <= offset <= self.OFFSETMAX):
            self.log.error('TimeHarp: Invalid offset.\nValue must be within '
                           'the range [{0},{1}] ps, but a value of {2} has been '
                           'passed.'.format(self.OFFSETMIN, self.OFFSETMAX, offset))
        else:
            self.check(self._dll.TH260_SetInputChannelOffset(self._deviceID, channel, offset))

    def set_input_channel_enable(self, channel, enable):
        """ Enable or disable the corresponding input channel

        @param int channel:  id (0 or 1) of the input channel
        @param int enable: desired enable state of the input channel (0=disabled, 1=enabled)
        @return int : =0 success,  <0 error
        """
        channel = int(channel)
        enable = int(enable)
        channel_max = self.get_number_of_input_channels()

        if not (0 <= channel <= channel_max):
            self.log.error('TimeHarp.set_input_channel_enable: Channel does not exist.\nChannel has '
                           'to be 0 to 1 but {0} was passed.'.format(channel))
            return

        if enable not in (0, 1):
            self.log.error('TimeHarp.set_input_channel_enable: Enable does not exist.\nEnable has '
                           'to be 0 to 1 but {0} was passed.'.format(enable))
            return

        self.check(self._dll.TH260_SetInputChannelEnable(self._deviceID, channel, enable))

    def set_input_dead_time(self, channel, tdcode):
        """ Set the input dead time

        @param int channel:  id (0 or 1) of the input channel
        @param int tdcode: for the desired dead_time of the input channel. Check dll documentation for details.

        This function has not been tested
        """

        channel = int(channel)
        tdcode = int(tdcode)
        channel_max = self.get_number_of_input_channels()

        if not (0 <= channel <= channel_max):
            self.log.error('TimeHarp.set_input_channel_enable: Channel does not exist.\nChannel has '
                           'to be 0 to 1 but {0} was passed.'.format(channel))
            return

        if not (self.TDCODEMIN <= tdcode <= self.TDCODEMAX):
            self.log.error('TimeHarp.set_input_dead_time: tdcode does not exist.\ntdcode has '
                           'to be 0 to 7 but {0} was passed.'.format(tdcode))
            return

        self.check(self._dll.TH260_SetInputDeadTime(self._deviceID, channel, tdcode))

    def set_binning(self, binning):
        """ Set the base resolution of the measurement.

        @param int binning: binning code
                                minimum = 0 (smallest, i.e. base resolution)
                                maximum = (BINSTEPSMAX-1) (largest)

        The binning code corresponds to a power of 2, i.e.
            0 = base resolution,        => 4*2^0 =    4ps
            1 =   2x base resolution,     => 4*2^1 =    8ps
            2 =   4x base resolution,     => 4*2^2 =   16ps
            3 =   8x base resolution      => 4*2^3 =   32ps
            4 =  16x base resolution      => 4*2^4 =   64ps
            5 =  32x base resolution      => 4*2^5 =  128ps
            6 =  64x base resolution      => 4*2^6 =  256ps
            7 = 128x base resolution      => 4*2^7 =  512ps

        These are all the possible values. In histogram mode the internal
        buffer can store 65535 points (each a 32bit word). For largest
        resolution you can count  33.55392 ms in total
        """

        if not(0 <= binning < self.BINSTEPSMAX):
            self.log.error('TimeHarp: Invalid binning.\nValue must be within '
                           'the range [{0},{1}] bins, but a value of {2} has been '
                           'passed.'.format(0, self.BINSTEPSMAX, binning))
        else:
            self.check(self._dll.TH260_SetBinning(self._deviceID, binning))

    def set_offset(self, offset):
        """ Set an offset time.

        @param int offset: offset in ps (only possible for histogramming and T3
                           mode!). Value must be within [OFFSETMIN,OFFSETMAX].
        """
        if not(self.OFFSETMIN <= offset <= self.OFFSETMAX):
            self.log.error('TimeHarp260.set_offset: Invalid offset.\nValue must be within '
                           'the range [{0},{1}] ps, but a value of {2} has been '
                           'passed.'.format(self.OFFSETMIN, self.OFFSETMAX, offset))
        else:
            self.check(self._dll.TH260_SetOffset(self._deviceID, offset))

    def set_hist_len(self, lencode):
        """ Set the histogram length

        @param int lencode : histogram length code (between 0 and MAXLENCODE)
        @return int : returns the current length (time bin count) of histograms
                    calculated according to actual_length=1024*(2^lencode)
        """

        actual_length = ctypes.c_int()
        if not (0 <= lencode <= self.MAXLENCODE):
            self.log.error('TimeHarp260.set_hist_len: Invalid lencode.\nValue must be within '
                           'the range [{0},{1}], but a value of {2} has been '
                           'passed.'.format(0, self.MAXLENCODE, lencode))
        else:
            self.check(self._dll.TH260_SetHistoLen(self._deviceID, lencode, ctypes.byref(actual_length)))
        return actual_length.value

    def clear_hist_memory(self):
        """ Clear the histogram memory.
        """
        self.check(self._dll.TH260_ClearHistMem(self._deviceID))

    def set_stop_overflow(self, stop_overflow, stop_count):
        """ Set if a measurment will stop or not when reaching stop_count
        *
        @param int stop_overflow : 0 = do not stop, 1 = do stop on overflow
        @param unsigned stop_count : count level at which should be stopped
                (between STOPCOUNTMIN and STOPCOUNTMAX)
        """
        stop_overflow = int(stop_overflow)
        stop_count = int(stop_count)

        if stop_overflow not in (0, 1):
            self.log.error('TimeHarp.set_stop_overflow : stop_overflow does not exist.\nstop_overflow has '
                           'to be 0 to 1 but {0} was passed.'.format(stop_overflow))
            return
        if not (self.STOPCNTMIN <= stop_count <= self.STOPCNTMAX):
            self.log.error('TimeHarp.set_stop_overflow : stop_count does not exist.\nstop_count has '
                           'to be in the range [{0},{1}] but a value of {2} was '
                           'passed.'.format(self.STOPCNTMIN, self.STOPCNTMAX, stop_count))
            return

        self.check(self._dll.TH260_SetStopOverflow(self._deviceID, stop_overflow, stop_count))

    def set_trigger_output(self, period):
        """ Can be used to trigger external light sources

        @param int period : trigger period in unit of 100ns (0=off)

        Use with caution with laser : software can fail...
        """

        if not (self.TRIGOUTMIN <= period < self.TRIGOUTMAX):
            self.log.error('TimeHarp.set_trigger_output period: Invalid binning.\nValue must be within '
                           'the range [{0},{1}] bins, but a value of {2} has been '
                           'passed.'.format(self.TRIGOUTMIN, self.TRIGOUTMAX, period))
        else:
            self.check(self._dll.TH260_SetTriggerOutput(self._deviceID, period))

    def start(self, acq_time):
        """ Start acquisition for 'acq_time' ms.

        @param int acq_time: acquisition time in ms. The value must be
                             be within the range [ACQTMIN,ACQTMAX].
        """
        if not(self.ACQTMIN <= acq_time <= self.ACQTMAX):
            self.log.error('TimeHarp start: No measurement could be started.\n'
                           'The acquisition time must be within the range [{0},{1}] '
                           'ms, but a value of {2} has been passed.'
                           ''.format(self.ACQTMIN, self.ACQTMAX, acq_time))
        else:
            self.check(self._dll.TH260_StartMeas(self._deviceID, int(acq_time)))

    def stop_device(self):
        """ Stop the measurement
        """
        self.check(self._dll.TH260_StopMeas(self._deviceID))
        self.meas_run = False

    def _get_status(self):
        """ Check the status of the device.

        @return int:  = 0: acquisition time still running
                      > 0: acquisition time has ended, measurement finished.
        """
        ctc_status = ctypes.c_int32()
        self.check(self._dll.TH260_CTCStatus(self._deviceID, ctypes.byref(ctc_status)))
        return ctc_status.value

    def get_resolution(self):
        """ Retrieve the current resolution of the TimeHarp.

        @return double: resolution at current binning in ps
        """

        resolution = ctypes.c_double()
        self.check(self._dll.TH260_GetResolution(self._deviceID, ctypes.byref(resolution)))
        return resolution.value

    def get_count_rate(self, channel):
        """ Get the current count rate for the corresponding channel

        @param int channel: which input channel to read (0 or 1):

        @return int: count rate in s^-1
        """
        if not ((channel != 0) or (channel != 1)):
            self.log.error('TimeHarp: Count Rate could not be read out, '
                           'Channel does not exist.\nChannel has to be 0 or 1 '
                           'but {0} was passed.'.format(channel))
            return -1
        else:
            rate = ctypes.c_int32()
            self.check(self._dll.TH260_GetCountRate(self._deviceID, channel, ctypes.byref(rate)))
            return rate.value

    def get_flags(self):
        """ Get the current status flag as a bit pattern.

        @return int: the current status flags (a bit pattern)
        """

        flags = ctypes.c_int32()
        self.check(self._dll.TH260_GetFlags(self._deviceID, ctypes.byref(flags)))
        return flags.value

    def get_elapsed_meas_time(self):
        """ Retrieve the elapsed measurement time in ms.

        @return double: the elapsed measurement time in ms.
        """
        elapsed = ctypes.c_double()
        self.check(self._dll.TH260_GetElapsedMeasTime(self._deviceID, ctypes.byref(elapsed)))
        return elapsed.value

    def get_warnings(self):
        """ Retrieve any warnings about the device or the current measurement.

        @return int: a bitmask for the warnings, as defined in phdefin.h

        You must call get_count_rate for all channel prior to this call
        """

        warnings = ctypes.c_int32()
        self.check(self._dll.TH260_GetWarnings(self._deviceID, ctypes.byref(warnings)))
        return warnings.value

    def get_warnings_text(self, warning_num):
        """ Retrieve the warning text for the corresponding warning bitmask.

        @param int warning_num: the number for which you want to have the
                                warning text.
        @return char[32568]: the actual text of the warning.
        """
        text = ctypes.create_string_buffer(32568)  # buffer at least 16284 byte
        self.check(self._dll.TH260_GetWarningsText(self._deviceID, warning_num, text))
        return text.value

    def get_hardware_debug_info(self):
        """ Retrieve the debug information for the current hardware.

        @return char[32568]: the information for debugging.
        """
        debug_info = ctypes.create_string_buffer(32568)  # buffer at least 16284 byte
        self.check(self._dll.TH260_GetHardwareDebugInfo(self._deviceID, debug_info))
        return debug_info.value

    def get_histogram(self, channel, clear):
        """ Retrieve the histogram data

        @param int channel : input channel index
        @param int clear: denotes the action upon completing the reading process
            0 : keeps the histogram in the acquisition buffer
            1 : clears the acquisition buffer
        @return array of at least actual_length of double words : histogram data

        The histogram buffer size (actual_length) must correspond to the value obtained
        through set_histogram_len()
        """

        actual_length = self.set_hist_len(self._lencode)
        ch_count = np.ones((actual_length,), dtype=np.uint32)

        channel = int(channel)
        channel_max = self.get_number_of_input_channels()

        if not (0 <= channel <= channel_max):
            self.log.error('TimeHarp.set_input_channel_enable: Channel does not exist.\nChannel has '
                           'to be 0 to 1 but {0} was passed.'.format(channel))
            return

        if clear not in (0, 1):
            self.log.error('TimeHarp.get_histogram.\nclear has '
                           'to be 0 to 1 but {0} was passed.'.format(clear))
            return
        self._dll.TH260_GetHistogram.argtypes = [ctypes.c_int32, ctypes.c_int64, ctypes.c_int32, ctypes.c_int32]
        self.check(self._dll.TH260_GetHistogram(self._deviceID, ch_count.ctypes.data, channel, clear))

        return ch_count

    """
    =========================================================================
    #  Special functions for Time-Tagged Time Resolved mode
    =========================================================================
    # ALL 4 FUNCTIONS CONCERNING TTTR HAVE NOT BEEN TESTED
    # THEY ARE COMMENTED
    =========================================================================
    """

    # def tttr_read_fifo(self):  # , num_counts):
    #     """ Read out the buffer of the FIFO.
    #
    #     @param int num counts: number of TTTR records to be fetched. Maximal
    #                            TTREADMAX
    #
    #     @return tuple (buffer, actual_num_counts):
    #                 buffer = data array where the TTTR data are stored.
    #                 actual_num_counts = how many numbers of TTTR could be
    #                                     actually be read out. THIS NUMBER IS
    #                                     NOT CHECKED FOR PERFORMANCE REASONS, SO
    #                                     BE  CAREFUL! Maximum is TTREADMAX.
    #
    #     THIS FUNCTION SHOULD BE CALLED IN A SEPARATE THREAD!
    #
    #     Must not be called with count larger than buffer size permits. CPU time
    #     during wait for completion will be yielded to other processes/threads.
    #     Function will return after a timeout period of 80 ms even if not all
    #     data could be fetched. Return value indicates how many records were
    #     fetched. Buffer must not be accessed until the function returns!
    #
    #      ALL FUNCTIONS CONCERNING TTTR HAVE NOT BEEN TESTED
    #     """
    #     #############
    #     # if type(num_counts) is not int:
    #     #     num_counts = self.TTREADMAX
    #     # elif (num_counts<0) or (num_counts>self.TTREADMAX):
    #     #     self.log.error('TimeHarp : num_counts were expected to within the '
    #     #                 'interval [0,{0}], but a value of {1} was '
    #     #                 'passed'.format(self.TTREADMAX, num_counts))
    #     #     num_counts = self.TTREADMAX
    #
    #     # TimeHarp T3 Format (for analysis and interpretation):
    #     # The bit allocation in the record for the 32bit event is, starting
    #     # from the MSB:
    #     #       channel:     4 bit
    #     #       dtime:      12 bit
    #     #       nsync:      16 bit
    #     # The channel code 15 (all bits ones) marks a special record.
    #     # Special records can be overflows or external markers. To
    #     # differentiate this, dtime must be checked:
    #     #
    #     #     If it is zero, the record marks an overflow.
    #     #     If it is >=1 the individual bits are external markers.
    #     ################
    #
    #     num_counts = self.TTREADMAX
    #     buffer = np.zeros((num_counts,), dtype=np.uint32)
    #     actual_num_counts = ctypes.c_int32()
    #     self._dll.TH260_ReadFiFo.argtypes = [ctypes.c_int32, ctypes.c_int64, ctypes.c_int32, ctypes.c_void_p]
    #     self.check(self._dll.TH260_ReadFiFo(self._deviceID, buffer.ctypes.data, num_counts,
    #                ctypes.byref(actual_num_counts)))
    #
    #     return buffer, actual_num_counts.value
    #
    # def tttr_set_marker_edges(self, me0, me1, me2, me3):
    #     """ Set the marker edges
    #
    #     @param int me<n>:   active edge of marker signal <n>,
    #                             0 = falling
    #                             1 = rising
    #
    #     ALL FUNCTIONS CONCERNING TTTR HAVE NOT BEEN TESTED
    #     """
    #
    #     if (me0 != 0) or (me0 != 1) or (me1 != 0) or (me1 != 1) or \
    #        (me2 != 0) or (me2 != 1) or (me3 != 0) or (me3 != 1):
    #
    #         self.log.error('TimeHarp: All the marker edges must be either 0 '
    #                        'or 1, but the current marker settings were passed:\n'
    #                        'me0={0}, me1={1}, '
    #                        'me2={2}, me3={3},'.format(me0, me1, me2, me3))
    #         return
    #     else:
    #         self.check(self._dll.TH260_TTSetMarkerEdges(self._deviceID, me0, me1,
    #                                                   me2, me3))
    #
    # def tttr_set_marker_enable(self, me0, me1, me2, me3):
    #     """ Set the marker enable or not.
    #
    #     @param int me<n>:   enabling of marker signal <n>,
    #                             0 = disabled
    #                             1 = enabled
    #
    #     ALL FUNCTIONS CONCERNING TTTR HAVE NOT BEEN TESTED
    #     """
    #     if (me0 != 0) or (me0 != 1) or (me1 != 0) or (me1 != 1) or \
    #             (me2 != 0) or (me2 != 1) or (me3 != 0) or (me3 != 1):
    #
    #         self.log.error('TimeHarp: All the marker edges must be either 0 '
    #                        'or 1, but the current marker settings were passed:\n'
    #                        'me0={0}, me1={1}, '
    #                        'me2={2}, me3={3},'.format(me0, me1, me2, me3))
    #         return
    #     else:
    #     self.check(self._dll.TH260_SetMarkerEnable(self._deviceID, me0,
    #                                                    me1, me2, me3))
    #
    # def tttr_set_marker_holdofftime(self, hold_off_time):
    #     """ Set the holdofftime for the markers.
    #
    #     @param int hold_off_time: hold off time in ns. Maximal value is HOLDOFFMAX.
    #
    #
    #     """
    #
    #     if not(0 <= hold_off_time <= self.HOLDOFFMAX):
    #         self.log.error('TimeHarp: Holdofftime could not be set.\n'
    #             'Value of holdofftime must be within the range '
    #             '[0,{0}], but a value of {1} was passed.'
    #             ''.format(self.HOLDOFFMAX, hold_off_time))
    #     else:
    #         self.check(self._dll.TH260_SetMarkerHoldofftime(self._deviceID, hold_off_time))
    #

    # =========================================================================
    #  Higher Level function, which should be called directly from Logic
    # =========================================================================

    # =========================================================================
    #  Functions for the SlowCounter Interface
    # =========================================================================

    def set_up_clock(self, clock_frequency=None, clock_channel=None):
        """ Set here which channel you want to access of the TimeHarp.

        @param float clock_frequency: Sets the frequency of the clock. That frequency will not be taken. It is not
                                      needed, and argument will be omitted.
        @param string clock_channel: This is the physical channel of the clock. It is not needed, and
                                     argument will be omitted.

        @return int: error code (0:OK, -1:error)
        """

        if clock_frequency != 0:
            self.exposure_time = 1 / clock_frequency
        else:
            self.exposure_time = 0.1

        return 0

    def set_up_counter(self, counter_channels=0, sources=None, clock_channel=None):
        """ Set the card into slow counting mode

        @param string counter_channels : Set the actual channel which you want to
                                       read out. Default it is 0. It can
                                       also be 1.
        @param string sources : is not needed, arg will be omitted.
        @param string clock_channel: is not needed, arg will be omitted.

        @return int: error code (0:OK, -1:error)
        """

        self.set_binning(21)
        self._count_channel = counter_channels

        # FIXME: make the counter channel choosable in config
        # FIXME: add second photon source either to config or in a better way to file
        return 0

    def get_counter_channels(self):
        """ Return one counter channel
        """
        return ['Ctr0']

    def get_constraints(self):
        """ Get hardware limits

        @return SlowCounterConstraints: constraints class for slow counter

        FIXME: ask hardware for limits when module is loaded
        """
        constraints = SlowCounterConstraints()
        constraints.max_detectors = 1
        constraints.min_count_frequency = 1e-3
        constraints.max_count_frequency = 10e9
        constraints.counting_mode = [CountingMode.CONTINUOUS]
        return constraints

    def get_count_rate_dll(self):
        """ Returns the current counts per second of the counter.

        @return float: the photon counts per second

        first counting method (worst) : we use get_count_rate
        not a good dynamic, and exp time is fixed to 100ms
        """

        time.sleep(0.1)
        count_rate = np.zeros((1, 1))

        count_rate[0, 0] = self.get_count_rate(self._count_channel)
        return count_rate

    def get_counter_hist(self):
        """ Returns the current counts per second of the counter.

        @return float: the photon counts per second

        second counting method :taking acquisition time=1/freq
        and summing get_histogram acquired on this acquisition time
        """

        count_rate = np.zeros((1, 1))

        self.start(int(self.exposure_time * 1000))
        ctc_status = 0
        while ctc_status != 1:
            ctc_status = self._get_status()
        self.check(self._dll.TH260_StopMeas(self._deviceID))
        self.meas_run = False

        count_rate[0, 0] = self.get_histogram(self._count_channel, 1).sum()/self.exposure_time
        return count_rate

    def get_counter(self, samples=None):
        """ Returns the current counts per second of the counter.

        @param int samples: if defined, number of samples to read in one go

        @return float: the photon counts per second (second and best method for count rate !)
        """
        if self.meas_run==True and self._slow_or_fast == 'fast':
            return np.zeros((1, 1))-1

        elif self.meas_run == False and self._slow_or_fast == 'fast':
            # No acquisition running but coming from a fast configuration
            self.set_up_counter(self._count_channel)
            self._slow_or_fast = 'slow'
            self.meas_run = True
            return self.get_counter_hist()

        elif self.meas_run == False and self._slow_or_fast == 'slow':
            self.meas_run = True
            return self.get_counter_hist()

        else:
            return self.get_counter_hist()

    def close_counter(self):
        """ Closes the counter and cleans up afterwards. Actually, you do not
        have to do anything with the TimeHarp. Therefore this command will do
        nothing and is only here for SlowCounterInterface compatibility.

        @return int: error code (0:OK, -1:error)
        """
        self.meas_run == False
        return 0

    def close_clock(self):
        """ Closes the clock and cleans up afterwards.. Actually, you do not
        have to do anything with the TimeHarp. Therefore this command will do
        nothing and is only here for SlowCounterInterface compatibility.

        @return int: error code (0:OK, -1:error)
        """
        return 0

    """
    # =========================================================================
    #  Functions for the FastCounter Interface
    # =========================================================================
    """

    # FIXME: The interface connection to the fast counter must be established!

    def configure(self, fast_bin_width_s, record_length_s, number_of_gates=0):
        """ Configuration of the fast counter.

        @params int bin_width_ns: Length of a single time bin in the time trace histogram
                      in nanoseconds.
        @params int record_length_ns: Total length of the time trace/each single gate in
                          nanoseconds.
        @params int number_of_gates: Number of gates in the pulse sequence. Ignore for
                         ungated counter.
        @return int tuple (3) (bin width (sec), record length (sec), number of gates)
        """

        # On activation, set binning is set to the default value : 21
        # which is the worst resolution (52us), adapted for slow counting and scans (no timing goal)
        # We change this value for fast counting measurements in the configure for fast counting.
        # THIS IS WHAT WE DO HERE
        # in case of a come back to slow counting, we have to put back 21 through set_up_counter()

        self._fast_bin_width_s = fast_bin_width_s
        self._fast_record_length_s = self.HISTCHAN * self._fast_bin_width_s
        self._fast_number_of_gates = number_of_gates
        self._data_trace = np.zeros(self.HISTCHAN)

        if not self.meas_run:
            self._slow_or_fast = 'fast'
            bin_code = int(np.log2(fast_bin_width_s / self._base_resolution_s))
            self.set_binning(bin_code)

        return self._fast_bin_width_s, self._fast_record_length_s, self._fast_number_of_gates

    def get_constraints_FastCounterInterface(self):
        """ Retrieve the hardware constrains of the Fast counting device
        for the fast_counter_interface.

        @return dict: dict with keys being the constraint names as string and
                      items are the definition for the constaints.
        """
        constraints = dict()
        # the unit of those entries are seconds per bin. In order to get the
        # current bin_width in seconds use the get_bin_width method.
        n_powers = 21
        bin_list = []
        for i in range(n_powers):
            bin_list.append(25*self._PS_TO_S * 2 ** i)

        constraints['hardware_binwidth_list'] = bin_list
        return constraints

    def get_status(self):
        """ Receives the current status of the Fast Counter and outputs it as
        return value.
        0 = not configured
        1 = idle
        2 = running
        3 = paused
        -1 = error state
        """
        if not self.connected_to_device:
            return -1
        if self.meas_run:
            return 2
        if self._fast_bin_width_s is None:
            return 0
        return 1

    def pause_measure(self):
        """ Pauses the current measurement if the fast counter is in running state.
        """

        self.stop_measure()
        self.meas_run = False

    def continue_measure(self):
        """ Continues the current measurement if the fast counter is in pause state.
        """
        if self._slow_or_fast != 'fast':
            self.configure(self._fast_bin_width_s, self._fast_record_length_s, self._fast_number_of_gates)

        self.meas_run = True
        self.start(self.ACQTMAX)

    def is_gated(self):
        """ Boolean return value indicates if the fast counter is a gated counter
        (TRUE) or not (FALSE).
        """
        return False

    def get_binwidth(self):
        """ Returns the width of a single time bin in the time trace in seconds
        """
        return self._fast_bin_width_s

    def get_data_trace(self, channel=0):
        """ Polls the current time_trace data from the fast counter and returns it
        as a numpy array (dtype = int64). The binning specified by calling
        configure() must be taken care of in this hardware class. A possible
        overflow of the histogram bins must be caught here and taken care of.
          - If the counter is NOT gated it will return a 1D-numpy-array with
            return array[time_bin_index].
          - If the counter is gated it will return a 2D-numpy-array with
            return array[gate_index, time_bin_index]
        """

        if self._slow_or_fast == 'fast':
            return self.get_histogram(self._count_channel, 0)
        else:
            return

    """
    # =========================================================================
    #  Test routine for continuous readout
    # =========================================================================
    """

    def start_measure(self):
        """ Starts the fast counter.

        @return int: error code (0:OK, -1:error)
        """
        if self.meas_run and self._slow_or_fast == 'slow':
            return -1

        elif not self.meas_run and self._slow_or_fast == 'slow':
            self.configure(self._fast_bin_width_s, self._fast_record_length_s, self._fast_number_of_gates)
            self.meas_run = True
            self.clear_hist_memory()
            self.start(self.ACQTMAX)
            return 0

        else:
            self.meas_run = True
            self.clear_hist_memory()
            self.start(self.ACQTMAX)
            return 0

    def stop_measure(self):
        """ By setting the Flag, the measurement should stop.
        """
        if self._slow_or_fast == 'slow':
            return

        else:
            self.meas_run = False
            self.stop_device()
