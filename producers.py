import threading
import Queue

from pychedelic.utils.files import samples_to_string

from settings import logger, db


class BaseProducer(threading.Thread):

    def __init__(self, *args, **kwargs):
        try:
            self.queue = kwargs.pop('queue')
        except KeyError:
            raise TypeError('Please provide a queue to write data to')
        super(BaseProducer, self).__init__(*args, **kwargs)
        self.daemon = True
        self.running = True


class SoundProducer(BaseProducer):

    def run(self):
        import math
        phase = 0
        K = 2 * math.pi * 440 / 44100
        while self.running:
            data = []
            for i in range(block_size):
                phase += K
                data.append(math.cos(phase))
            sound_queue.put(samples_to_string(np.array(data, dtype=np.float32)))
