# -*- coding: utf-8 -*-
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

from ctypes import c_long, c_ulong, c_buffer, c_float, windll, pointer
from collections import OrderedDict

from core.module import Base
from core.configoption import ConfigOption

from interface.motor_interface import MotorInterface
from interface.switch_interface import SwitchInterface

HARDWARE_TYPES = {'BSC001': 11,  # 1 Ch benchtop stepper driver
                  'BSC101': 12,  # 1 Ch benchtop stepper driver
                  'BSC002': 13,  # 2 Ch benchtop stepper driver
                  'BDC101': 14,  # 1 Ch benchtop DC servo driver
                  'SCC001': 21,  # 1 Ch stepper driver card (used within BSC102,103 units)
                  'DCC001': 22,  # 1 Ch DC servo driver card (used within BDC102,103 units)
                  'ODC001': 24,  # 1 Ch DC servo driver cube
                  'OST001': 25,  # 1 Ch stepper driver cube
                  'MST601': 26,  # 2 Ch modular stepper driver module
                  'TST001': 29,  # 1 Ch Stepper driver T-Cube
                  'TDC001': 31,  # 1 Ch DC servo driver T-Cube
                  'KDC101': 31,  # 1 Ch DC servo driver T-Cube - Newer model
                  'LTSXXX': 42,  # LTS300/LTS150 Long Travel Integrated Driver/Stages
                  'L490MZ': 43,  # L490MZ Integrated Driver/Labjack
                  'BBD10X': 44,  # 1/2/3 Ch benchtop brushless DC servo driver
                  'MFF101': 48  # Flipper mirror
                  }

ERROR_CODES =    {10000: 'An unknown Server error has occurred. ',
                  10001: 'A Server internal error has occurred. ',
                  10002: 'A Server call has failed. ',
                  10003: 'An attempt has been made to pass a parameter that is '
                         'invalid or out of range. In the case of motor '
                         'commands, this error may occur when a move is '
                         'requested that exceeds the stage travel or exceeds '
                         'the calibration data.',
                  10004: 'An attempt has been made to save or load control '
                         'parameters to the registry (using the SaveParamSet '
                         'or LoadParamSet methods) when the unit serial number '
                         'has not been specified.',
                  10005: 'APT DLL not intialised',
                  10050: 'An error has occurred whilst accessing the disk. '
                         'Check that the drive is not full, missing or '
                         'corrupted.',
                  10051: 'An error has occurred with the ethernet connections '
                         'or the windows sockets. ',
                  10052: 'An error has occurred whilst accessing the '
                         'registry. ',
                  10053: 'An internal memory allocation error or '
                         'de-allocation error has occurred.',
                  10054: 'An error has occurred with the COM system. '
                         'Restart the program.',
                  10055: 'An error has occurred with the USB communications.',
                  10100: 'A serial number has been specified that is unknown '
                         'to the server.',
                  10101: 'A duplicate serial number has been detected. '
                         'Serial numbers are required to be unique.',
                  10102: 'A duplicate device identifier has been detected.',
                  10103: 'An invalid message source has been detected.',
                  10104: 'A message has been received with an unknown '
                         'identifier.',
                  10105: 'An unknown hardware identifier has been encountered.',
                  10106: 'An invalid serial number has been detected.',
                  10107: 'An invalid message destination ident has been detected.',
                  10108: 'An invalid index parameter has been passed.',
                  10109: 'A software call has been made to a control which is '
                         'not currently communicating with any hardware. This '
                         'may be because the control has not been started or '
                         'may be due to an incorrect serial number or missing '
                         'hardware. ',
                  10110: 'A notification or response message has been '
                         'received from a hardware unit. This may be indicate '
                         'a hardware fault or that an illegal '
                         'command/parameter has been sent to the hardware.',
                  10111: 'A time out has occurred while waiting for a '
                         'hardware unit to respond. This may be due to '
                         'communications problems or a hardware fault. ',
                  10112: 'Some functions are applicable only to later '
                         'versions of embedded code. This error is returned '
                         'when a software call is made to a unit with an '
                         'incompatible version of embedded code installed.',
                  10115: 'Some functions are applicable only to later versions '
                         'of hardware. This error is returned when a software '
                         'call is made to an incompatible version of hardware.',
                  10150: 'The GetStageAxisInfo method has been called when '
                         'no stage has been assigned. ',
                  10151: 'An internal error has occurred when using an '
                         'encoded stage.',
                  10152: 'An internal error has occurred when using an '
                         'encoded stage. ',
                  10153: 'A software call applicable only to encoded stages '
                         'has been made to a non-encoded stage.'}


STATUS_CODE =     {1: '0x00000001, 1, forward hardware limit switch is active. '
                      'CW hardware limit switch (0 - no contact, 1 - contact).',
                   2: '0x00000002, 2, reverse hardware limit switch is active. '
                      'CCW hardware limit switch (0 - no contact, 1 - contact).',
                   3: '0x00000004, 3, CW software limit switch (0 - no '
                      'contact, 1 - contact). Not applicable to Part Number '
                      'ODC001 and TDC001 controllers', 4: '0x00000008, 4, CCW software limit switch (0 - no '
                                                          'contact, 1 - contact). Not applicable to Part Number '
                                                          'ODC001 and TDC001 controllers',
                   5: '0x00000010, 5, in motion, moving forward, Motor shaft '
                      'moving clockwise (1 - moving, 0 - stationary).',
                   6: '0x00000020, 6, in motion, moving reverse, Motor shaft '
                      'moving counterclockwise (1 - moving, 0 - stationary).',
                   7: '0x00000040, 7, in motion, jogging forward, Shaft '
                      'jogging clockwise (1 - moving, 0 - stationary).',
                   8: '0x00000080, 8, in motion, jogging reverse, Shaft '
                      'jogging counterclockwise (1 - moving, 0 - stationary).',
                   9: '0x00000100, 9, Motor connected (1 - connected, 0 - '
                      'not connected). Not applicable to Part Number BMS001 '
                      'and BMS002 controllers. Not applicable to Part Number '
                      'ODC001 and TDC001 controllers.', 10: '0x00000200, 10, in motion, homing, Motor homing '
                                                            '(1 - homing, 0 - not homing).',
                   11: '0x00000400, 11, homed (homing has been completed)'
                       '(1 - homed, 0 - not homed).', 12: '0x00000800, 12, For Future Use.',
                   13: '0x00001000, 13, Trajectory within tracking window '
                       '(1 – within window, 0 – not within window).',
                   14: '0x00002000, 14, settled, Axis within settled window '
                       '(1 – settled within window, 0 – not settled within'
                       'window).', 15: '0x00004000, 15, motion error (excessive position '
                                       'error), Axis exceeds position error limit '
                                       '(1 – limit exceeded, 0 – within limit).',
                   16: '0x00008000, 16, Set when position module instruction '
                       'error exists (1 – instruction error exists, 0 – '
                       'no error).', 17: '0x00010000, 17, Interlock link missing in motor '
                                         'connector (1 – missing, 0 – present).',
                   18: '0x00020000, 18, Position module over temperature '
                       'warning (1 – over temp, 0 – temp OK).', 19: '0x00040000, 19, Position module bus voltage fault '
                                                                    '(1 – fault exists, 0 – OK).',
                   20: '0x00080000, 20, Axis commutation error '
                       '(1 – error, 0 – OK).', 21: '0x00100000, 21, Digital input 1 state (1 - '
                                                   'logic high, 0 - logic low).',
                   22: '0x00200000, 22, Digital input 2 state (1 - '
                       'logic high, 0 - logic low).', 23: '0x00400000, 23, Digital input 3 state (1 - '
                                                          'logic high, 0 - logic low).',
                   24: '0x00800000, 24, Digital input 4 state (1 - '
                       'logic high, 0 - logic low).', 25: '0x01000000, 25, BBD10x Controllers: Axis phase '
                                                          'current limit (1 – current limit exceeded, '
                                                          '0 – below limit). Other Controllers: Digital input 5 '
                                                          'state (1 - logic high, 0 - logic low).',
                   26: '0x02000000, 26, Digital input 6 state (1 - logic '
                       'high, 0 - logic low).', 27: '0x04000000, 27, Unspecified, for Future Use.',
                   28: '0x08000000, 28, Unspecified, for Future Use.',
                   29: '0x10000000, 29, Unspecified, for Future Use.',
                   30: '0x20000000, 30, Active (1 – indicates unit is active, '
                       '0 – not active).', 31: '0x40000000, 31, Unspecified, for Future Use.',
                   32: '0x80000000, Channel enabled (1 – enabled, 0- disabled).'}


class APTDevice:
    """ General class for APT devices, motor or flipper """
    def __init__(self, dll, serial_number):
        """
        @param (ctypes.WinDLL) dll: a handle to the initialized dll
        @param (int) serial_number: serial number of the stage

        """
        self._dll = dll
        self._serial_number = serial_number
        self.connected = False
        self.initialize_hardware_device()

    def initialize_hardware_device(self):
        """ Initialize the device

        Once initialized, it will not respond to other objects trying to control it, until released.
        """
        result = self._dll.InitHWDevice(self._serial_number)
        if result == 0:
            self.connected = True
        else:
            raise Exception('Connection Failed. Check Serial Number')

    def disable(self):
        """ Disable axis so that other programs can access it """
        self._dll.DisableHWChannel(self._serial_number)
        self.connected = False

    def get_status_bits(self):
        """ Get the status bits

        @return (int): the current status as an integer
        """
        status_bits = c_ulong()
        self._dll.MOT_GetStatusBits(self._serial_number, pointer(status_bits))
        return status_bits.value

    def _test_bit(self, int_val, offset):
        """ Check a bit in an integer number at position offset.

        @param (int) int_val: an integer value, which is checked
        @param (int) offset: the position which should be checked whether in int_val for a bit of 1 is set.

        @return (bool): Check in an integer representation, whether the bit at the position offset is set to 0 or to 1.
                        If bit is set True will be returned else False.
        """
        mask = 1 << offset
        return(int_val & mask) != 0

    def get_hardware_information(self):
        """ Get information from the hardware"""
        model = c_buffer(255)
        software_version = c_buffer(255)
        hardware_notes = c_buffer(255)
        self._dll.GetHWInfo(self._serial_number, model, 255, software_version, 255, hardware_notes, 255)
        return {'model': model.value, 'version': software_version.value, 'notes': hardware_notes.value}


class APTMotor(APTDevice):
    """ Class to control a single Thorlabs APT motor """

    def __init__(self, dll, serial_number):
        super().__init__(dll, serial_number)
        self._wait_until_done = False
        params = self.get_stage_axis_info()
        self._unit = params['unit']
        self._unit_factor = 1 if self._unit == 'degree' else 1000  # convert mm to meter for the dll
        self._pitch = params['pitch']
        velocity_params = self._get_velocity_parameters()
        self._velocity = velocity_params['maximum_velocity']
        self._acceleration = velocity_params['acceleration']

    def get_stage_axis_info(self):
        """ Get parameter configuration of the stage

        @return dict: Dictionary containing the axis informations

        Keys are :
            - (float) minimum_position : Minimum position in m or degree
            - (float) maximum_position : Maximum position in m or degree
            - (str) unit : 'meter' or 'degree'  # unit: 1=m and 2=degree
            - (float) pitch : The angular distance to the next teeth in
                                     the stepper motor. That determines
                                     basically the precision of the movement of
                                     the stepper motor.

        This method will handle the conversion to the non SI unit mm.
        """
        minimum_position = c_float()
        maximum_position = c_float()
        unit = c_long()
        pitch = c_float()
        self._dll.MOT_GetStageAxisInfo(self._serial_number, pointer(minimum_position), pointer(maximum_position),
                                       pointer(unit), pointer(pitch))
        unit_factor = 1 if unit.value == 2 else 1000  # convert mm to meter for the dll
        return {'minimum_position': minimum_position.value / unit_factor,
                'maximum_position': maximum_position.value / unit_factor,
                'unit': 'meter' if unit.value == '1' else 'degree',  # 1 = m, 2 = degree
                'pitch': pitch.value}

    def set_stage_axis_range(self, minimum_position, maximum_position):
        """ Set a new range for the stage.

        @param (float) minimum_position: minimal position of the axis in m or degree.
        @param (float) maximum_position: maximal position of the axis in m or degree.
        """
        minimum_position = c_float(minimum_position * self._unit_factor)
        maximum_position = c_float(maximum_position * self._unit_factor)

        unit = c_long(1) if self._unit == 'meter' else c_long(2)
        pitch = c_float(self._pitch)
        self._dll.MOT_SetStageAxisInfo(self._serial_number, minimum_position, maximum_position, unit, pitch)

    def set_pitch(self, value):
        """ Set the pitch of the axis """
        self._pitch = value
        params = self.get_stage_axis_info()
        self.set_stage_axis_range(params['minimum_position'], params['maximum_position'])  # send pitch to dll

    def get_pitch(self):
        """ Get the current pitch """
        return self._pitch

    def get_hardware_limit_switches(self):
        """ Get limits switches """
        reverse_limit_switch = c_long()
        forward_limit_switch = c_long()
        self._dll.MOT_GetHWLimSwitches(self._serial_number, pointer(reverse_limit_switch),
                                       pointer(forward_limit_switch))
        return [reverse_limit_switch.value, forward_limit_switch.value]

    def set_hardware_limit_switches(self, switch_reverse, switch_forward):
        """ Set the Switch Configuration of the axis.

        @param int switch_reverse: sets the switch in reverse movement
        @param int switch_forward: sets the switch in forward movement

        The following values are allowed:
        0x01 or 1: Ignore switch or switch not present.
        0x02 or 2: Switch makes on contact.
        0x03 or 3: Switch breaks on contact.
        0x04 or 4: Switch makes on contact - only used for homes (e.g. limit switched rotation stages).
        0x05 or 5: Switch breaks on contact - only used for homes (e.g. limit switched rotations stages).
        0x06 or 6: For PMD based brushless servo controllers only - uses index mark for homing.
        """
        reverse_limit_switch = c_long(switch_reverse)
        forward_limit_switch = c_long(switch_forward)
        self._dll.MOT_SetHWLimSwitches(self._serial_number, reverse_limit_switch, forward_limit_switch)

    def _get_velocity_parameters(self):
        """ Retrieve the velocity parameter with the currently used acceleration.

        @return (dict): Dict containing velocity parameters

        - (float) minimum_velocity : minimal velocity in m/s or degree/s - should be 0
        - (float) maximum_velocity : maximal velocity in m/s or degree/s
        - (float) acceleration: currently set acceleration in m/s^2 or degree/s^2
        """
        minimum_velocity = c_float()
        maximum_velocity = c_float()
        acceleration = c_float()
        self._dll.MOT_GetVelParams(self._serial_number, pointer(minimum_velocity), pointer(acceleration),
                                   pointer(maximum_velocity))

        return {'minimum_velocity': minimum_velocity.value / self._unit_factor,
                'maximum_velocity': maximum_velocity.value / self._unit_factor,
                'acceleration': acceleration.value / self._unit_factor}

    def get_velocity(self):
        """ Get the current maximum velocity setting """
        params = self._get_velocity_parameters()
        return params['maximum_velocity']

    def set_velocity_parameters(self, acceleration, maximum_velocity):
        """ Set the velocity and acceleration parameter.

        @param (float) acceleration: the rate at which the velocity climbs from minimum to maximum,
                                     and slows from maximum to minimum current (acceleration in m/s^2 or degree/s^2)
        @param (float) maximum_velocity: the maximum velocity at which to perform a move in m/s or degree/s
        """
        minimum_velocity = c_float(0)
        maximum_velocity = c_float(maximum_velocity * self._unit_factor)
        acceleration = c_float(acceleration * self._unit_factor)
        self._dll.MOT_SetVelParams(self._serial_number, minimum_velocity, acceleration, maximum_velocity)

    def set_velocity(self, value):
        """ Set the maximal velocity for the motor movement.

        @param (float) value: maximal velocity of the stage in m/s or degree/s.
        """
        self.set_velocity_parameters(self._acceleration, value)

    def get_velocity_parameter_limits(self):
        """ Get the current maximal velocity and acceleration parameter.

        @return (dict): Dict the limits velocity parameters

        - (float) maximum_acceleration : maximum acceleration in m/s^2 or degree/s^2
        - (float) maximum_velocity : maximal velocity in m/s or degree/s
        """
        maximum_acceleration = c_float()
        maximum_velocity = c_float()
        self._dll.MOT_GetVelParamLimits(self._serial_number, pointer(maximum_acceleration), pointer(maximum_velocity))
        return {'maximum_acceleration': maximum_acceleration.value / self._unit_factor,
                'maximum_velocity':  maximum_velocity.value / self._unit_factor}

    def get_home_parameter(self):
        """ Get the home parameter

        #todo: Unused - test and document """
        home_direction = c_long()
        limit_switch = c_long()
        home_velocity = c_float()
        zero_offset = c_float()
        self._dll.MOT_GetHomeParams(self._serial_number, pointer(home_direction), pointer(limit_switch),
                                    pointer(home_velocity), pointer(zero_offset))

        return {'home_direction': home_direction.value,
                'limit_switch': limit_switch.value,
                'home_velocity': home_velocity.value / self._unit_factor,  # test unit
                'zero_offset': zero_offset.value}  # test unit

    def set_home_parameter(self, home_dir, switch_dir, home_vel, zero_offset):
        """ Set the home parameters.
        @param (int) home_dir: direction to the home position,
                                1 = Move forward
                                2 = Move backward
        @param (int) switch_dir: Direction of the switch limit:
                                 4 = Use forward limit switch for home datum
                                 1 = Use forward limit switch for home datum.
        @param (float) home_vel: default velocity
        @param (float) zero_offset: the distance or offset (in mm or degrees) of
                                  the limit switch from the Home position.

        #todo: test and document

        """
        home_dir_c = c_long(home_dir)
        switch_dir_c = c_long(switch_dir)
        home_vel_c = c_float(home_vel)
        zero_offset_c = c_float(zero_offset)
        self._dll.MOT_SetHomeParams(self._serial_number, home_dir_c, switch_dir_c, home_vel_c, zero_offset_c)

    def get_pos(self):
        """ Obtain the current absolute position of the stage.

        @return (float): the value of the axis either in meter or in degree.
        """
        if not self.connected:
            raise Exception('Axis not connected.')
        position = c_float()
        self._dll.MOT_GetPosition(self._serial_number, pointer(position))
        return position.value / self._unit_factor

    def move_rel(self, value):
        """ Moves the motor a relative distance specified

        @param (float) value: Relative position desired, in meter or in degree.
        """
        if not self.connected:
            raise Exception('Axis not connected.')

        value = c_float(value * self._unit_factor)
        self._dll.MOT_MoveRelativeEx(self._serial_number, value, self._wait_until_done)

    def move_abs(self, value):
        """ Moves the motor to the Absolute position specified

        @param (float) value: absolute position desired, in meter or degree.
        """
        if not self.connected:
            raise Exception('Axis not connected.')
        value = c_float(value * self._unit_factor)
        self._dll.MOT_MoveAbsoluteEx(self._serial_number, value, self._wait_until_done)

    def move_bc_rel(self, distance):
        """ Moves the motor a relative distance specified, correcting for backlash.

        @param (float) distance: Relative position desired in m or in degree

        NOTE: Be careful in using this method. If interactive mode is on, then
              the stage reacts immediately on both input for the relative
              movement, which prevents the proper execution of the first
              command!
        """
        if not self.connected:
            raise Exception('Axis not connected.')
        self.move_rel(distance - self._backlash)
        self.move_rel(self._backlash)

    # --------------------------- Miscellaneous --------------------------------
    def _create_status_dict(self):
        """ Extract from the status integer all possible states. """
        return {0: 'magnet stopped', 1: 'magnet moves forward', 2: 'magnet moves backward'}

    def get_status(self):
        """ Get the status bits of the current axis.

        @return tuple(int, dict): the current status as an integer and the
                                  dictionary explaining the current status.
        """
        status = self.get_status_bits()

        # Check at least whether magnet is moving:
        if self._test_bit(status, 4):
            return 1, self._create_status_dict()
        elif self._test_bit(status, 5):
            return 2, self._create_status_dict()
        else:
            return 0, self._create_status_dict()

    def identify(self):
        """ Causes the motor to blink the Active LED. """
        self._dll.MOT_Identify(self._serial_number)

    def abort(self):
        """ Abort the movement. """
        self._dll.MOT_StopProfiled(self._serial_number)

    def go_home(self):
        # TODO: a proper home position has to be set, not just zero.
        self.move_abs(0.0)

    def set_backlash(self, backlash):
        """ Set the provided backlash for the apt motor.

        @param float backlash: the backlash in m or degree for the used stage.
        """
        c_backlash = c_float(backlash * self._unit_factor)
        self._dll.MOT_SetBLashDist(self._serial_number, c_backlash)
        self._backlash = backlash
        return backlash

    def get_backlash(self):
        """ Ask for the currently set backlash in the controller for the axis.

        @return float: backlash in m or degree, depending on the axis config.
        """
        backlash = c_float()
        self._dll.MOT_GetBLashDist(self._serial_number, pointer(backlash))
        self._backlash = backlash.value / self._unit_factor
        return self._backlash
# ==============================================================================


class APTFlipper(APTDevice):
    """ Class to control a single Thorlabs APT flipper """

    def __init__(self, dll, serial_number):
        super().__init__(dll, serial_number)

    def get_switch_state(self):
        """ Gives state of switch.

        @return bool: True if on, False if off, None on error
        """
        bits = self.get_status_bits()
        return self._test_bit(bits, 1)

    def switch_on(self):
        """ Set the state to on

        @return (bool): True if succeeds, False otherwise
        """
        status = self.get_status_bits()
        if self._test_bit(status, 4):
            raise Exception('Flipper already moving.')
            return False
        try:
            self._dll.MOT_MoveJog(self._serial_number, 2)
            return True
        except:

            return False

    def switch_off(self):
        """ Set the state to off (channel 2)

        @return (bool): True if succeeds, False otherwise
        """
        status = self.get_status_bits()
        if self._test_bit(status, 4):
            raise Exception('Flipper already moving.')
            return False
        try:
            self._dll.MOT_MoveJog(self._serial_number, 1)
            return True
        except:
            raise Exception('Could not switch flipper.')
            return False

    def get_switch_time(self):
        """ Give switching time for switch.

          @return (float): time needed for switch state change
        """
        return 500e-3  # 500 ms to 2 800 ms #todo: ask the hardware


class APTStage(Base, MotorInterface, SwitchInterface):
    """ Module class to interface Thorlabs APT dll.

    This module interface multiples motor axis, rotation or linear.
    This module also can interface flippers like MFF101 with the SwitchInterface

    A config file entry for a single-axis rotating half-wave-plate stage would look like:

    apt_stage:
        module.Class: 'motor.aptmotor.APTStage'
        dll_path: 'C:\\Program Files\\Thorlabs\\APT\\APT Server\\APT.dll'
        axis_labels: ['phi']
        serial_numbers: [27500136]

    A config file entry for a linear xy-axis stage would look like:

    apt_stage:
        module.Class: 'motor.aptmotor.APTStage'
        dll_path: 'C:\\Program Files\\Thorlabs\\APT\\APT Server\\APT.dll'
        axis_labels: ['x', 'y']
        serial_numbers: [00000000, 00000001]
        pitch: [None, 1]
        minimum_positions: [None, 0]
        maximum_positions: [None, 100e-3]
        maximum_velocity: [None, 10]
        acceleration_max: [None, 10]

    apt_stage:
        module.Class: 'motor.aptmotor.APTStage'
        dll_path: 'C:\\Program Files\\Thorlabs\\APT\\APT Server\\APT.dll'
        flippers: [27500136]

    Tested successfully with :
        - TDC001
        - KDC001
        - MFF101

    """

    dll_path = ConfigOption('dll_path', missing='error')  # Probably : C:\Program Files\Thorlabs\APT\APT Server\APT.dll
    axis_labels = ConfigOption('axis_labels', default=[])  # A list of axis label
    serial_numbers = ConfigOption('serial_numbers', default=[])  # A list of serial number as numbers

    # Below are optional parameters, default value are probably good.
    pitch = ConfigOption('pitch', default=None)  # None for default or a list of explicitly defined pitch
    minimum_positions = ConfigOption('minimum_positions', default=None)  # None or a list of explicitly defined minimum
    maximum_positions = ConfigOption('maximum_positions', default=None)  # None or a list of explicitly defined maximum
    maximum_acceleration = ConfigOption('maximum_acceleration', default=None)  # None or a list of maximum acceleration
    backlash = ConfigOption('backlash', default=None)  # None or a list of backlash

    flippers = ConfigOption('flippers', default=[])  # A list of flipper serial numbers

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._axis_dict = None
        self._dll = None

    def on_activate(self):
        """ Initialize instance variables and connect to hardware as configured """

        self._dll = windll.LoadLibrary(self.dll_path)
        self._dll.EnableEventDlg(False)
        self._dll.APTInit()

        # The references to the different axis are stored in this dictionary:
        self._axis_dict = OrderedDict()
        for i, label in enumerate(self.axis_labels):
            axis = APTMotor(self._dll, self.serial_numbers[i])
            axis.initialize_hardware_device()

            # Apply config
            if self.pitch is not None and self.pitch[i] is not None:
                axis.set_pitch(self.pitch[i])

            params = axis.get_stage_axis_info()
            minimum_position = params['minimum_position']
            maximum_position = params['maximum_position']
            if self.minimum_positions is not None and self.minimum_positions[i] is not None:
                minimum_position = self.minimum_positions[i]
            if self.maximum_positions is not None and self.maximum_positions[i] is not None:
                maximum_position = self.maximum_positions[i]
            axis.set_stage_axis_range(minimum_position, maximum_position)

            params = axis.get_velocity_parameter_limits()
            maximum_acceleration = params['maximum_acceleration']
            if self.maximum_acceleration is not None and self.maximum_acceleration[i] is not None:
                maximum_acceleration = self.maximum_acceleration[i]
            axis.set_velocity_parameters(maximum_acceleration, params['maximum_velocity'])

            if self.backlash is not None and self.backlash[i] is not None:
                axis.set_backlash(self.backlash[i])

            self._axis_dict[label] = axis

        # The references to the different flippers are stored in this list:
        self._flipper_list = []
        for i, serial_number in enumerate(self.flippers):
            flipper = APTFlipper(self._dll, serial_number)
            flipper.initialize_hardware_device()
            self._flipper_list.append(flipper)

    def on_deactivate(self):
        """ Disconnect from hardware and clean up.
        """
        self._dll.APTCleanUp()

    def get_number_of_hardware_units(self, hardware_type):
        """ Returns the number of connected external hardware (HW) units that are available to be interfaced. """
        number = c_long()
        self._dll.GetNumHWUnitsEx(HARDWARE_TYPES[hardware_type], pointer(number))
        return number.value

    def get_serial_number_by_index(self, hardware_type, index=0):
        """ Returns the Serial Number of the specified index """
        serial_number = c_long()
        self._dll.GetHWSerialNumEx(HARDWARE_TYPES[hardware_type], index, pointer(serial_number))
        return serial_number.value

    def get_constraints(self):
        """ Retrieve the hardware constrains from the motor device.

        @return dict: dict with constraints for the motor stage hardware. These
                      constraints will be passed via the logic to the GUI so
                      that proper display elements with boundary conditions
                      can be made.

        Provides all the constraints for each axis of a motorized stage
        (like total travel distance, velocity, ...)
        Each axis has its own dictionary, where the label is used as the
        identifier throughout the whole module. The dictionaries for each axis
        are again grouped together in a constraints dictionary in the form

            {'<label_axis0>': axis0 }

        where axis0 is again a dict with the possible values defined below. The
        possible keys in the constraint are defined in the interface file.
        If the hardware does not support the values for the constraints, then
        insert just None. If you are not sure about the meaning, look in other
        hardware files to get an impression.
        """
        constraints = {}

        for label in self.axis_labels:
            axis = self._axis_dict[label]

            # create a dictionary for the constraints of this axis
            dict_axis = {}
            dict_axis['label'] = label
            stage_axis_info = axis.get_stage_axis_info()
            dict_axis['unit'] = stage_axis_info['unit']
            dict_axis['pos_min'] = stage_axis_info['minimum_position']
            dict_axis['pos_max'] = stage_axis_info['maximum_position']
            dict_axis['pos_step'] = 0.01  # todo: fix this
            velocity_parameter_limits = axis.get_velocity_parameter_limits()
            dict_axis['vel_min'] = 0
            dict_axis['vel_max'] = velocity_parameter_limits['maximum_velocity']
            dict_axis['vel_step'] = 0.1  # todo: fix this
            dict_axis['acc_min'] = 0.0  # todo: fix this
            dict_axis['acc_max'] = velocity_parameter_limits['maximum_acceleration']  # todo: fix this
            dict_axis['ramp'] = ['Trapez']  # todo: document
            constraints[label] = dict_axis

        return constraints

    def move_rel(self,  param_dict):
        """ Moves stage in given direction (relative movement)

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters, which should be changed.
                                With get_constraints() you can obtain all
                                possible parameters of that stage. According to
                                this parameter set you have to pass a dictionary
                                with keys that are called like the parameters
                                from get_constraints() and assign a SI value to
                                that. For a movement in x the dict should e.g.
                                have the form:
                                    dict = { 'x' : 23 }
                                where the label 'x' corresponds to the chosen
                                axis label.

        """
        curr_pos_dict = self.get_pos()
        constraints = self.get_constraints()

        for label_axis in self._axis_dict:
            if param_dict.get(label_axis) is not None:
                move = param_dict[label_axis]
                curr_pos = curr_pos_dict[label_axis]

                if (curr_pos + move > constraints[label_axis]['pos_max']) or\
                   (curr_pos + move < constraints[label_axis]['pos_min']):

                    self.log.error('Cannot make further relative movement')
                else:
                    self._axis_dict[label_axis].move_rel(move)

    def move_abs(self, param_dict):
        """ Moves stage to absolute position (absolute movement)

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters, which should be changed. Usage:
                                 {'axis_label': <a-value>}.
                                 'axis_label' must correspond to a label given
                                 to one of the axis.
        A smart idea would be to ask the position after the movement.
        """
        constraints = self.get_constraints()

        for label_axis in self._axis_dict:
            if param_dict.get(label_axis) is not None:
                desired_pos = param_dict[label_axis]

                constr = constraints[label_axis]
                if not(constr['pos_min'] <= desired_pos <= constr['pos_max']):

                    self.log.warning(
                        'Cannot make absolute movement of the '
                        'axis "{0}" to position {1}, since it exceeds '
                        'the limts [{2},{3}]. Movement is ignored!'
                        ''.format(label_axis, desired_pos, constr['pos_min'], constr['pos_max'])
                    )
                else:
                    self._axis_dict[label_axis].move_abs(desired_pos)

    def abort(self):
        """ Stops movement of the stage. """

        for label_axis in self._axis_dict:
            self._axis_dict[label_axis].abort()

        self.log.warning('Movement of all the axis aborted! Stage stopped.')

    def get_pos(self, param_list=None):
        """ Gets current position of the stage arms

        @param list param_list:
            optional, if a specific position of an axis
            is desired, then the labels of the needed
            axis should be passed as the param_list.
            If nothing is passed, then from each axis the
            position is asked.

        @return
            dict with keys being the axis labels and item the current
            position.
        """
        pos = {}

        if param_list is not None:
            for label_axis in param_list:
                if label_axis in self._axis_dict:
                    pos[label_axis] = self._axis_dict[label_axis].get_pos()
        else:
            for label_axis in self._axis_dict:
                pos[label_axis] = self._axis_dict[label_axis].get_pos()

        return pos

    def get_status(self, param_list=None):
        """ Get the status of the position

        @param list param_list: optional, if a specific status of an axis
                                is desired, then the labels of the needed
                                axis should be passed in the param_list.
                                If nothing is passed, then from each axis the
                                status is asked.


        """

        status = {}
        if param_list is not None:
            for label_axis in param_list:
                if label_axis in self._axis_dict:
                    status[label_axis] = self._axis_dict[label_axis].get_status()
        else:
            for label_axis in self._axis_dict:
                status[label_axis] = self._axis_dict[label_axis].get_status()

        return status

    def calibrate(self, param_list=None):
        """ Calibrates the stage.

        @param dict param_list: param_list: optional, if a specific calibration
                                of an axis is desired, then the labels of the
                                needed axis should be passed in the param_list.
                                If nothing is passed, then all connected axis
                                will be calibrated.

        @return int: error code (0:OK, -1:error)

        After calibration the stage moves to home position which will be the
        zero point for the passed axis. The calibration procedure will be
        different for each stage.
        """
        return  # todo: implement go_home correctly
        #if param_list is not None:
        #    for label_axis in param_list:
        #        if label_axis in self._axis_dict:
        #            self._axis_dict[label_axis].go_home()
        #else:
        #    for label_axis in self._axis_dict:
        #        self._axis_dict[label_axis].go_home()

    def get_velocity(self, param_list=None):
        """ Gets the current velocity for all connected axes.

        @param dict param_list: optional, if a specific velocity of an axis
                                is desired, then the labels of the needed
                                axis should be passed as the param_list.
                                If nothing is passed, then from each axis the
                                velocity is asked.

        @return dict : with the axis label as key and the velocity as item.
        """

        vel = {}
        if param_list is not None:
            for label_axis in param_list:
                if label_axis in self._axis_dict:
                    vel[label_axis] = self._axis_dict[label_axis].get_velocity()
        else:
            for label_axis in self._axis_dict:
                vel[label_axis] = self._axis_dict[label_axis].get_velocity()

        return vel

    def set_velocity(self, param_dict):
        """ Write new value for velocity.

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters, which should be changed. Usage:
                                 {'axis_label': <the-velocity-value>}.
                                 'axis_label' must correspond to a label given
                                 to one of the axis.
        """
        constraints = self.get_constraints()

        for label_axis in param_dict:
            if label_axis in self._axis_dict:
                desired_vel = param_dict[label_axis]
                constr = constraints[label_axis]
                if not(constr['vel_min'] <= desired_vel <= constr['vel_max']):

                    self.log.warning(
                        'Cannot set velocity of the axis "{0}" '
                        'to the desired velocity of "{1}", since it '
                        'exceeds the limts [{2},{3}] ! Command is ignored!'
                        ''.format(label_axis, desired_vel, constr['vel_min'], constr['vel_max'])
                    )

    # ################# SwitchInterface ######################
    def getNumberOfSwitches(self):
        """ Gives the number of switches connected to this hardware.

          @return (int: number of swiches on this hardware
        """
        return len(self._flipper_list)

    def getSwitchState(self, switchNumber=0):
        """ Get the state of the switch.

          @param int switchNumber: index of switch

          @return bool: True if On, False if Off
        """
        return self._flipper_list[switchNumber].get_switch_state()

    def getCalibration(self, switchNumber, state):
        """ Get calibration parameter for switch.

        Function not used by this module
        """
        return 0

    def setCalibration(self, switchNumber, state, value):
        """ Set calibration parameter for switch.

        Function not used by this module
        """
        return True

    def switchOn(self, switchNumber):
        """ Set the state to on (channel 1)

          @param int switchNumber: number of switch to be switched

          @return bool: True if succeeds, False otherwise
        """
        self._flipper_list[switchNumber].switch_on()
        return True

    def switchOff(self, switchNumber):
        """ Set the state to off (channel 2)

          @param int switchNumber: number of switch to be switched

          @return bool: True if suceeds, False otherwise
        """
        self._flipper_list[switchNumber].switch_off()
        return True

    def getSwitchTime(self, switchNumber):
        """ Give switching time for switch.

          @param int switchNumber: number of switch

          @return float: time needed for switch state change
        """
        return self._flipper_list[switchNumber].get_switch_time()
