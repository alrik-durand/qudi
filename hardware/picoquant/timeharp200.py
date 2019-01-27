# -*- coding: utf-8 -*-
"""
This file contains the Qudi hardware module for the TimeHarp 200.

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

import os
import ctypes
import numpy as np
import time
from qtpy import QtCore

from core.module import Base, ConfigOption
from core.util.modules import get_main_dir
from core.util.mutex import Mutex
from interface.slow_counter_interface import SlowCounterInterface
from interface.slow_counter_interface import SlowCounterConstraints
from interface.slow_counter_interface import CountingMode
from interface.simple_data_interface import SimpleDataInterface


# =============================================================================
# Wrapper around the THLib.DLL.
# This module is inspired from the picoharp300 module.
# It uses the functions from the TimeHarp200 DLL manual. The error codes are the same as the PicoHarp300.
# For more information, please read the documentation that PicoQuant is not publishing online.
# =============================================================================
"""
The TimeHarp programming library THLib.DLL is written in C and its data types
correspond to standard C/C++ data types as follows:

    char                    8 bit, byte (or characters in ASCII)
    short int               16 bit signed integer
    unsigned short int      16 bit unsigned integer
    int                     32 bit signed integer
    long int                32 bit signed integer
    unsigned int            32 bit unsigned integer
    unsigned long int       32 bit unsigned integer
    float                   32 bit floating point number
    double                  64 bit floating point number
"""

# Bitmask in hex.
# the comments behind each bitmask contain the integer value for the bitmask.
# You can check that by typing 'int(0x0001)' into the console to get the int.

#FEATURE_DLL     = 0x0001    #
#FEATURE_TTTR    = 0x0002    # 2
#FEATURE_MARKERS = 0x0004    # 4
#FEATURE_LOWRES  = 0x0008    # 8
#FEATURE_TRIGOUT = 0x0010    # 16
#
#FLAG_FIFOFULL   = 0x0003  # T-modes             # 3
#FLAG_OVERFLOW   = 0x0040  # Histomode           # 64
#FLAG_SYSERROR   = 0x0100  # Hardware problem    # 256

# The following are bitmasks for return values from GetWarnings()
#WARNING_INP0_RATE_ZERO         = 0x0001    # 1
#WARNING_INP0_RATE_TOO_LOW      = 0x0002    # 2
#WARNING_INP0_RATE_TOO_HIGH     = 0x0004    # 4
#
#WARNING_INP1_RATE_ZERO         = 0x0010    # 16
#WARNING_INP1_RATE_TOO_HIGH     = 0x0040    # 64
#
#WARNING_INP_RATE_RATIO         = 0x0100    # 256
#WARNING_DIVIDER_GREATER_ONE    = 0x0200    # 512
#WARNING_TIME_SPAN_TOO_SMALL    = 0x0400    # 1024
#WARNING_OFFSET_UNNECESSARY     = 0x0800    # 2048


class TimeHarp200(Base, SlowCounterInterface, SimpleDataInterface):
    """ Hardware class to control the TimeHarp 200 from PicoQuant.

    This class is written according to the Programming Library Version 6.1
    Tested Version: Alrik D.

    Example config for copy-paste:

    fastcounter_timeharp200:
        module.Class: 'picoquant.picoharp300.PicoHarp300'
        sync_level: 150
        range: 5
        CFD_level: 10
        CFD_zero: 5
        offset: 0   
    """
    _modclass = 'TimeHarp200'
    _modtype = 'hardware'

    _sync_level = ConfigOption('sync_level')
    _range = ConfigOption('range', 5)
    _CFD_level = ConfigOption('CFD_level')
    _CFD_zero = ConfigOption('CFD_zero')
    _offset = ConfigOption('offset', 0)

    sigReadoutTimeharp = QtCore.Signal()
    sigAnalyzeData = QtCore.Signal(object, object)
    sigStart = QtCore.Signal()

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        self.errorcode = self._create_errorcode()
        self._set_constants()

        self.connected_to_device = False


        # Load the picoharp library file thlib64.dll from the folder
        # <Windows>/System32/
        self._dll = ctypes.cdll.LoadLibrary('THLib')

        # Just some default values:
        self._bin_width_ns = 3000
        self._record_length_ns = 100 *1e9

        self._mode = 0

        # locking for thread safety
        self.threadlock = Mutex()

    def on_activate(self):
        """ Activate and establish the connection to TimeHarp and initialize.
        """
        self.initialize(self._mode)
        self.calibrate()

        # Set config
        self.set_sync_level(level=self. _sync_level)
        self.set_range(_range=self._range)
        self.set_input_CFD(level=self._CFD_level, zerocross=self._CFD_zero)
        self.set_offset(offset=self._offset)


        self.sigStart.connect(self.start_measure)
        self.sigReadoutTimeharp.connect(self.get_fresh_data_loop, QtCore.Qt.QueuedConnection) # ,QtCore.Qt.QueuedConnection
        self.sigAnalyzeData.connect(self.analyze_received_data, QtCore.Qt.QueuedConnection)

    def on_deactivate(self):
        """ Deactivates and disconnects the device.
        """

        self.close_connection()
        self.sigStart.disconnect()
        self.sigReadoutTimeharp.disconnect()
        self.sigAnalyzeData.disconnect()

    def _create_errorcode(self):
        """ Create a dictionary with the errorcode for the device.

        @return dict: errorcode in a dictionary

        The errorcode is extracted of PHLib  Ver. 3.0, December 2013. The
        errorcode can be also extracted by calling the get_error_string method
        with the appropriate integer value.
        """

        maindir = get_main_dir()

        filename = os.path.join(maindir, 'hardware', 'PicoQuant', 'errorcodes.h')
        try:
            with open(filename) as f:
                content = f.readlines()
        except:
            self.log.error('No file "errorcodes.h" could be found in the '
                        'PicoHarp hardware directory!')

        errorcode = {}
        for line in content:
            if '#define ERROR' in line:
                errorstring, errorvalue = line.split()[-2:]
                errorcode[int(errorvalue)] = errorstring

        return errorcode

    def _set_constants(self):
        """ Set the constants (max and min values) for the TimeHarp200 device. """

        self.MODE_HIST = 0
        self.MODE_TTTR = 1

        self.RANGES = 6

        # in mV:
        self.ZCMIN = 0
        self.ZCMAX = 40
        self.DISCRMIN = 0
        self.DISCRMAX = 400
        self.SYNCMIN = -1300
        self.SYNCMAX = 400

        # in ns:
        self.OFFSETMIN = 0
        self.OFFSETMAX = 2000

        # in ms:
        self.ACQTMIN = 1
        self.ACQTMAX = 10*60*60*1000
        self.TIMEOUT = 80   # the maximal device timeout for a readout request

        self.BLOCKSIZE = 4096    # number of histogram channels 2^12

    def check(self, func_val):
        """ Check routine for the received error codes.

        @param int func_val: return error code of the called function.

        @return int: pass the error code further so that other functions have
                     the possibility to use it.

        Each called function in the dll has an 32-bit return integer, which
        indicates, whether the function was called and finished successfully
        (then func_val = 0) or if any error has occured (func_val < 0). The
        errorcode, which corresponds to the return value can be looked up in
        the file 'errorcodes.h'.
        """

        if not func_val == 0:
            self.log.error('Error in TimeHarp200 with errorcode {0}:\n'
                        '{1}'.format(func_val, self.errorcode[func_val]))
        return func_val

    # =========================================================================
    # These two function below can be accessed without connection to device.
    # =========================================================================

    def get_version(self):
        """ Get the software/library version of the device.

        @return string: string representation of the
                        Version number of the current library."""
        buf = ctypes.create_string_buffer(16)   # at least 7 byte
        self.check(self._dll.TH_GetLibraryVersion(ctypes.byref(buf)))
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
        self.check(self._dll.TH_GetErrorString(ctypes.byref(buf), errcode))
        return buf.value.decode()  # .decode() converts byte to string

    # =========================================================================
    # Establish the connection and initialize the device or disconnect it.
    # =========================================================================

    def initialize(self, mode):
        """ Initialize the device with one of the two possible modes.

        @param int mode:    0: histogramming
                            1: TTTR
        """
        mode = int(mode)    # for safety reasons, convert to integer

        if mode in [self.MODE_HIST, self.MODE_TTTR]:
            self._mode = mode
            error_code = self.check(self._dll.TH_Initialize(mode))
            if error_code == 0:
                self.connected_to_device = True
                self.log.info('TimeHarp 200 has been initialized')
        else:
            self.log.error('TimeHarp: Mode for the device could not be set. '
                    'It must be {0}=Histogram-Mode, {1}=TTTR-Mode, but a parameter {2} was '
                    'passed.'.format(
                        self.MODE_HIST,
                        self.MODE_TTTR,
                        mode))

    def close_connection(self):
        """ Close the connection to the device.

        """
        self.connected_to_device = False
        self.check(self._dll.TH_Shutdown())
        self.log.info('Connection to the Picoharp 300 closed.')

    # =========================================================================
    # All functions below can be used if the device was successfully called.
    # =========================================================================

    def get_hardware_info(self):
        """ Retrieve the device hardware information.

        @return string: Hardware version
        """
        version = ctypes.create_string_buffer(16)   # at least 7 byte
        self.check(self._dll.TH_GetHardwareVersion(ctypes.byref(version)))

        return version.value.decode()  # .decode() converts byte to string

    def get_serial_number(self):
        """ Retrieve the serial number of the device.

        @return string: serial number of the device
        """

        serialnum = ctypes.create_string_buffer(16)   # at least 7 byte
        self.check(self._dll.TH_GetSerialNumber(ctypes.byref(serialnum)))
        return serialnum.value.decode()  # .decode() converts byte to string

    def get_base_resolution(self):
        """ Retrieve the base resolution of the device.

        @return int: the base resolution of the device in some format (TODO)
        """

        resolution = self._dll.TH_GetBaseResolution()
        if resolution > 0:
            return resolution
        else:
            self.check(resolution)
            return resolution

    def calibrate(self):
        """ Calibrate the device."""
        self.check(self._dll.TH_Calibrate())

    def set_input_CFD(self, level, zerocross):
        """ Set the Constant Fraction Discriminators for the TimeHarm200.

        @param int level: CFD discriminator level in millivolts
        @param int zerocross: CFD zero cross in millivolts
        """
        level = int(level)
        zerocross = int(zerocross)
        if not(self.DISCRMIN <= level <= self.DISCRMAX):
            self.log.error('TimeHarp: Invalid CFD level.\nValue must be '
                        'within the range [{0},{1}] millivolts but a value of '
                        '{2} has been '
                        'passed.'.format(self.DISCRMIN, self.DISCRMAX, level))
            return
        if not(self.ZCMIN <= zerocross <= self.ZCMAX):
            self.log.error('TimeHarp: Invalid CFD zero cross.\nValue must be '
                        'within the range [{0},{1}] millivolts but a value of '
                        '{2} has been '
                        'passed.'.format(self.ZCMIN, self.ZCMAX, zerocross))
            return

        self.check(self._dll.TH_SetCFDDiscrMin(level))
        self.check(self._dll.TH_SetCFDZeroCross(level))

    def set_sync_level(self, level):
        """ Set the Sync level in millivolts

        @param int level: Sync level in millivolts
        """
        level = int(level)
        if not(self.SYNCMIN <= level <= self.SYNCMAX):
            self.log.error('TimeHarp: Invalid Sync level.\nValue must be '
                        'within the range [{0},{1}] millivolts but a value of '
                        '{2} has been '
                        'passed.'.format(self.SYNCMIN, self.SYNCMAX, level))
            return
        self.check(self._dll.TH_SetSyncLevel(level))

    def set_range(self, _range):
        """ Set the measurement range code

        @param int _range: measurement range code
            minimum = 0 (smallest, i.e. base resolution)
            maximum = RANGES-1 (largest)

        note: range code 0 = base resolution, 1 = 2 x base resolution and so on.
        """
        _range = int(_range)
        if not(0 <= _range <= self.RANGES-1):
            self.log.error('TimeHarp: Invalid range.\nValue must be '
                        'within the range [{0},{1}] but a value of '
                        '{2} has been '
                        'passed.'.format(0, self.RANGES-1, _range))
            return
        self.check(self._dll.TH_SetRange(_range))

    def set_offset(self, offset):
        """ Set the offset

        @param int offset: offset (time shift) in ns. That
                           value must lie within the range of OFFSETMIN and
                           OFFSETMAX.
        """
        offset = int(offset)
        if not(self.OFFSETMIN <= offset <= self.OFFSETMAX):
            self.log.error('PicoHarp: Invalid offset.\nValue '
                    'must be within the range [{0},{1}] ps but a value of '
                    '{2} has been passed.'.format(
                        self.OFFSETMIN, self.OFFSETMAX, offset))
        else:
            result = self._dll.TH_SetOffset(offset)
            if result >= 0:
                return result
            else:
                self.check(result)

    def next_offset(self, direction):
        """ ??? TODO :OOO

        @param int direction: direction of the desired offset change
                           minimum = -1 (down)
                           maximum = +1 (up)

        note: The offset changes at a step size of approximately 2.5 ns

        TODO: if direction is -1, what does it return ?
        """
        direction = int(direction)
        if not(-1 <= direction <= 1):
            self.log.error('PicoHarp: Invalid next offset direction.\nValue '
                    'must be within the range [{0},{1}] ps but a value of '
                    '{2} has been passed.'.format(
                        -1, +1, direction))
        else:
            result = self._dll.TH_NextOffset(direction)
            if result >= 0:
                return result
            else:
                self.check(result)

    def set_stop_overflow(self, stop_ovfl, stopcount):
        """ Stop the measurement if maximal amount of counts is reached.

        @param int stop_ovfl:  0 = do not stop,
                               1 = do stop on overflow
        @param int stopcount: count level at which should be stopped
                              (maximal 65535).

        This setting determines if a measurement run will stop if any channel
        reaches the maximum set by stopcount.
        """
        if stop_ovfl not in (0, 1):
            self.log.error('Timeharp: Invalid overflow parameter.\n'
                        'The overflow parameter must be either 0 or 1 but a '
                        'value of {0} was passed.'.format(stop_ovfl))
            return

        if not(1 <= stopcount <= self.HISTCHAN):
            self.log.error('PicoHarp: Invalid stopcount parameter.\n'
                        'stopcount must be within the range [1,{0}] but a '
                        'value of {1} was passed.'.format(self.HISTCHAN, stopcount))
            return

        return self.check(self._dll.TH_SetStopOverflow(stop_ovfl, stopcount))

    # def set_binning(self, binning):
    #     """ Set the base resolution of the measurement.
    #
    #     @param int binning: binning code
    #                             minimum = 0 (smallest, i.e. base resolution)
    #                             maximum = (BINSTEPSMAX-1) (largest)
    #
    #     The binning code corresponds to a power of 2, i.e.
    #         0 = base resolution,        => 4*2^0 =    4ps
    #         1 =   2x base resolution,     => 4*2^1 =    8ps
    #         2 =   4x base resolution,     => 4*2^2 =   16ps
    #         3 =   8x base resolution      => 4*2^3 =   32ps
    #         4 =  16x base resolution      => 4*2^4 =   64ps
    #         5 =  32x base resolution      => 4*2^5 =  128ps
    #         6 =  64x base resolution      => 4*2^6 =  256ps
    #         7 = 128x base resolution      => 4*2^7 =  512ps
    #
    #     These are all the possible values. In histogram mode the internal
    #     buffer can store 65535 points (each a 32bit word). For largest
    #     resolution you can count  33.55392 ms in total
    #
    #     """
    #     if not(0 <= binning < self.BINSTEPSMAX):
    #         self.log.error('PicoHarp: Invalid binning.\nValue must be within '
    #                 'the range [{0},{1}] bins, but a value of {2} has been '
    #                 'passed.'.format(0, self.BINSTEPSMAX, binning))
    #     else:
    #         self.check(self._dll.PH_SetBinning(self._deviceID, binning))

    # def set_multistop_enable(self, enable=True):
    #     """ Set whether multistops are possible within a measurement.
    #
    #     @param bool enable: optional, Enable or disable the mutlistops.
    #
    #     This is only for special applications where the multistop feature of
    #     the Picoharp is causing complications in statistical analysis. Usually
    #     it is not required to call this function. By default, multistop is
    #     enabled after PH_Initialize.
    #     """
    #     if enable:
    #         self.check(self._dll.PH_SetMultistopEnable(self._deviceID, 1))
    #     else:
    #         self.check(self._dll.PH_SetMultistopEnable(self._deviceID, 0))

    def clear_hist_memory(self, block=0):
        """ Clear the histogram memory.

        @param int block: set which block number to clear (always 0 if not routing)
        """
        self.check(self._dll.TH_ClearHistMem(block))

    def set_mode(self, mode, tacq):
        """ Set the device modes acquisition time in milliseconds

        @param int mode:    0: histogramming
                            1: TTTR
        @param int tacq:    acquisition time in milliseconds
                            minimum = ACQTMIN
                            maximum = ACQTMAX
                            set this to 0 for continuous mode with external clock

        """
        if self.module_state != 'idle':
            self.log.error('Can not change TimeHarp mode while running.')

        mode = int(mode)  # for safety reasons, convert to integer
        tacq = int(tacq)

        ok = True
        if mode not in [self.MODE_HIST, self.MODE_TTTR]:
            ok = False
            self.log.error('TimeHarp: Mode for the device could not be set. '
                           'It must be {0}=Histogram-Mode, {1}=TTTR-Mode, but a parameter {2} was '
                           'passed.'.format(
                self.MODE_HIST,
                self.MODE_TTTR,
                mode))

        if not (self.ACQTMIN <= tacq <= self.ACQTMAX):
            ok = False
            self.log.error('TimeHarp: Invalid acquisition time.\nValue '
                           'must be within the range [{0},{1}] ms but a value of '
                           '{2} has been passed.'.format(
                self.ACQTMIN, self.ACQTMAX, tacq))
        if ok:
            self._mode = mode
            self.check(self._dll.TH_SetMMode(mode, tacq))

    def start(self):
        """ Start acquisition """
        if self.module_state != 'idle':
            self.log.error('TimeHarp is already running.')
        self.run()
        self.check(self._dll.TH_StartMeas())

    def stop_device(self):
        """ Stop the measurement."""
        if self.module_state != 'running':
            self.log.error('TimeHarp is not running.')
        self.stop()
        self.check(self._dll.TH_StopMeas())
        self.meas_run = False

    def _get_status(self):
        """ Check the status of the device.

        @return int:  = 0: acquisition time still running
                      > 0: acquisition time has ended, measurement finished.
        """
        return self._dll.TH_CTCStatus()

    def set_sync_mode(self):
        """" The the counting for TH_GetCountRate to sync channel

        This function must be called before TH_GetCountRate()
        if the sync rate is to be measured. Allow at least 500ms
        after this call to get a stable sync rate reading."""
        if self.module_state != 'idle':
            self.log.error('Can not change TimeHarp counter source while running.')

        self.check(self._dll.TH_SetSyncMode())

    def get_histogram(self, block=0, xdata=True):
        """ Retrieve the measured histogram.

        @param int block: the block number to fetch (block >0 is only
                          meaningful with routing) (0..3)
        @param bool xdata: if true, the x values in ns corresponding to the
                           read array will be returned.

        @return numpy.array[65536] or  numpy.array[65536], numpy.array[65536]:
                        depending if xdata = True, also the xdata are passed in
                        ns.

        """
        if self.module_state != 'idle':
            self.log.warning('The module is running.')

        chcount = np.zeros((self.BLOCKSIZE,), dtype=np.uint32)
        # buf.ctypes.data is the reference to the array in the memory.
        self.check(self._dll.TH_GetBlock(chcount.ctypes.data, block))
        if xdata:
            xbuf = np.arange(self.BLOCKSIZE) * self.get_resolution()# TODO unit ?  # / 1000
            return xbuf, chcount
        return chcount

    def get_resolution(self):
        """ Retrieve the current resolution of the timeharp.

        @return double: resolution at current binning.
        """
        self._dll.TH_GetResolution.restype = ctypes.c_double
        result = self._dll.TH_GetResolution()
        if result > 0:
            return result
        else:
            self.check(result)
            return result

    def get_count_rate(self):
        """ Get the current count rate or sync rate

        @return int: count rate in TODO

        The function returns either the current count rate if previously
        set_mode() was called or the current sync rate if previously
        set_sync_mode() was called. Allow at least 500ms to get a stable
        rate meter reading in both cases.
        """
        if self.module_state != 'idle':
            self.log.error('Can not measure count rate while running.')

        result = self._dll.TH_GetCountRate()
        if result >= 0:
            return result
        else:
            self.check(result)
            return result

    def get_flags(self):
        """ Get the current status flag as a bit pattern.


        Use the predefined macros in thdefin.h (e.g. FLAG_OVERFLOW)
        to extract individual bits through a bitwise AND.
        You can call this function anytime during measurement but not
        during DMA.
        """

        return self._dll.TH_GetFlags()

    def get_elepased_meas_time(self):
        """ Retrieve the elapsed measurement time in ms.

        Not for continuous mode.

        @return int: the elapsed measurement time in ms.
        """
        return self._dll.TH_GetElapsedMeasTime()

    # =========================================================================
    #  Higher Level function, which should be called directly from Logic
    # =========================================================================

    # =========================================================================
    #  Functions for the SlowCounter Interface
    # =========================================================================

    def set_up_clock(self, clock_frequency=None, clock_channel=None):
        """  Ensure Interface compatibility. The counter allows no set up.

        @return int: error code (0:OK, -1:error)
        """
        return 0

    def set_up_counter(self, counter_channels=None, sources=None,
                       clock_channel=None, counter_buffer=None):
        """ This function is called when the counter is started

        @return int: error code (0:OK, -1:error)
        """
        self.run()
        return 0

    def get_counter_channels(self):
        """ Return one counter channel. """
        return ['Start counter']

    def get_constraints(self):
        """ Get hardware limits of device.

        @return SlowCounterConstraints: constraints class for slow counter

        """

        class CounterConstraints(SlowCounterConstraints):

            def __init__(self):
                super().__init__()
                self.hardware_binwidth_list = []

        constraints = CounterConstraints()
        constraints.max_detectors = 1
        constraints.min_count_frequency = 1e-3
        constraints.max_count_frequency = 20
        constraints.counting_mode = [CountingMode.CONTINUOUS]

        # Fast counter binwidth
        constraints.hardware_binwidth_list = np.power(2, np.arange(0, self.RANGES)) * self.get_base_resolution()

        return constraints

    def get_counter(self, samples=None):
        """ Returns the current counts per second of the counter.

        @param int samples: if defined, number of samples to read in one go

        @return float: the photon counts per second
        """
        if self.module_state != 'running':
            self.log.error('Can not get count if counter is not running')
        time.sleep(0.05)
        return [self.get_count_rate()]

    def close_counter(self):
        """ Ensure Interface compatibility. The counter allows no set up.

        @return int: error code (0:OK, -1:error)
        """
        self.stop()
        return 0

    def close_clock(self):
        """ Ensure Interface compatibility. The counter allows no set up.

        @return int: error code (0:OK, -1:error)
        """
        return 0

    # =========================================================================
    #  Functions for the FastCounter Interface
    # =========================================================================

    # get_constraints is shared with slow counter, this is very dirty...

    def configure(self, bin_width_ns, record_length_ns, number_of_gates=0):
        """
        Configuration of the fast counter.
        bin_width_ns: Length of a single time bin in the time trace histogram
                      in nanoseconds.
        record_length_ns: Total length of the timetrace/each single gate in
                          nanoseconds.
        number_of_gates: Number of gates in the pulse sequence. Ignore for
                         ungated counter.
        """
        # self.set_mode(mode=0)
        self._bin_width_ns = bin_width_ns
        self._record_length_ns = record_length_ns
        self._number_of_gates = number_of_gates

        # FIXME: actualle only an unsigned array will be needed. Change that later.
        #        self.data_trace = np.zeros(number_of_gates, dtype=np.int64 )
        self.data_trace = [0] * number_of_gates
        self.count = 0

        self.result = []
        return

    def get_status(self):
        """
        Receives the current status of the Fast Counter and outputs it as
        return value.
        0 = unconfigured
        1 = idle
        2 = running
        3 = paused
        -1 = error state
        """
        if not self.connected_to_device:
            return -1
        else:
            returnvalue = self._get_status()
            if returnvalue == 0:
                return 2
            else:
                return 1


    # =========================================================================
    #  Test routine for continuous readout
    # =========================================================================


    def start_measure(self):
        """
        Starts the fast counter.
        """
        self.lock()

        self.meas_run = True

        # start the device:
        self.start(int(self._record_length_ns/1e6))

        self.sigReadoutTimeharp.emit()

    def stop_measure(self):
        """ By setting the Flag, the measurement should stop.  """
        self.meas_run = False


    def get_fresh_data_loop(self):
        """ This method will be run infinitely until the measurement stops. """

        # for testing one can also take another array:
        buffer, actual_counts = self.tttr_read_fifo()
#        buffer, actual_counts = [1,2,3,4,5,6,7,8,9], 9

        # This analysis signel should be analyzed in a queued thread:
        self.sigAnalyzeData.emit(buffer[0:actual_counts-1], actual_counts)

        if not self.meas_run:
            with self.threadlock:
                self.unlock()
                self.stop_device
                return

        print('get new data.')
        # get the next data:
        self.sigReadoutTimeharp.emit()

    def analyze_received_data(self, arr_data, actual_counts):
        pass

    # =========================================================================
    #  Simple data interface to access
    # =========================================================================

    def getData(self):
        """ Return a measured value """
        if self.module_state == 'idle':
            return [self.get_count_rate()]

    def getChannels(self):
        """ Return number of channels for value """
        return 1


