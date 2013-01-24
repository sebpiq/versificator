# usage: ./example.py /path/to/file1 /path/to/file2 ...
import shout
import sys
import string
import time

import settings
from fileutils import convert_file, write_wav

s = shout.Shout()
print "Using libshout version %s" % shout.version()

s.host = 'localhost'
s.port = settings.icecast['port']
s.password = settings.icecast['password']
s.mount = settings.icecast['mount']
# s.format = 'vorbis'
# s.protocol = 'http'
# s.name = ''
# s.genre = ''
# s.url = ''
# s.public = 1
# s.audio_info = { 'key': 'val', ... }
#  (keys are shout.SHOUT_AI_BITRATE, shout.SHOUT_AI_SAMPLERATE,
#   shout.SHOUT_AI_CHANNELS, shout.SHOUT_AI_QUALITY)

s.open()
#s.set_metadata({'song': 'blabal.ogg'})


def next_frame():
    import math
    phase = 0
    K = 2 * math.pi * 440 / 44100
    global phase, K
    while(True):
        phase += K
        yield math.cos(phase)


while True:
    data_gen = next_frame()
    data = [data_gen.next() for i in range(44100)]
    write_wav('/tmp/temp.wav', data)
    converted_filename = convert_file('/tmp/temp.wav', 'ogg')
    with open(converted_filename) as fd:
        while True:
            buf = fd.read(4096)
            if not buf: break
            s.send(buf)
            s.sync()
f.close()
    

print s.close()
