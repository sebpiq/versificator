import threading
import math
from tempfile import NamedTemporaryFile
from Queue import Queue
from unittest import TestCase
import numpy as np
from pychedelic import Sound

from consumers import WavFileConsumer
from __init__ import VersTestCase


class WavFileConsumer_Test(VersTestCase):

    def write_to_file_test(self):
        # Create the queue and write data to it
        queue = Queue(maxsize=10)
        samples = np.array([(i % 10)/10.0 for i in range(100)])
        samples = samples.reshape((100, 1))
        sound = Sound(samples, sample_rate=44100)
        for data in sound.iter_raw(10):
            queue.put(data)
        self.assertEqual(queue.qsize(), 10)

        # Create a temp file to which the data will be written, 
        # and starts the consumer
        dest_file = NamedTemporaryFile('r', delete=True, suffix='.wav')
        consumer = WavFileConsumer(queue=queue, path=dest_file.name)
        consumer.start()

        # After 1 second, stops all and checks that data has been
        # written without problem 
        def continue_exec():
            continue_event.set()
        continue_event = threading.Event()
        timer = threading.Timer(2, continue_exec)
        timer.start()
        continue_event.wait()
        
        consumer.running = False
        sound = Sound.from_file(dest_file.name)
        self.assertEqual(sound.values.round(4), samples.round(4))
