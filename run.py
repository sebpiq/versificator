# usage: ./example.py /path/to/file1 /path/to/file2 ...
import shout
import sys
import string
import time

import settings

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

total = 0
st = time.time()
for fa in sys.argv[1:]:
    print "opening file %s" % fa
    f = open(fa)

    nbuf = f.read(4096)
    while 1:
        buf = nbuf
        nbuf = f.read(4096)
        total = total + len(buf)
        if len(buf) == 0:
            break
        s.send(buf)
        s.sync()
    f.close()
    
    et = time.time()
    br = total*0.008/(et-st)
    print "Sent %d bytes in %d seconds (%f kbps)" % (total, et-st, br)

print s.close()
