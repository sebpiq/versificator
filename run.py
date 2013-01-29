# coding=utf8
# Copyright 2012 - 2013 Sébastien Piquemal <sebpiq@gmail.com>
#
# This file is part of Versificator.
#
# Versificator is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# Versificator is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Versificator.  If not, see <http://www.gnu.org/licenses/>.

import sys
import subprocess
import threading
from Queue import Queue, Empty

from scrapers import SoundScraper


block_size = 1024
sound_queue = Queue()

#SoundScraper.wake_up(3)


class SoundConsumer(threading.Thread):

    def __init__(self, *args, **kwargs):
        super(SoundConsumer, self).__init__(*args, **kwargs)
        self.daemon = True
        self.ices = subprocess.Popen(['ices2', 'ices.xml'], 
            stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)

    def run(self):
        while True:
            data = sound_queue.get()
            self.ices.stdin.write(data)


class SoundProducer(threading.Thread):
    
    def __init__(self, *args, **kwargs):
        super(SoundProducer, self).__init__(*args, **kwargs)
        self.daemon = True

    def run(self):
        import math
        phase = 0
        K = 2 * math.pi * 440 / 44100
        while(True):
            data = []
            for i in range(block_size):
                phase += K
                data.append(math.cos(phase))
            sound_queue.put(data)


consumer = SoundConsumer()
consumer.start()
producer = SoundProducer()
producer.start()

while(True):
    q = Queue()
    try: q.get(True, 30)
    except Empty: pass
