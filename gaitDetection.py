from scipy import signal
import numpy as np
from scipy.signal import find_peaks

def getGaitEvents(acc, sf, min_stride):

    '''
    This function detects the final contact (FC) and initial contact (IC) events in an acceleration signal.

    The code is based on the following paper and the respective MATLAB code: Gurchiek et al. (2020): Gait event detection using a thigh-worn accelerometer, https://doi.org/10.1016/j.gaitpost.2020.06.004.

    Parameters
    ----------
    acc : array
        The 1D acceleration signal.

    sf : int
        The sampling frequency of the acceleration signal.

    min_stride : float
        The minimum stride duration in seconds.

    Returns
    -------
    FC_pred : array
        The indices of the predicted foot contact events.

    IC_pred : array
        The indices of the predicted foot off events.

    acc_step : array
        The filtered acceleration signal used to detect the foot contact events.

    acc_stride : array
        The filtered acceleration signal used to detect the foot off events.

    acc_5stride : array
        The filtered acceleration signal used to detect the foot off events.
    '''
    
    min_stride_samples = int(min_stride * sf)

    #### FILTERING ####

    # calculate the power spectral density of the acceleration signal and frequencies
    f, Pxx = signal.welch(acc, fs=sf, nfft=4096, nperseg=2048)

    f_step = f[np.argmax(Pxx)]

    peaks, _ = find_peaks(Pxx[f < f_step])

    f_stride = f[peaks[np.argmax(Pxx[peaks])]]

    if f_stride < 0.5:
        f_stride = f[peaks[np.argsort(Pxx[peaks])[-2]]]

    # create filtered signals
    b, a = signal.butter(4, f_step, 'low', fs=sf)
    acc_step = signal.filtfilt(b, a, acc)

    b, a = signal.butter(4, f_stride, 'low', fs=sf)
    acc_stride = signal.filtfilt(b, a, acc)

    b, a = signal.butter(4, 5 * f_stride, 'low', fs=sf)
    acc_5stride = signal.filtfilt(b, a, acc)

    # identify local minima in the x_f_stride signal
    minima, _ = find_peaks(acc_stride * -1)

    # calculate the difference between each minimum
    minima_diff = np.diff(minima)

    # check if any of the differences are smaller than the minimum stride samples
    minima_check = minima_diff < min_stride_samples

    # if there are any minima that are too close, remove the one with the lower variance
    if np.sum(minima_check) > 0:

        # filter the acceleration signal with a low-pass butterworth filter with a cut-off frequency of 10 Hz
        b, a = signal.butter(4, 10, 'high', fs=sf)
        acc10 = signal.filtfilt(b, a, acc)

        del_min = []

        # loop through minima_check == True
        for i, check in enumerate(minima_check):

            if check:

                min1 = minima[i]
                min2 = minima[i + 1]

                # calculate the variance of the signal between min1 and min2
                var1 = np.var(acc10[min1:min2])

                # calculate the variance of the signal following min2
                var2 = np.var(acc10[min2:min2 + (min2 - min1)])

                # remove the minimum with the lower variance
                if var1 < var2:
                    del_min.append(min1)
                else:
                    del_min.append(min2)

        # remove the minima in del_min
        minima = np.setdiff1d(minima, del_min)

    #### FC EVENTS ####

    # identify peaks in the x_f_step signal
    peaks, _ = find_peaks(acc_step, height=1, distance=100)

    # for each minimum find the highest peak between it and the previous minimum
    FC_pred = []

    for i in range(len(minima)):
        minimum = minima[i]
        peaks_between = peaks[[peaks < minimum][0]]

        if i > 0:
            peaks_between = peaks_between[[peaks_between > minima[i-1]][0]]

        if len(peaks_between) > 0:
            FC_min = peaks_between[np.argmax(acc_step[peaks_between])]
            FC_pred.append(FC_min)


    #### IC EVENTS ####

    # Find crossings of the 5*stride_freq filtered signal with the threshold of 1
    crossings = np.where(np.diff(np.sign((acc_5stride) - 1)) == 2)[0]

    # Ensure crossings are after peaks
    IC_pred = []

    for i, peak in enumerate(FC_pred):

        after_peak_crossings = crossings[[crossings > peak][0]]

        after_peak_crossings = after_peak_crossings[[after_peak_crossings - peak > 25][0]]

        if len(after_peak_crossings) > 0:
            if i < len(FC_pred) - 2:
                if after_peak_crossings[0] < FC_pred[i + 1]:
                    IC_pred.append(after_peak_crossings[0])
            else:
                IC_pred.append(after_peak_crossings[0])
                
    return FC_pred, IC_pred, acc_step, acc_stride, acc_5stride