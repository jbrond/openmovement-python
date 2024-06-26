"""
Open Movement Accelerometer Calibration
Dan Jackson, 2014-2021
Based on a C implementation by Dan Jackson/Nils Hammerla 2014,
Based on a Matlab implementation by Nils Hammerla 2014,
Inspired by the algorithm in the GGIR package (http://cran.r-project.org/web/packages/GGIR/) by Vincent T van Hees, Zhou Fang, Jing Hua Zhao.
...as discussed in "Autocalibration of accelerometer data for free-living physical activity assessment using local gravity and temperature: an evaluation on four continents", https://dx.doi.org/10.1152%2Fjapplphysiol.00421.2014
"""

# NOTE: Not quite complete - do not use!

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
import openmovement.load.cwa_load as cwa_load
import openmovement.process.epoch as epoch

NUM_AXES = 3
AXIS_STD_THRESHOLD = 0.013
WINDOW_DURATION = 10

def find_stationary_points(samples, sample_rate, temperature=None, window_duration = WINDOW_DURATION, axis_std_threshold = AXIS_STD_THRESHOLD, verbose=False):
    if verbose: print('Finding stationary points...', flush=True)

    # Parameters
    window_size = int(window_duration * sample_rate)
    if verbose: print('...window size: %d samples' % window_size, flush=True)

    # Samples should be triaxial
    axes = samples.shape[1]
    if axes != NUM_AXES:
        print('WARNING: Only designed to find stationary points in %d-axis accelerometer data (%d-axes)' % (NUM_AXES, axes))

    # Use zero when temperature not used
    if temperature is None:
        print('WARNING: Temperature not being used for calibration')
        temperature = np.zeros(samples.shape[0])

    # Must use 1D temperature
    if temperature.ndim != 1:
        raise Exception('Temperature can only be one-dimensional')

    # Check there is a temperature for each sample
    if temperature.shape[0] != samples.shape[0]:
        print('WARNING: Expected temperature to be same length as samples')
        if temperature.shape[0] < samples.shape[0]:
            raise Exception('When the temperature is used, each sample must have a temperature')

    # Divide into windows (window/sample/axis), (NOTE: based on configured rate rather than actual times)
    num_axes = samples.shape[1]
    windows = epoch.split_into_blocks(samples, window_size)
    windows_temperature = epoch.split_into_blocks(temperature, window_size)
    if verbose: print('...%d windows' % windows.shape[0], flush=True)

    # Transpose (axis/window/sample)
    per_axis_windows = np.transpose(windows, axes=[2,0,1])

    # Per-axis standard deviation below threshold, and all axes below threshold
    per_axis_window_std_below_threshold = np.std(per_axis_windows, axis=2) < axis_std_threshold
    windows_all_axes_std_below_threshold = np.sum(per_axis_window_std_below_threshold, axis=0) >= num_axes

    # Mean axis values and mean temperature
    per_axis_window_mean = np.mean(per_axis_windows,axis=2)
    windows_mean_temperature = np.mean(windows_temperature, axis=1)

    # Selected windows (window/axis)
    selected_window_mean = per_axis_window_mean[:,windows_all_axes_std_below_threshold].transpose()
    selected_window_temperature = windows_mean_temperature[windows_all_axes_std_below_threshold]

    # Stationary periods: (mean_x, mean_y, mean_z, temperature)
    stationary_periods = np.c_[ selected_window_mean, selected_window_temperature ]

    if verbose: print('...done (%d)' % stationary_periods.shape[0], flush=True)

    return stationary_periods
    

def find_calibration(stationary_points, verbose=False):
    # Stationary points: (mean_x, mean_y, mean_z, temperature)
    samples = stationary_points[:,0:3]
    temperature = stationary_points[:,3]

    # Configuration parameters
    config = {
        "max_iter": 1000,				    # 
        "conv_crit": 0.000001,				# 
        "axis_range": 0.3,					# Required per-axis range in stationary points (0.3)
        "maximum_scale_diff": 0.2,			# Maximum amount of per-axis scale (absolute difference from 1)
        "maximum_offset_diff": 0.41,		# Maximum amount of per-axis offset
        "maximum_temp_offset_diff": 0.02,	# Maximum amount of per-axis temperature offset
    }

    # Initial values
    calibration = {
        'scale': np.ones(NUM_AXES),
        'offset': np.zeros(NUM_AXES),
        'temp_offset': np.zeros(NUM_AXES),
        'reference_temperature': 0.0,
        'num_axes': 0,
        'error_code': 0,
    }


    # TODO: Check unit sphere coverage on each axis against config['axis_range']


    # Iterate to converge
    for iter in range(config['max_iter']):

        # Apply current calibration
        scaled_points = apply_calibration(calibration, samples, temperature)

        # Project onto unit sphere
        targets = (scaled_points.transpose() / np.sqrt(np.sum(scaled_points * scaled_points,axis=1))).transpose()

        # Fit
        for axis in [0,1,2]:

            # TODO: This is only 1D on scale/offset and is not currently 2D for temperature_offset
            (scale, offset) = np.polyfit(scaled_points[:,axis], targets[:,axis], 1)
        
            # adapt
            calibration['scale'][axis] *= scale
            calibration['offset'][axis] += offset

    print(calibration)
    return calibration


def apply_calibration(calibration, samples, temperature):
    # Use zero when temperature not used
    if temperature is None:
        print('WARNING: Temperature not being used to apply calibration')
        temperature = np.full(samples.shape[0], calibration['reference_temperature'])

    # Rescaling is:  v = (v + offset) * scale + (temp - referenceTemperature) * tempOffset
    calibrated = (samples + calibration['offset']) * calibration['scale']
    shifted_temperature = temperature - calibration['reference_temperature']

    # Repeat over axes for multiplying
    shifted_temperature = shifted_temperature[:, np.newaxis].repeat(3, axis=1)
    temp_offsets = calibration['temp_offset'] * shifted_temperature

    calibrated += temp_offsets
    return calibrated


def main():
    filename = '../../_local/data/sample.cwa'
    #filename = '../../_local/data/mixed_wear.cwa'
    #filename = '../../_local/data/AX6-Sample-48-Hours.cwa'
    #filename = '../../_local/data/AX6-Static-8-Day.cwa'
    #filename = '../../_local/data/longitudinal_data.cwa'
    
    # Data file path relative to module root/source parent (rather than CWD)
    import os
    filename = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', filename))

    with cwa_load.CwaData(filename, verbose=True, include_gyro=False, include_temperature=True) as cwa_data:
        sample_values = cwa_data.get_temperature_values()  # time,accel_x,accel_y,accel_z,*_,temperature

        samples = sample_values[:,1:4]
        temperature = sample_values[:,-1]

        sample_rate = cwa_data.get_sample_rate()
        stationary_points = find_stationary_points(samples, sample_rate, temperature, verbose=True)
        #print(stationary_points)

        calibration = find_calibration(stationary_points)
        print(calibration)

        calibrated = apply_calibration(calibration, samples, temperature)
        print(calibrated)

        print('Done')
        
    print('End')

if __name__ == "__main__":
    main()

