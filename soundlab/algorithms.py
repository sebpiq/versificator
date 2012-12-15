import math
import numpy as np


def fft(samples, sample_rate):
    """
    Performs the FFT of a real, 1-dimension signal.
    """
    f_results = np.fft.fftfreq(len(samples), 1.0 / sample_rate)
    f_results = f_results[:len(f_results)/2 + 1]
    f_results[-1] = -f_results[-1] # Because last term is -Nyquist f
    results = np.fft.rfft(samples)
    return f_results, results


def ifft(samples, sample_rate):
    """
    Performs the inverse FFT of the spectrum of a real 1-dimension signal (when in time domain).
    """
    results = np.fft.irfft(samples)
    t_results = np.arange(0, (len(samples) - 1) * 2) * 1.0 / sample_rate
    return t_results, results


def goertzel(samples, sample_rate, *freqs):
    """
    Implementation of the Goertzel algorithm, useful for calculating individual
    terms of a discrete Fourier transform.

    `samples` is a windowed one-dimensional signal originally sampled at `sample_rate`.
 inverse_tan(b(n)/a(n))
    The function returns 2 arrays, one containing the actual frequencies calculated,
    the second the coefficients `(real part, imag part, power)` for each of those frequencies.
    For simple spectral analysis, the power is usually enough.

    Example of usage :
        
        # calculating frequencies in ranges [400, 500] and [1000, 1100]
        # of a windowed signal sampled at 44100 Hz
        freqs, results = goertzel(some_samples, 44100, (400, 500), (1000, 1100))
    """
    if isinstance(samples, np.ndarray): samples = samples.tolist() # We need simple list, no numpy.array
    window_size = len(samples)
    f_step = sample_rate / float(window_size)
    f_step_normalized = 1.0 / window_size

    # Calculate all the DFT bins we have to compute to include frequencies
    # in `freqs`.
    bins = set()
    for f_range in freqs:
        f_start, f_end = f_range
        k_start = int(math.floor(f_start / f_step))
        k_end = int(math.ceil(f_end / f_step))

        if k_end > window_size - 1: raise ValueError('frequency out of range %s' % k_end)
        bins = bins.union(range(k_start, k_end))

    # For all the bins, calculate the DFT term
    n_range = range(0, window_size)
    f_results = []
    results = []
    for k in bins:

        # Bin frequency and coefficients for the computation
        f = k * f_step_normalized
        w_real = 2.0 * math.cos(2.0 * math.pi * f)
        w_imag = math.sin(2.0 * math.pi * f)

        # Doing the calculation on the whole sample
        d1, d2 = 0.0, 0.0
        for n in n_range:
            y  = samples[n] + w_real * d1 - d2
            d2, d1 = d1, y

        # Storing results `(complex result, amplitude, phase)`
        results.append(complex(0.5 * w_real * d1 - d2, w_imag * d1))
        f_results.append(f * sample_rate)
    return np.array(f_results), np.array(results)


def get_ft_phase(term):
    """
    """
    return math.atan2(term.imag / term.real)


def get_ft_amplitude(term):
    """
    """
    return abs(term)


def get_ft_phase_array(array):
    """
    """
    return np.arctan2(np.imag(array), np.real(array)).astype(float)


def get_ft_amplitude_array(array):
    """
    """
    return np.absolute(array).astype(float)


def maxima(x, y, take_edges=True):
    cond1 = lambda grad: grad > 0
    cond2 = lambda grad: grad < 0
    return _extrema(x, y, cond1, cond2, take_edges=take_edges)


def minima(x, y, take_edges=True):
    cond1 = lambda grad: grad < 0
    cond2 = lambda grad: grad > 0
    return _extrema(x, y, cond1, cond2, take_edges=take_edges)


def _extrema(x, y, cond1, cond2, take_edges=True):
    # Preparing data and factorized functions
    gradients = np.diff(y, axis=0)
    extrema_x = []
    extrema_y = []
    def extremum_found(ind):
        extrema_x.append(x[ind])
        extrema_y.append(y[ind])
    def gradient0_found(ind):
        j = ind + 1
        while j < len(gradients) - 2 and gradients[j] == 0: j += 1
        if j >= len(gradients) - 1 or cond2(gradients[j]): extremum_found(ind)

    # Handling lower edge
    if (take_edges and cond2(gradients[0])): extremum_found(0)
    if gradients[0] == 0: gradient0_found(0)

    # In the middle
    for i, grad in enumerate(gradients[:-1]):
        if cond1(grad):
            # i + 1, because we need `diff[i]` is `y[i+1] - y[i]`
            if cond2(gradients[i+1]): extremum_found(i+1)
            elif gradients[i+1] == 0: gradient0_found(i+1)

    # Handling upper edge         
    if take_edges and cond1(gradients[-1]): extremum_found(-1)

    # Return
    return extrema_x, extrema_y


def optimize_windowsize(n):
    orig_n = n
    while True:
        n = orig_n
        while (n % 2) == 0: n /= 2
        while (n % 3) == 0: n /= 3
        while (n % 5) == 0: n /= 5
        if n < 2: break
        orig_n += 1
    return orig_n


def paulstretch(samples, samplerate, stretch, windowsize_seconds=0.25, onset_level=0.5):
    """
    stretch amount (1.0 = no stretch)
    window size (seconds)
    onset sensitivity (0.0=max,1.0=min)

    This is Paulstretch , Python version
    by Nasca Octavian PAUL, Targu Mures, Romania
    https://github.com/paulnasca/paulstretch_python

    Original version with GUI: 
    http://hypermammut.sourceforge.net/paulstretch/
    """
    stretched_sig = np.array([])
    samples = np.copy(samples)

    # make sure that windowsize is even and larger than 16
    windowsize = int(windowsize_seconds * samplerate)
    windowsize = max(16, windowsize)
    windowsize = optimize_windowsize(windowsize)
    windowsize = int(windowsize / 2) * 2
    half_windowsize = int(windowsize / 2)

    # correct the end of `samples`
    nsamples = samples.size
    end_size = min(int(nsamples * 0.5), int(samplerate * 0.05))
    if end_size < 16: end_size = 16
    samples[nsamples-end_size:nsamples] *= np.linspace(1, 0, end_size)

    
    # compute the displacement inside the input file
    start_pos = 0.0
    displace_pos = windowsize * 0.5

    #create Hann window
    window = 0.5 - np.cos(np.arange(windowsize, dtype='float') * 2.0 * np.pi / (windowsize - 1)) * 0.5

    old_windowed_buf = np.zeros(windowsize)
    hinv_sqrt2 = (1 + np.sqrt(0.5)) * 0.5
    hinv_buf = 2.0 * (hinv_sqrt2 - (1.0 - hinv_sqrt2) * np.cos(np.arange(half_windowsize,dtype='float') * 2.0 * np.pi / half_windowsize)) / hinv_sqrt2

    freqs = np.zeros(half_windowsize + 1)
    old_freqs = freqs

    num_bins_scaled_freq = 32
    freqs_scaled = np.zeros(num_bins_scaled_freq)
    old_freqs_scaled = freqs_scaled

    displace_tick = 0.0
    displace_tick_increase = 1.0 / stretch
    if displace_tick_increase > 1.0: displace_tick_increase = 1.0
    extra_onset_time_credit = 0.0
    get_next_buf = True
    while True:
        if get_next_buf:
            old_freqs = freqs
            old_freqs_scaled = freqs_scaled

            # get the windowed buffer
            istart_pos = int(np.floor(start_pos))
            buf = samples[istart_pos:istart_pos+windowsize]
            if buf.size < windowsize:
                buf = np.append(buf, np.zeros(windowsize - buf.size), 1)
            buf = buf * window
    
            # get the amplitudes of the frequency components and discard the phases
            freqs = abs(np.fft.rfft(buf))

            # scale down the spectrum to detect onsets
            # basically, this groups the amplitudes into `num_bins_scaled_freq` bins, and calculate
            # for each bin the average amplitude.
            freqs_len = freqs.size
            if num_bins_scaled_freq < freqs_len:
                freqs_len_div = freqs_len // num_bins_scaled_freq
                new_freqs_len = freqs_len_div * num_bins_scaled_freq
                freqs_scaled = np.mean(np.array([freqs[:new_freqs_len]]).reshape([num_bins_scaled_freq, freqs_len_div]), 1)
            else:
                freqs_scaled = np.zeros(num_bins_scaled_freq)

            # process onsets
            m = 2.0 * np.mean(freqs_scaled - old_freqs_scaled) / (np.mean(abs(old_freqs_scaled)) + 1e-3)
            if m < 0.0: m = 0.0
            if m > 1.0: m = 1.0
            if m > onset_level:
                displace_tick = 1.0
                extra_onset_time_credit += 1.0

        cfreqs = (freqs * displace_tick) + (old_freqs * (1.0 - displace_tick))

        # randomize the phases by multiplication with a random complex number with modulus=1
        ph = np.random.uniform(0, 2 * np.pi, cfreqs.size) * 1j
        cfreqs = cfreqs * np.exp(ph)

        # do the inverse FFT 
        buf = np.fft.irfft(cfreqs)

        # window again the output buffer
        buf *= window

        # overlap-add the output
        output = buf[:half_windowsize] + old_windowed_buf[half_windowsize:windowsize]
        old_windowed_buf = buf

        # remove the resulted amplitude modulation
        output *= hinv_buf
        
        # clamp the values to -1..1 
        #output[output > 1.0] = 1.0
        #output[output < -1.0] = -1.0

        # write the output to wav file
        stretched_sig = np.hstack((stretched_sig, output))

        if get_next_buf: start_pos += displace_pos
        get_next_buf = False

        if start_pos >= nsamples: break
        
        if extra_onset_time_credit <= 0.0:
            displace_tick += displace_tick_increase
        else:
            credit_get = 0.5 * displace_tick_increase #this must be less than displace_tick_increase
            extra_onset_time_credit -= credit_get
            if extra_onset_time_credit < 0:
                extra_onset_time_credit = 0
            displace_tick += displace_tick_increase - credit_get

        if displace_tick >= 1.0:
            displace_tick = displace_tick % 1.0
            get_next_buf = True

    ampl = np.max(stretched_sig) - np.min(stretched_sig)
    return np.int16(stretched_sig / ampl * 32767.0)
    
