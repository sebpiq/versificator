import copy
import numpy as np
import pylab
from soundlab import Spectrum, Sound, TimeSpectrum
from __init__ import SoundLabTestCase

class Spectrum_Test(SoundLabTestCase):

    def get_spectrum_test(self):
        t = np.linspace(0, 1, 44100)
        sine_wave = np.sin(2*np.pi*440*t)
        sound = Sound(data=np.array([sine_wave]).transpose(), sample_rate=44100)

        spectrum = sound.get_spectrum()
        maxima = spectrum.maxima(channel=1)
        self.assertEqual(maxima.axes[0], [440])

        spectrum = sound.get_spectrum((400, 500))
        maxima = spectrum.maxima(channel=1)
        self.assertEqual(maxima.axes[0], [440])

    def get_sound_test(self):
        t = np.linspace(0, 0.5, 22050)
        sine_wave = np.sin(2*np.pi*440*t)
        sound = Sound(data=np.array([sine_wave]).transpose(), sample_rate=44100)
        spectrum = sound.get_spectrum()

        # Reconstructing sound wave from spectrum
        reconstructed = spectrum.get_sound()
        pylab.subplot(2, 1, 1)
        pylab.plot(t[:300], sine_wave[:300])
        pylab.subplot(2, 1, 2)
        pylab.plot(reconstructed.axes[0][:300], reconstructed.data[:,0][:300])
        pylab.show()

    def get_time_spectrum_test(self):
        t1 = np.linspace(0, 0.1, 4410)
        sine_wave1 = np.sin(2*np.pi*440*t1)
        t2 = np.linspace(0.1, 0.2, 4410)
        sine_wave2 = np.sin(2*np.pi*220*t2)

        sound_data = np.array([np.hstack((sine_wave1, sine_wave2))]).transpose()
        sine_wave = Sound(data=sound_data, sample_rate=44100)
        time_spectrum = sine_wave.get_time_spectrum(window_size=1024, overlap=0)
        reduced_data = np.vstack((time_spectrum.data[:,4], time_spectrum.data[:,11])).transpose()
        time_spectrum = TimeSpectrum(None, [time_spectrum.f[4], time_spectrum.f[11]],
            data=reduced_data, sample_rate=44100)
        time_spectrum.plot()
