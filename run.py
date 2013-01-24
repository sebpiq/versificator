import sys
import subprocess

import settings
from fileutils import wav_to_string


def next_frame():
    import math
    phase = 0
    K = 2 * math.pi * 440 / 44100
    while(True):
        phase += K
        yield math.cos(phase)


ices2 = subprocess.Popen(['ices2', 'ices.xml'], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)

while True:
    data_gen = next_frame()
    data = [data_gen.next() for i in range(4410)]
    data = wav_to_string(data)
    ices2.stdin.write(data)
    
    print 'written'
    
