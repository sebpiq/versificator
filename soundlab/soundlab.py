from tempfile import NamedTemporaryFile
import math
import subprocess
import os
import pylab
import numpy as np
from scipy import pi
from scipy.io import wavfile
import algorithms as algos


# Common slices
SLC_ALL = slice(None, None)


class DataHolder(np.ndarray):
    # TODO: generalize for n-dimensions

    def __new__(cls, input_array, info=None):
        obj = np.asarray(input_array).view(cls)
        obj.info = info
        return obj

    def __array_finalize__(self, obj):
        pass

    def col(self, ind):
        return self[:,ind]

    def to_col(self, ind):
        return self[:, ind:ind + 1]

    def iter_columns(self):
        return iter(self.transpose())


class DataSet(object):
    # TODO: couldn't this be a ndarray ?

    dimensions = ['x']

    def __init__(self, *axes, **kwargs):
        # TODO: axes also accepts a dict
        # Handling data, validating its shape
        data = np.array(kwargs.get('data', []))
        if len(data.shape) != len(self.dimensions):
            raise ValueError('data must have %s dimensions.' % len(self.dimensions))
        self._data = data
        self._vdata = None

        # Handling axes, validating them or putting a default axis
        if len(axes) > len(self.dimensions):
            raise TypeError('you provided too much axes')
        self.axes = []
        # Remembering the axes initially passed to __init__
        self._user_axes = [None] * len(self.dimensions)
        for i, axis in enumerate(axes):
            self._user_axes[i] = axis
            if axis is None: axis = np.arange(0, self._data.shape[i])
            else:
                axis = np.array(axis)
                if len(axis.shape) != 1:
                    raise ValueError('axes must have only one dimension')
                if (self._data.shape[i] != axis.size):
                    raise ValueError('axis must contain as many values as the corresponding data dimension')
            self.axes.append(axis)
        while (len(self.axes) != len(self.dimensions)):
            axis = np.arange(0, self._data.shape[len(self.axes)])
            self.axes.append(axis)

    def __getitem__(self, key):
        # TODO: supports slice syntax [] only on first axis
        if isinstance(key, slice):
            return self.slice(start=key.start, end=key.stop, dimension=0)
        else:
            return self.slice(start=key, dimension=0).data[0]

    def __copy__(self, *axes, **kwargs):
        axes = kwargs.get('axes', {})
        data = kwargs.get('data', None)
        if data is None:
            copy_data = np.copy(self._data)
        else:
            copy_data = data
        copy_kwargs = {'data': copy_data}
        copy_kwargs.update(kwargs)
        new_axes = self._user_axes[:]
        for i, axis in axes.items(): new_axes[i] = axis
        return self.__class__(*new_axes, **copy_kwargs)

    @property
    def data(self):
        return self._get_data()

    def _get_data(self):
        # TODO: cache ?
        if not self._vdata is None:
            return DataHolder(np.hstack((self._data, self._vdata)))
        else:
            return DataHolder(self._data)

    def sort(self, key, dimension=0):
        axis = self.axes[dimension]
        axes_and_data = np.concatenate((axis, self._data), axis=dimension)
        #def _sort()

    def slice(self, start=None, end=None, dimension=0):
        # TODO: should this keep the offset in 'dimensions' or not ?
        axis = self.axes[dimension]
        start = start or axis.min()
        end = end or axis.max() + 1

        # We find the mask to apply to the data to filter what we don't want,
        # then we put `dimension` as 0, slice, and swap dimensions back.
        mask = (axis >= start) * (axis < end)
        data = self._data
        if dimension != 0: data = data.swapaxes(0, dimension)
        data = data[mask,]
        if dimension != 0: data = data.swapaxes(dimension, 0)
        return self.__copy__(axes={dimension: axis[mask,]}, data=data)

    def sample_slice(self, start=None, end=None, dimension=0):
        if start is None: start = 0
        if end is None: end = self.sample_count
        data = self._data
        if dimension != 0: data = data.swapaxes(dimension, 0)
        data = data[start:end]
        if dimension != 0: data = data.swapaxes(0, dimension)
        return self.__copy__(axes={dimension: self.axes[dimension][start:end]}, data=data)

    def iter_frames(self):
        data = np.vstack(([self.axes[0]], self._data))
        for i in range(0, data.shape[1]):
            yield data[:,i]

    def maxima(self, channel=0, take_edges=True):
        x = self.axes[0]
        if len(self.dimensions) == 1:
            y = self.data
        else:
            y = self.data.col(channel)
        max_x, max_y = algos.maxima(x, y, take_edges=take_edges)
        return DataSet(max_x, data=max_y)

    def minima(self, channel=0, take_edges=True):
        x = self.axes[0]
        if len(self.dimensions) == 1:
            y = self.data
        else:
            y = self.data.col(channel)
        min_x, min_y = algos.minima(x, y, take_edges=take_edges)
        return DataSet(min_x, data=min_y)

    def convolve(self, array, dimension=0):
        # TODO : works only for 2 dims
        convolved = np.convolve(self.data.col(0), array, mode='same')
        return self.__copy__(data=np.array([convolved]).transpose())

    def smooth(self, window_size=11, window='hanning'):
        """
        smooth the data using a window with requested size.
        
        This method is based on the convolution of a scaled window with the signal.
        The signal is prepared by introducing reflected copies of the signal 
        (with the window size) in both ends so that transient parts are minimized
        in the begining and end part of the output signal.
        
        input:
            data: the input signal `data(x, V)`
            window_size: the dimension of the smoothing window; should be an odd integer
            window: the type of window from 'flat', 'hanning', 'hamming', 'bartlett', 'blackman'
                flat window will produce a moving average smoothing.

        output:
            the smoothed signal `data(x, V)`
     
        TODO: the window parameter could be the window itself if an array instead of a string
        NOTE: length(output) != length(input), to correct this: return y[(window_size/2-1):-(window_size/2)] instead of just y.
        """
        # TODO: move to algorithms.py
        # TODO: only work for 2 dimensions. Does it make sense for more ?
        if hasattr(self, 'sample_count') and self.sample_count < window_size:
            raise ValueError('sample count of the sound needs to be bigger than window size.')

        if window_size < 3:
            return self.__copy__()

        if len(self.dimensions) == 2: all_data = self._data.transpose()
        elif len(self.dimensions) == 1: all_data = [self.data]

        final_data = []
        for data in all_data:
            if not window in ['flat', 'hanning', 'hamming', 'bartlett', 'blackman']:
                raise ValueError, "Window is on of 'flat', 'hanning', 'hamming', 'bartlett', 'blackman'"

            s = np.r_[data[window_size-1:0:-1], data, data[-1:-window_size:-1]]

            if window == 'flat': # moving average
                w = np.ones(window_size,'d')
            else:
                w = getattr(np, window)(window_size)

            smoothed = np.convolve(w/w.sum(), s, mode='valid')
            smoothed = smoothed[math.floor(window_size/2.0)-1:-math.ceil(window_size/2.0)] # To have `length(output) == length(input)`
            final_data.append(smoothed)

        if len(self.dimensions) == 2:
            return self.__copy__(data=np.array(final_data).transpose())
        elif len(self.dimensions) == 1:
            return self.__copy__(data=final_data[0])
        

    def plot(self, title=None, channel=None):
        """
        Plots all channels.
        """
        x = self.axes[0]
        kwargs = {'title': title}
        if len(self.dimensions) == 1:
            self._datasets_to_plot.append(((x, self.data, kwargs),))
        else:
            if not channel is None:
                self._datasets_to_plot.append(((x, self.data.col(channel), kwargs),))
            else:
                for channel in self.data.iter_columns():
                    self._datasets_to_plot.append(((x, channel, kwargs),))
        self.__class__.plot_stacked()

    def stack_plot(self, title=None, channel=0):
        if len(self.dimensions) == 1:
            y = self.data
        else:
            y = self.data.col(channel)
        self._datasets_to_plot.append(((self.axes[0], y, {'title': title}),))

    @classmethod
    def plot_stacked(cls):
        for i, plot_data in enumerate(cls._datasets_to_plot):
            pylab.subplot(len(cls._datasets_to_plot), 1, i+1)
            for x, y, kwargs in plot_data:
                title = kwargs.pop('title', None)
                if title: pylab.title(title)
                pylab.plot(x, y, '-', **kwargs)
        pylab.show()
        DataSet._datasets_to_plot = []
    _datasets_to_plot = []


class SampledDataSet(DataSet):
    
    dimensions = ['x', 'y']

    def __init__(self, *axes, **kwargs):
        self.sample_rate = kwargs.pop('sample_rate', None)
        # TODO: distortion when calculating `x` ? Because of approximation ?
        #if len(axes) == 0 or axes[0] is None: replace
        super(SampledDataSet, self).__init__(*axes, **kwargs)
        # If the user didn't provide an axis, we build it automatically with the sample rate
        if self._user_axes[0] is None: self.axes[0] = np.arange(self.sample_count) / float(self.sample_rate)

    @property
    def sample_count(self):
        """
        Returns the number of samples in the sound.
        """
        return self._data.shape[0]

    def __copy__(self, *axes, **kwargs):
        kwargs.setdefault('sample_rate', self.sample_rate)
        return super(SampledDataSet, self).__copy__(*axes, **kwargs) 


class Sound(SampledDataSet):

    dimensions = ['t', 'channel']

    def __init__(self, *axes, **kwargs):
        kwargs.setdefault('sample_rate', 44100)
        super(Sound, self).__init__(*axes, **kwargs)

    @property
    def t(self):
        return self.axes[0]

    @property
    def channel_count(self):
        return self._data.shape[1]

    @property
    def length(self):
        """
        Returns the sound length in seconds.
        """
        # The first sample is at `x = 0`, so we take `samp_count - 1`
        return (self.sample_count - 1) / float(self.sample_rate)

    @classmethod
    def from_file(cls, filename, fileformat=None):
        # TODO: the file might be very big, so this shoud be lazy
        # Get the format of the file
        try:
            fileformat = filename.split('.')[-1]
        except IndexError:
            raise ValueError('unknown file format')

        # If the file is not .wav, we need to convert it
        if fileformat != 'wav':

            # Copying source file to a temporary file
            origin_file = NamedTemporaryFile(mode='wb', delete=False)
            with open(filename, 'r') as fd:
                while True:
                    copy_buffer = fd.read(1024*1024)
                    if copy_buffer: origin_file.write(copy_buffer)
                    else: break
            origin_file.flush()

            # Converting the file to wav
            dest_file = NamedTemporaryFile(mode='rb', delete=False)
            ffmpeg_call = ['ffmpeg', '-y',
                            '-f', fileformat,
                            '-i', origin_file.name,  # input options (filename last)
                            '-vn',  # Drop any video streams if there are any
                            '-f', 'wav',  # output options (filename last)
                            dest_file.name
                          ]
            subprocess.check_call(ffmpeg_call, stdout=open(os.devnull,'w'), stderr=open(os.devnull,'w'))
            filename = dest_file.name

            # Closing file descriptors, removing files
            origin_file.close()
            os.unlink(origin_file.name)

        # Finally create sound 
        sample_rate, data = wavfile.read(filename)
        if len(data.shape) == 1:
            data = np.array([data]).transpose()
        sound = cls(data=data, sample_rate=sample_rate, channels=data.shape[0])

        # Cleaning
        if fileformat != 'wav':
            dest_file.close()
            os.unlink(dest_file.name)

        return sound

    def to_file(self, filename):
        wavfile.write(filename, self.sample_rate, self._data.astype(np.int16))

    def mix(self):
        if self.channel_count == 1: return self.__copy__()
        mixed = np.zeros(self.sample_count)
        for channel in self.data.iter_columns():
            mixed += channel
        return self.__copy__(data=np.array([mixed]).transpose())

    def get_spectrum(self, *freq_ranges):
        """
        Returns the spectrum of the signal `data(x, v)`. Negative spectrum is removed.
        """
        mixed_sound = self.mix()
        if len(freq_ranges) == 0:
            freqs, results = algos.fft(mixed_sound.data.col(0), self.sample_rate)
            f_sample_rate = 1.0 / (freqs[1] - freqs[0])
            return Spectrum(freqs, data=np.array([results]).transpose(), sample_rate=f_sample_rate)
        else:
            freqs, results = algos.goertzel(mixed_sound.data.col(0), self.sample_rate, *freq_ranges)
            return Spectrum(freqs, data=np.array([results]).transpose())

    def get_time_spectrum(self, *freq_ranges, **kwargs):
        window_size = kwargs.get('window_size', 256)
        overlap = kwargs.get('overlap', 16)
        if overlap > window_size: raise ValueError('overlap must be less than window size')
        start = 0
        end = window_size
        offset = 0
        # Rows are t, columns are f
        all_time_spectrum = np.array([])
        while(end < self.sample_count):
            sound_slice = self.sample_slice(start=start, end=end)
            spectrum = sound_slice.get_spectrum(*freq_ranges)
            start = end - overlap
            end = start + window_size
            # Builds the data freq/time/amplitude for this window :
            # we basically copy the frequency data over all time samples on `window - overlap`.
            window_time_spectrum = np.tile(spectrum.data.col(1), (window_size - overlap, 1))
            # Concatenate with previous data.
            if not all_time_spectrum.size: vstack_data = (window_time_spectrum,)
            else: vstack_data = (all_time_spectrum, window_time_spectrum)
            all_time_spectrum = np.vstack(vstack_data)
        time_spectrum = TimeSpectrum(None, spectrum.axes[0], data=all_time_spectrum, sample_rate=self.sample_rate)
        return time_spectrum


class Spectrum(SampledDataSet):
    
    dimensions = ['f', 'amplitude/phase']

    def __init__(self, *axes, **kwargs):
        super(Spectrum, self).__init__(*axes, **kwargs)
        if self._data.shape[1] != 1:
            raise ValueError('Spectrum just needs one set of complex data.')
        # Calculate amplitude and phase data
        complex_data = self.data.to_col(0)
        amplitudes = algos.get_ft_amplitude_array(complex_data)
        phases = algos.get_ft_phase_array(complex_data)
        self._vdata = np.hstack((amplitudes, phases))

    @property
    def f(self):
        return self.axes[0]

    def get_sound(self):
        """
        Performs inverse FFT to reconstruct a sound from this spectrum.
        """
        times, results = algos.ifft(self.data.col(0), 1.0 / self.sample_rate)
        sample_rate = 2 * (self.sample_count - 1) / self.sample_rate
        return Sound(data=np.array([results]).transpose(), sample_rate=sample_rate)


class TimeSpectrum(SampledDataSet):
    
    dimensions = ['t', 'f']

    @property
    def t(self):
        return self.axes[0]

    @property
    def f(self):
        return self.axes[1]

    def plot(self):
        """
        Plots all channels.
        """
        t = self.axes[0]
        to_plot = []
        for i, f_data in enumerate(self.data.iter_columns()):
            to_plot.append((t, f_data, dict(label='%s' % self.f[i])))
        self._datasets_to_plot.append(to_plot)
        pylab.legend(loc='lower left')
        self.__class__.plot_stacked()

