from unittest import TestCase
from scrapers import AudioQuantum


class AudioQuantum_Test(TestCase):

    def comparison_test(self):
        self.assertTrue(AudioQuantum(start=3, duration=7) < AudioQuantum(start=0.1, duration=10))
        self.assertTrue(AudioQuantum(start=0.1, duration=7) < AudioQuantum(start=0.1, duration=10))
        self.assertTrue(AudioQuantum(start=0.5, duration=1) < AudioQuantum(start=0.1, duration=10))
        self.assertTrue(AudioQuantum(start=0.1, duration=10) <= AudioQuantum(start=0.1, duration=10))

        self.assertFalse(AudioQuantum(start=0, duration=1) < AudioQuantum(start=0.1, duration=10))
        self.assertFalse(AudioQuantum(start=11.8, duration=1.9) < AudioQuantum(start=0.1, duration=10))
        self.assertFalse(AudioQuantum(start=11.8, duration=1.9) <= AudioQuantum(start=0.1, duration=10))
        self.assertFalse(AudioQuantum(start=0.1, duration=10) < AudioQuantum(start=0.1, duration=10))

    def overlap_test(self):
        self.assertTrue(AudioQuantum(start=0.1, duration=10).overlap(AudioQuantum(start=3, duration=7)))
        self.assertTrue(AudioQuantum(start=0.1, duration=10).overlap(AudioQuantum(start=0.1, duration=7)))
        self.assertTrue(AudioQuantum(start=0.1, duration=10).overlap(AudioQuantum(start=0.5, duration=1)))
        self.assertTrue(AudioQuantum(start=0.1, duration=10).overlap(AudioQuantum(start=0, duration=1)))
        self.assertTrue(AudioQuantum(start=0.1, duration=10).overlap(AudioQuantum(start=0.1, duration=10)))
        self.assertTrue(AudioQuantum(start=0.1, duration=10).overlap(AudioQuantum(start=0.1, duration=10)))
        self.assertTrue(AudioQuantum(start=10.99, duration=5.6).overlap(AudioQuantum(start=10.99, duration=5.6)))
        self.assertTrue(AudioQuantum(start=10.99, duration=5.6).overlap(AudioQuantum(start=10.99, duration=5.6)))

        self.assertFalse(AudioQuantum(start=0.1, duration=10).overlap(AudioQuantum(start=11.8, duration=1.9)))
        self.assertFalse(AudioQuantum(start=0.01, duration=0.0115).overlap(AudioQuantum(start=0.1, duration=10)))
