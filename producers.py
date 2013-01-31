import threading
import Queue
import math
import random

from pychedelic.utils.files import samples_to_string
from pychedelic import Sound

import settings


class BaseProducer(threading.Thread):

    def __init__(self, *args, **kwargs):
        try:
            self.queue = kwargs.pop('queue')
        except KeyError:
            raise TypeError('Please provide a queue to write data to')
        super(BaseProducer, self).__init__(*args, **kwargs)
        self.daemon = True
        self.running = True


class VersProducer(BaseProducer):

    def run(self):
        loops = []
        db_loops = list(settings.db.loops.find())
        for i in range(3):
            loop = random.choice(db_loops)
            loop = Sound.from_file(loop['path'],
                start=loop['start'], end=loop['start'] + loop['duration'])
            loop = loop.fade(in_dur=0.003, out_dur=0.003)
            loops.append(loop)

        print 'start generating'
        written = 0
        while self.running:
            if written > 4 * 4410000: break
            pattern = self.get_pattern()
            sequence = pattern * random.randint(4, 8)
            for loop_ind in sequence:
                loop = loops[loop_ind]
                for data in loop.iter_raw(1024):
                    self.queue.put(data)
                    written += len(data)
        print 'produced %s bytes' % written
                
    def get_pattern(self):
        return [random.randint(0, 2) for i in range(random.randint(3, 6))]


class OscProducer(BaseProducer):

    def run(self):
        phase = 0
        K = 2 * math.pi * 440 / 44100
        while self.running:
            data = []
            for i in range(block_size):
                phase += K
                data.append(math.cos(phase))
            self.queue.put(samples_to_string(np.array(data, dtype=np.float32)))
