# -*- coding: utf-8 -*-

"""
This file contains the Qudi Interface file to control motorized stages.

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

from core.meta import InterfaceMetaclass
from core.interface import abstract_interface_method
from core.interface import ScalarConstraint


class Status(Enum):
    """ Different possible status of the hardware """
    IDLE = 0
    MOVING_FORWARD = 1
    MOVING_BACKWARD = 2
    MOVING_UNKNOWN = 3  # Some hardware might not know this. The logic will handle it.


class AxisConstraints:
    def __init__(self):
        self.label = ''
        self.unit = ''  # 'rad' or 'meter'
        self.position = ScalarConstraint()
        self.velocity = ScalarConstraint()
        self.acceleration = ScalarConstraint()


class MotorInterface(metaclass=InterfaceMetaclass):
    """ This is the Interface class to define the controls for a multi axis step motor device.

    """

    @abstract_interface_method
    def get_constraints(self):
        """ Retrieve the hardware fixed constrains

        @return list(AxisConstraints): A list of AxisConstraints representing the constraints of each axis
        """
        pass

    @abstract_interface_method
    def move_relative(self, axis, value):
        """ Moves stage in given direction (relative movement)

        @param (str) axis : Label of the axis
        @param (float) value : Relative distance to move

        Method returns immediately. Use get_status for help.
        """
        pass

    @abstract_interface_method
    def move_absolute(self, axis, value):
        """ Moves stage to absolute position (absolute movement)

        @param (str) axis : Label of the axis
        @param (float) value : Position to set

        """
        pass

    @abstract_interface_method
    def abort(self, axis):
        """ Stops movement of the stage

        @param (str) axis : Label of the axis
        """
        pass

    @abstract_interface_method
    def get_position(self, axis):
        """ Gets current position of an axis

        @param (str) axis : Label of the axis

        @return (float): Current position of the axis

        The current position should match the physical value if possible, not the setpoint value
        """
        pass

    @abstract_interface_method
    def get_status(self, axis):
        """ Get the status of the given axis

        @param (str) axis : Label of the axis

        @return (Status): Status object representing the current status
        """
        pass

    @abstract_interface_method
    def calibrate(self, axis):
        """ Calibrates the stage.

        @param (str) axis : Label of the axis

        After calibration the stage moves to home position which will be the
        zero point for the passed axis. The calibration procedure will be
        different for each stage.
        """
        pass

    @abstract_interface_method
    def get_velocity(self, axis):
        """ Gets the current velocity of an axis

        @param (str) axis : Label of the axis

        @return (float): The velocity in unit/s
        """
        pass

    @abstract_interface_method
    def set_velocity(self, axis, value):
        """ Set the velocity of an axis

        @param (str) axis : Label of the axis
        @param (float) value: The velocity in unit/s
        """
        pass
