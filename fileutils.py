import cStringIO as StringIO
from tempfile import NamedTemporaryFile
import os
import math
import numpy
import wave
import subprocess


def wav_to_string(data):
    data = numpy.array(data, dtype=numpy.float32) * (2**15 - 0.5)
    return data.astype(numpy.uint16).tostring()
    

def write_wav(f, data):
    data = wav_to_string(data)
    fd = wave.open(f, mode='wb')
    fd.setnchannels(1)
    fd.setsampwidth(2)
    fd.setframerate(44100)
    fd.writeframes(data)


def read_wav(f, start=None, end=None):
    # TODO: Test with 8-bit wavs ?
    # TODO: the file might be very big, so this should be lazy
    # If the file is not .wav, we need to convert it

    # Reading the data from the converted file
    raw = wave.open(f, 'rb')

    channels = raw.getnchannels()
    sample_width = raw.getsampwidth()       # Sample width in byte
    if sample_width == 1: np_type = 'uint8'
    elif sample_width == 2: np_type = 'uint16'
    else: raise ValueError('Wave format not supported')
    frame_rate = raw.getframerate()         
    frame_width = channels * sample_width

    if start is None: start = 0
    start_frame = start * frame_rate
    if end is None: end_frame = raw.getnframes()
    else: end_frame = end * frame_rate
    frame_count = end_frame - start_frame
    sample_count = frame_count * channels

    raw.setpos(int(start_frame))
    data = raw.readframes(int(frame_count))
    data = numpy.fromstring(data, dtype=np_type)
    data = data.reshape([frame_count, channels])

    return data


def convert_file(filename, to_format, to_filename=None):
    """
    Returns None if the file is already of the desired format.
    """
    fileformat = guess_fileformat(filename)
    if fileformat == to_format:
        if to_filename:
            shutil.copy(filename, to_filename)
            return to_filename
        else:
            return filename

    # Copying source file to a temporary file
    # TODO: why copying ?
    origin_file = NamedTemporaryFile(mode='wb', delete=True)
    with open(filename, 'r') as fd:
        while True:
            copy_buffer = fd.read(1024*1024)
            if copy_buffer: origin_file.write(copy_buffer)
            else: break
    origin_file.flush()

    # Converting the file to wav
    if to_filename is None:
        dest_file = NamedTemporaryFile(mode='rb', delete=False)
        to_filename = dest_file.name
    avconv_call = ['avconv', '-y',
                    '-f', fileformat,
                    '-i', origin_file.name,  # input options (filename last)
                    '-vn',  # Drop any video streams if there are any
                    '-f', to_format,  # output options (filename last)
                    to_filename
                  ]
    subprocess.check_call(avconv_call, stdout=open(os.devnull,'w'), stderr=open(os.devnull,'w'))
    origin_file.close()
    return to_filename


class OggEncoder(object):
    
    def __init__(self):
        #self._in = file()
        self._out = StringIO.StringIO()
        self.oggenc = subprocess.Popen(['oggenc', '-', '-r', '-C', '1', '-B', '16', '-R', '44100'],
                        stdout=subprocess.PIPE,
                                    stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
        
    def encode(self, data):
        import time
        data = StringIO.StringIO(wav_to_string(data))
        out = ''
        print self.oggenc.poll()
        while True:
            stdin_data = data.read(64)
            if not stdin_data: break
            print stdin_data
            stdout_data, stderr_data = self.oggenc.communicate(input=stdin_data)
            #time.sleep(1)
            print 'read %s bytes' % len(stdout_data)
            print self.oggenc.poll()
            out += stdout_data
        return out


def guess_fileformat(filename):
    # Get the format of the file
    try:
        return filename.split('.')[-1]
    except IndexError:
        raise ValueError('unknown file format')


if __name__ == '__main__':
    import math
    phase = 0
    K = 2 * math.pi * 440 / 44100
    def next_frame():
        global phase, K
        while(True):
            phase += K
            yield math.cos(phase)
    data_gen = next_frame()
    data = [data_gen.next() for i in range(44100)]

    write_wav('test.wav', data)

    enc = OggEncoder()
    encoded = enc.encode(data)
    print len(encoded)
    with open('test.ogg', 'wb') as fd:
        fd.write(encoded)
