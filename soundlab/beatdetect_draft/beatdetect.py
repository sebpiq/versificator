import numpy as np
import pylab
from soundlab import *


sound = Sound.from_file('directions.wav')[10:25]
sound.stack_plot('original sound')

spectrum = sound.get_spectrum()
bands = []
for f_start, f_end in [(0, 200)]:#[(0, 200), (200, 400), (400, 800), (800, 1600), (1600, 3200), (3200, 4096)]:

    # Filtering    
    band = spectrum[f_start:f_end]
    filtered_sound = band.get_sound()
    filtered_sound.stack_plot('filtered sound')

    # Full-wave rectifying
    samples = filtered_sound.data.col(0)
    for i, sample in enumerate(samples):
        if samples[i] < 0: samples[i] = -samples[i]

    # convolution
    #window = np.hanning(len(samples) * 2)[len(samples):]
    #filtered_sound = filtered_sound.convolve(window)
    filtered_sound = filtered_sound.smooth()
    filtered_sound.stack_plot('processed sound')

    # Half-wave rectifying
    samples = filtered_sound.data.col(0)
    samples_rectified = []
    for sample in np.diff(samples):
        if sample > 0: samples_rectified.append(sample)
    dataset = DataSet(data=samples_rectified)
    dataset.plot()


        bpms = arange(50, 171, 1)
        energies = []
        for bpm in bpms:
            energies.append(combFilter(bands, bpm, frequency))

    # Time-comb
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
    

"""
  if nargin < 2, acc = 1; end 
  if nargin < 3, minbpm = 60; end
  if nargin < 4, maxbpm = 240; end
  if nargin < 5, bandlimits = [0 200 400 800 1600 3200]; end
  if nargin < 6, maxfreq = 4096; end


  n=length(sig);

  nbands=length(bandlimits);

  % Set the number of pulses in the comb filter
  
  npulses = 3;

  % Get signal in frequency domain

  for i = 1:nbands
    dft(:,i)=fft(sig(:,i));
  end
  
  % Initialize max energy to zero
  
  maxe = 0;
  
  for bpm = minbpm:acc:maxbpm
    
    % Initialize energy and filter to zero(s)
    
    e = 0;
    fil=zeros(n,1);
    
    % Calculate the difference between peaks in the filter for a
    % certain tempo
    
    nstep = floor(120/bpm*maxfreq);

    
    % Set every nstep samples of the filter to one
    
    for a = 0:npulses-1
      fil(a*nstep+1) = 1;
    end
    
    % Get the filter in the frequency domain
    
    dftfil = fft(fil);
    
    % Calculate the energy after convolution
    
    for i = 1:nbands
      x = (abs(dftfil.*dft(:,i))).^2;
      e = e + sum(x);
    end
    
    % If greater than all previous energies, set current bpm to the
    % bpm of the signal
    
    if e > maxe
      sbpm = bpm;
      maxe = e;
    end
  end
  
  output = sbpm;
"""
