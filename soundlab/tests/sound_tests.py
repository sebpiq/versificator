import copy
import os
import numpy as np
import scipy
from soundlab import Sound, TimeSpectrum
from __init__ import SoundLabTestCase

dirname = os.path.dirname(__file__)

class Sound_Test(SoundLabTestCase):

    def init_test(self):
        sound = Sound(data=[[1], [2], [3]])
        self.assertEqual(sound.channel_count, 1)
        sound = Sound(data=[[1, 4], [2, 5], [3, 6]])
        self.assertEqual(sound.channel_count, 2)

    def from_file_test(self):
        sound = Sound.from_file(os.path.join(dirname, 'A440_mono.wav'))
        self.assertEqual(sound.channel_count, 1)
        self.assertEqual(sound.sample_rate, 44100)
        self.assertEqual(sound.sample_count, 441)

        sound = Sound.from_file(os.path.join(dirname, 'A440_stereo.wav'))
        self.assertEqual(sound.channel_count, 2)
        self.assertEqual(sound.sample_rate, 44100)
        self.assertEqual(sound.sample_count, 441)

        sound = Sound.from_file(os.path.join(dirname, 'A440_mono.mp3'))
        self.assertEqual(sound.channel_count, 1)
        self.assertEqual(sound.sample_rate, 44100)
        self.assertTrue(sound.sample_count > 44100 and sound.sample_count < 50000)

    def mix_test(self):
        sound = Sound(data=[[1, 0.5, 0.5], [2, 0.4, 0.4], [3, 0.3, 0.3], [4, 0.2, 0.2], [5, 0.1, 0.1], [6, 0, 0], [7, -0.1, -0.1], [8, -0.2, -0.2]], sample_rate=2)
        mixed = sound.mix()
        self.assertEqual(np.round(mixed.data, 4), np.round([[2.0], [2.8], [3.6], [4.4], [5.2], [6.0], [6.8], [7.6]], 4))

        sound = Sound(data=[[1], [2], [3], [4], [5], [6], [7], [8]], sample_rate=2)
        mixed = sound.mix()
        self.assertEqual(mixed.data, [[1], [2], [3], [4], [5], [6], [7], [8]])
