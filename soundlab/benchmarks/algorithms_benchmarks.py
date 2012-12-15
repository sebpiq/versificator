import timeit


def fft_vs_goertzel():
    setup_benchmarks = """
import sys, os
sys.path.append(os.path.abspath('..'))

from algorithms import goertzel, fft
import timeit
import numpy as np

SAMPLE_RATE = 44100
WINDOW_SIZE = 1024
t = np.linspace(0, 1, SAMPLE_RATE)[:WINDOW_SIZE]
sine_wave = np.sin(2*np.pi*440*t) + np.sin(2*np.pi*1020*t)
sine_wave = sine_wave * np.hamming(WINDOW_SIZE)
    """
    NUMBER = 1000
    print 'FFT:', timeit.timeit('fft(sine_wave, SAMPLE_RATE)', setup=setup_benchmarks, number=NUMBER)
    print 'Goertzel (many freqs):', timeit.timeit('goertzel(sine_wave, SAMPLE_RATE, (400, 500), (1000, 1100))', setup=setup_benchmarks, number=NUMBER)
    print 'Goertzel (few freqs):', timeit.timeit('goertzel(sine_wave, SAMPLE_RATE, (435, 445), (1015, 1025))', setup=setup_benchmarks, number=NUMBER)


if __name__ == '__main__':
    fft_vs_goertzel()
