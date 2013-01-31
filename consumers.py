import threading
import subprocess
import Queue
import wave

from settings import logger


class BaseConsumer(threading.Thread):

    def __init__(self, *args, **kwargs):
        try:
            self.queue = kwargs.pop('queue')
        except KeyError:
            raise TypeError('Please provide a queue to consume from')
        super(BaseConsumer, self).__init__(*args, **kwargs)
        self.daemon = True
        self.running = True


class IcesConsumer(BaseConsumer):

    def __init__(self, *args, **kwargs):
        super(IcesConsumer, self).__init__(*args, **kwargs)
        self.ices = subprocess.Popen(['ices2', 'ices.xml'], 
            stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)

    def run(self):
        while self.running:
            try:
                data = self.queue.get_nowait()
            except Queue.Empty:
                logger.error('consumer starved')
                try:
                    data = self.queue.get(True, 5)
                except Queue.Empty:
                    pass
                else:
                    self.ices.stdin.write(data)
            else:
                self.ices.stdin.write(data)


class WavFileConsumer(BaseConsumer):

    def __init__(self, *args, **kwargs):
        try:
            self.path = kwargs.pop('path')
        except KeyError:
            raise TypeError('Please provide a path to write to')
        super(WavFileConsumer, self).__init__(*args, **kwargs)

    def run(self):
        self.fd = wave.open(self.path, mode='wb')
        self.fd.setnchannels(2)
        self.fd.setsampwidth(2)
        self.fd.setframerate(44100)
        written = 0
        while self.running:
            try:
                data = self.queue.get(5)
            except Queue.Empty:
                pass
            else:
                written += len(data)
                self.fd.writeframes(data)
        print 'written %s bytes to file' % written
        self.fd.close()
