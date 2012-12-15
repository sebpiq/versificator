'''
Created on 04.08.2009

@author: Henning
'''
import numpy
from scipy import *
from scipy.signal import *
from scipy.fftpack import *
import scipy.io.wavfile as wave
import pylab

def bandFilter(signal, bands, maxFreq):
    spectrum = rfft(signal)
      
    n = len(spectrum)
    bandCount = len(bands)
        
    bounds = []
    
    for i in range(bandCount - 1):
        lower = int(float(bands[i]) / float(maxFreq) * n)
        upper = int(float(bands[i + 1]) / float(maxFreq) * n)
        bounds.append([lower, upper])
    bounds.append([int(float(bands[bandCount - 1]) / float(maxFreq) * n), n])
    
    output = [numpy.zeros(n) for i in range(bandCount)]
    
    for i in range(bandCount):
        bound = bounds[i]
        output[i][bound[0]:bound[1]] = irfft(spectrum[bound[0]:bound[1]])
    
    """
    pylab.subplot(211)
    for out in output:
        pylab.plot(out)    
    
    energy = [i.sum() for i in output]
    
    pylab.subplot(212)
    pylab.plot(signal, label="orig")

    for out in output:
        pylab.plot(irfft(out))
        
    pylab.legend()
    """
    
    return output

def rectifyAndSmooth(signals, smoothLength):
    count = len(signals)
    size = len(signals[0])
    window = hanning(smoothLength * 2)[smoothLength:]
    window = numpy.concatenate((window, numpy.zeros(size - smoothLength)))
        
    for i in range(count):
        signals[i] = abs(signals[i])        
        signals[i] = rfft(signals[i])
        signals[i] = signals[i] * window       
        signals[i] = irfft(signals[i])

    return signals

def halfWaveRectify(signals):
    for i in range(len(signals)):
        signals[i] = numpy.clip(signals[i], 0.0, numpy.finfo('f').max)
    return signals

def combFilter(signals, bpm, frequency):
    size = len(signals[0])
    comb = numpy.zeros(size)   
    interval = int((60.0 / bpm) * frequency)
    
    for i in range(0, size, interval):
        comb[i] = 1.0
    comb = rfft(comb)
    
    energies = array([0.0 for i in range(len(signals))])
    
    for i in range(len(signals)):
        conv = signals[i] * comb
        energies[i] = conv.sum()
        
    return energies.sum()

def slicer(signal, windowSize):
    size = len(signal)
    pos = 0
    
    while pos < size:
        slice = signal[pos:pos+windowSize]
        window = blackman(len(slice))
        slice = slice * window
        pos = pos + int(windowSize / 2)
        yield slice

def get_tempo(sound):
    frequency = sound.sample_rate
    samples = sound.mix().data.col(0)

    """
    samples = numpy.zeros(frequency * 20)
    impulses = arange(0, frequency * 20, frequency * 1.0)
    for i in impulses:
        samples[i] = 1.0
    """

    slices = slicer(samples, int(frequency * 2.2))
    slice = slices.next()       
    bands = bandFilter(slice, [0, 200, 400, 800, 1600, 3200], 6400)
            
    """
    pylab.subplot(311)
    for band in bands:
        pylab.plot(band)
    """
    
    bands = rectifyAndSmooth(bands, int(frequency * 0.4))
    
    """
    pylab.subplot(312)
    for band in bands:
        pylab.plot(band)
    """
    
    for i in range(len(bands)):
        bands[i] = numpy.diff(bands[i])
        
    bands = halfWaveRectify(bands)

    """
    pylab.subplot(313)
    for band in bands:
        pylab.plot(band)
    """

    for i in range(len(bands)):
        bands[i] = rfft(bands[i])
    
    bpms = arange(50, 171, 1)
    energies = []
    for bpm in bpms:
        energies.append(combFilter(bands, bpm, frequency))

    return bpms, energies
        
        
    
