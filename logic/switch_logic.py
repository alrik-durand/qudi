# -*- coding: utf-8 -*-
"""
Interact with switches.

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

from logic.generic_logic import GenericLogic
from core.connector import Connector
from core.configoption import ConfigOption
from core.util.mutex import RecursiveMutex
from qtpy import QtCore


class SwitchLogic(GenericLogic):
    """ Logic module for interacting with the hardware switches.
    This logic has the same structure as the SwitchInterface but supplies additional functionality:
        - switches can either be manipulated by index or by their names
        - signals are generated on state changes

    switchlogic:
        module.Class: 'switch_logic.SwitchLogic'
        watchdog_interval: 1  # optional
        autostart_watchdog: True  # optional
        connect:
            hardware: <switch name>
        switch_names:
            one: ['down', 'up']
            two: ['down', 'up']
            three: ['low', 'middle', 'high']
    """

    # connector for one switch, if multiple switches are needed use the SwitchCombinerInterfuse
    hardware = Connector(interface='SwitchInterface')

    _custom_name_config = ConfigOption(name='custom_name', default=None, missing='nothing')
    _custom_states_config = ConfigOption(name='custom_states', default=None, missing='nothing')

    _watchdog_interval = ConfigOption(name='watchdog_interval', default=1.0, missing='nothing')
    _autostart_watchdog = ConfigOption(name='autostart_watchdog', default=False, missing='nothing')

    sigSwitchesChanged = QtCore.Signal(dict)
    sigWatchdogToggled = QtCore.Signal(bool)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._thread_lock = RecursiveMutex()
        self._watchdog_active = None
        self._watchdog_interval_ms = None
        self._old_states = None
        self._custom_name = None
        self._custom_states = None
        self._hardware_states = None

    def on_activate(self):
        """ Activate module
        """

        self._custom_name = self._custom_name_config if self._custom_name_config else self.hardware().name

        # Define states as config defined if possible
        if self._custom_states_config is not None:
            self._custom_states = self._custom_states_config
        else:
            self._custom_states = self.hardware().available_states

        # Check states validity
        if not isinstance(self._custom_states, dict):
            self.log.error('custom_states must be a dict of tuples')
        if len(self._custom_states) != self.hardware().number_of_switches:
            self.log.error('number of elements in custom states do not match')
        if not all((isinstance(name, str) and name) for name in self._custom_states):
            self.log.error('Switch name must be non-empty string')
        if not all(len(states) > 1 for states in self._custom_states.values()):
            self.log.error('State tuple must contain at least 2 states')
        if not all(all((s and isinstance(s, str)) for s in states) for states in self._custom_states.values()):
            self.log.error('Switch states must be non-empty strings')

        # Convert state lists to tuples in order to restrict mutation
        self._custom_states = {switch: tuple(states) for switch, states in self._custom_states.items()}

        # Store the hardware defined states for name conversion
        self._hardware_states = self.hardware().available_states

        self._old_states = self.hardware().states
        self._watchdog_interval_ms = int(round(self._watchdog_interval * 1000))

        if self._autostart_watchdog:
            self._watchdog_active = True
            QtCore.QMetaObject.invokeMethod(self, '_watchdog_body', QtCore.Qt.QueuedConnection)
        else:
            self._watchdog_active = False

    def on_deactivate(self):
        """ Deactivate module
        """
        self._watchdog_active = False

    @property
    def switch_names(self):
        """ Names of all available switches as tuple.

        @return str[]: Tuple of strings of available switch names.
        """
        return tuple(self._custom_states)

    @property
    def number_of_switches(self):
        """ Number of switches provided by the hardware.

        @return int: number of switches
        """
        return int(self.hardware().number_of_switches)

    @property
    def available_states(self):
        """ Names of the states as a dict of tuples.

        The keys contain the names for each of the switches. The values are tuples of strings
        representing the ordered names of available states for each switch.

        @return dict: Available states per switch in the form {"switch": ("state1", "state2")}
        """
        return self._custom_states

    @property
    def device_name(self):
        """ Name of the connected hardware switch as string.

        @return str: The name of the connected hardware switch
        """
        return self.hardware().name

    @property
    def watchdog_active(self):
        return self._watchdog_active


    def _hardware_to_custom(self, states):
        """ Convert a state dictionary from the hardware convention to custom config defined convention

        Ex : {'A': '1'}  -->  {'Detector switch': 'APD'} """
        result = {}
        for key in states:
            custom_name = list(self._custom_states)[list(self._hardware_states).index(key)]
            custom_state_name = self._custom_states[custom_name][self._hardware_states[key].index(states[key])]
            result[custom_name] = custom_state_name
        return result

    def _custom_to_hardware(self, states):
        """ Convert a state dictionary from the custom config convention to hardware convention

        Ex : {'Detector switch': 'APD'} --> {'A': '1'} """
        result = {}
        for key in states:
            hardware_name = list(self._hardware_states)[list(self._custom_states).index(key)]
            hardware_state_name = self._hardware_states[hardware_name][self._custom_states[key].index(states[key])]
            result[hardware_name] = hardware_state_name
        return result

    @property
    def states(self):
        """ The current states the hardware is in as state dictionary with switch names as keys and
        state names as values.

        @return dict: All the current states of the switches in the form {"switch": "state"}
        """
        with self._thread_lock:
            try:
                hardware_states = self.hardware().states
                self._old_states = hardware_states
            except:
                self.log.exception('Error during query of all switch states.')
                hardware_states = dict()
            return self._hardware_to_custom(hardware_states)

    @states.setter
    def states(self, state_dict):
        """ The setter for the states of the hardware.

        The states of the system can be set by specifying a dict that has the switch names as keys
        and the names of the states as values.

        @param dict state_dict: state dict of the form {"switch": "state"}
        """
        with self._thread_lock:
            try:
                self.hardware().states = self._custom_to_hardware(state_dict)
            except:
                self.log.exception('Error while trying to set switch states.')

            states = self.states
            if states:
                self.sigSwitchesChanged.emit({switch: states[switch] for switch in state_dict})

    def get_state(self, switch):
        """ Query state of single switch by name

        @param str switch: name of the switch to query the state for
        @return str: The current switch state
        """
        with self._thread_lock:
            try:
                hardware_name = list(self._hardware_states)[list(self._custom_states).index(switch)]
                state = self.hardware().get_state(hardware_name)
                self._old_states[hardware_name] = state
            except:
                self.log.exception(f'Error while trying to query state of switch "{switch}".')
                state = None
            return self._custom_states[switch][self._hardware_states[hardware_name].index(state)]

    @QtCore.Slot(str, str)
    def set_state(self, switch, state):
        """ Query state of single switch by name

        @param str switch: name of the switch to change
        @param str state: name of the state to set
        """
        with self._thread_lock:
            try:
                hardware_name = list(self._hardware_states)[list(self._custom_states).index(switch)]
                hardware_state = self._hardware_states[hardware_name][self._custom_states[switch].index(state)]
                self.hardware().set_state(hardware_name, hardware_state)
            except:
                self.log.exception(
                    f'Error while trying to set switch "{switch}" to state "{state}".'
                )
            curr_state = self.get_state(switch)
            if curr_state is not None:
                self.sigSwitchesChanged.emit({switch: curr_state})

    @QtCore.Slot(bool)
    def toggle_watchdog(self, enable):
        """

        @param bool enable:
        """
        enable = bool(enable)
        with self._thread_lock:
            if enable != self._watchdog_active:
                self._watchdog_active = enable
                self.sigWatchdogToggled.emit(enable)
                if enable:
                    QtCore.QMetaObject.invokeMethod(self,
                                                    '_watchdog_body',
                                                    QtCore.Qt.QueuedConnection)

    @QtCore.Slot()
    def _watchdog_body(self):
        """ Helper function to regularly query the states from the hardware.

        This function is called by an internal signal and queries the hardware regularly to fire
        the signal sig_switch_updated, if the hardware changed its state without notifying the logic.
        The timing of the watchdog is set by the ConfigOption watchdog_interval in seconds.
        """
        with self._thread_lock:
            if self._watchdog_active:
                curr_states = self.hardware().states
                diff_state = {switch: state for switch, state in curr_states.items() if
                              state != self._old_states[switch]}
                self._old_states = curr_states
                if diff_state:
                    self.sigSwitchesChanged.emit(self._hardware_to_custom(diff_state))
                QtCore.QTimer.singleShot(self._watchdog_interval_ms, self._watchdog_body)
