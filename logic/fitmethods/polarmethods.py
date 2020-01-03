# -*- coding: utf-8 -*-
"""
This file contains methods for dipole or other polar function polar fitting, these methods
are imported by class FitLogic.

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


from lmfit.models import Model
import numpy as np


def make_dipole_model(self, prefix=None):
    """ Create a model of the fluorescence depending on collection angle.

    @return tuple: (object model, object params)

    Explanation of the objects:
        object lmfit.model.CompositeModel model:
            A model the lmfit module will use for that fit.
            Returns an object of the class
            lmfit.model.CompositeModel.

        object lmfit.parameter.Parameters params:
            It is basically an OrderedDict, so a dictionary, with keys
            denoting the parameters as string names and values which are
            lmfit.parameter.Parameter (without s) objects, keeping the
            information about the current value.
    """

    def dipole_function(x, amplitude, phi, ratio):
        """ Fluorescence depending excitation power function

        @param numpy.array x: 1D array as the independent variable - angle in radian
        @param float amplitude: The maximum fluorescence
        @param float phi: The angle of the most emission, in radian, in [0, pi]
        @param float ratio: the percentage of polarization dependant fluorescence

        @return: dipole model
        """

        return amplitude*((1-ratio) + ratio * np.cos(x-phi)**2)

    if not isinstance(prefix, str) and prefix is not None:
        self.log.error('The passed prefix <{0}> of type {1} is not a string and'
                     'cannot be used as a prefix and will be ignored for now.'
                     'Correct that!'.format(prefix, type(prefix)))

    model = Model(dipole_function, independent_vars='x', prefix=prefix)
    params = model.make_params()
    params['ratio'].min = 0

    return model, params


def make_dipole_fit(self, x_axis, data, estimator, units=None, add_params=None, **kwargs):
    """ Perform a fit on the provided data with a fluorescence polarization depending function.

    @param numpy.array x_axis: 1D axis values
    @param numpy.array data: 1D data, should have the same dimension as x_axis.
    @param method estimator: Pointer to the estimator method
    @param list units: List containing the ['angle', 'radius'] units as strings
    @param Parameters or dict add_params: optional, additional parameters of
                type lmfit.parameter.Parameters, OrderedDict or dict for the fit
                which will be used instead of the values from the estimator.

    @return object result: lmfit.model.ModelFit object, all parameters
                           provided about the fitting, like: success,
                           initial fitting values, best fitting values, data
                           with best fit with given axis,...
    """

    mod_final, params = self.make_dipole_model()

    error, params = estimator(x_axis, data, params)

    # overwrite values of additional parameters
    params = self._substitute_params(
        initial_params=params,
        update_params=add_params)

    result = mod_final.fit(data, x=x_axis, params=params, **kwargs)

    if units is None:
        units = ['arb. unit', 'arb. unit']
    result_str_dict = dict()

    result_str_dict['amplitude'] = {'value': result.params['amplitude'].value,
                                    'error': result.params['amplitude'].stderr,
                                    'unit': units[1]}

    result_str_dict['phi'] = {'value': result.params['phi'].value*180/np.pi % 180,
                                    'error': result.params['phi'].stderr*180/np.pi,
                                    'unit': '°'}

    result_str_dict['ratio'] = {'value': result.params['ratio'].value*100,
                                    'error': result.params['ratio'].stderr*100,
                                    'unit': '%'}

    result.result_str_dict = result_str_dict


    return result


def estimate_dipole(self, x_axis, data, params):
    """ Provides an estimation for a dipole function.

    @param numpy.array x_axis: 1D axis values
    @param numpy.array data: 1D data, should have the same dimension as x_axis.
    @param lmfit.Parameters params: object includes parameter dictionary which
                                    can be set

    @return tuple (error, params):

    Explanation of the return parameter:
        int error: error code (0:OK, -1:error)
        Parameters object params: set parameters of initial values
    """
    error = self._check_1D_input(x_axis=x_axis, data=data, params=params)
    params['amplitude'].value = np.max(data)
    params['phi'].value = x_axis[np.argmax(data)]
    params['ratio'].value = 0.5

    return error, params
