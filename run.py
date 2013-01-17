import time
import random
random.seed(time.time())
import os
import threading
import subprocess
import sys
import logging
import signal
import traceback
import gc

# Application logger
LOG_LEVEL = logging.INFO
logger = logging.getLogger('versificator')
handler = logging.StreamHandler()
logger.setLevel(LOG_LEVEL)
handler.setLevel(LOG_LEVEL)

import OSC
import settings
from pyechonest import config
config.ECHO_NEST_API_KEY = settings.echonest_api_key
from pychedelic import Sound

from tools import get_sound, extract_loop, send_msg


class ScraperType(type):
    
    def __new__(cls, name, bases, attrs):
        # For each subclass of `BaseScraper`, we add new attributes,
        # and we don't want those to be shared between subclasses.
        defaults = dict(
            pool = [],                      # Pool containing the loops
            pool_lock = threading.RLock(),  # Lock to access the pool
            pool_min_size = 15,             # Pool will always contain at least that much loops
            names_lock = threading.RLock(), # Lock to get a unique name for a sound file to save
            name_counter = 0,               # Counter used to "uniquely" name the soudn files
            filename_prefix = ''
        )
        for key, value in defaults.items(): attrs.setdefault(key, value)
        return super(ScraperType, cls).__new__(cls, name, bases, attrs)


class BaseScraper(threading.Thread):

    __metaclass__ = ScraperType

    def __init__(self, *args, **kwargs):
        super(BaseScraper, self).__init__(*args, **kwargs)
        self.daemon = True

    def run(self):
        """
        This fills up the loop pool until there is at least `pool_min_size` loops in it.
        The method which actually fills-up the pool is `scrape`.
        """
        while (len(self.pool) < self.pool_min_size):
            # Protect from exceptions
            try:
                # We always have at least `pool_min_size` loops in our pool
                self.scrape()
            except:
                print traceback.format_exc()
        logger.info('harakiri %s' % self)

    def scrape(self):
        """
        This is called in a loop by `run` to fill-up the pool.
        """
        raise NotImplementedError()

    @classmethod
    def wake_up_scrapers(cls):
        logger.info('waking up scrapers %s' % cls)
        for i in range(1): cls().start()

    def _get_free_path(self):
        """
        This returns the filepath for the next loop to use.
        """
        with self.names_lock:
            filename = '%s%s.wav' % (self.filename_prefix, self.__class__.name_counter)
            path = settings.app_root + 'patch/' + filename
            self.__class__.name_counter = (self.__class__.name_counter + 1) % 1000
            return path


# TODO: log thread ids
# -------- LOOPS --------#
class LoopScraper(BaseScraper):
    sample_length = 20              # Length (in s.) to sample from the original sound
    filename_prefix = 'loop'
    pool_min_size = 3

    def scrape(self):
        filename, sound_length = get_sound()

        # Check if the sound is long enough, and if yes we extract some loops from it.
        # TODO: make this less restrictive to waste a bit less
        if sound_length > 2 * self.sample_length:
            offset = 0
            upper_limit = sound_length - 2 * self.sample_length
            while (offset + 2 * self.sample_length < upper_limit):

                # Calculate a random offset where the loop will start
                offset = random.randint(offset, int(min(offset + sound_length * 0.2, upper_limit)))

                # Extracting a loop and saving it to 'loop<n>.wav'
                sample = Sound.from_file(filename, start=offset, end=offset+self.sample_length)
                loop = extract_loop(sample)
                if loop is not None:
                    loop_path = self._get_free_path()
                    logger.info('loop extracted to %s' % loop_path)
                    loop.to_file(loop_path)
                    key, key_confidence, length = loop.echonest.key, loop.echonest.key_confidence, loop.length

                    # Delete the sounds to save memory
                    # We also have to collect manually because of a "bug" in pandas:
                    # https://github.com/pydata/pandas/issues/2659
                    del loop; del sample
                    gc.collect()

                    with self.pool_lock:
                        self.pool.append({
                            'path': loop_path,
                            'length': length,
                            'key': (key, key_confidence)
                        })

                # Increment values for next loop
                offset += self.sample_length

    @classmethod
    def gimme_loop_handler(cls, addr, tags, data, source):
        # time in seconds; key between 0 (for C) and 11 (for B)
        required_length, required_key = data[0], data[1]

        # Picking loop in the pool with closest required length
        # time stretching it, apply some fade in / out.
        with cls.pool_lock:
            loop_infos = sorted(cls.pool, key=lambda l: abs(l['length'] - required_length))[0]
            cls.pool.pop(cls.pool.index(loop_infos))
        logger.info('sending new loop %s, still %s in pool' % (loop_infos['path'], len(cls.pool)))

        loop = Sound.from_file(loop_infos['path'])
        loop.time_stretch(required_length).fade(in_dur=0.003, out_dur=0.003).to_file(loop_infos['path'])

        # Sending loop, and fill-up the pool if necessary.
        send_msg('/new_loop', loop_infos['path'])
        if len(LoopScraper.pool) < LoopScraper.pool_min_size: LoopScraper.wake_up_scrapers()


class PadScraper(BaseScraper):

    pool_min_size = 3
    filename_prefix = 'pad'

    def scrape(self):
        pad_path, pad_length = get_sound()
        logger.info('pad extracted to %s' % pad_path)
        '''pad.to_file(pad_path)

        # Delete the sound to save memory
        # We also have to collect manually because of a "bug" in pandas:
        # https://github.com/pydata/pandas/issues/2659 
        del pad
        gc.collect()'''

        with self.pool_lock:
            self.pool.append({
                'path': pad_path
            })
        
    @classmethod
    def gimme_pad_handler(cls, addr, tags, data, source):
        with cls.pool_lock:
            pad_infos = cls.pool.pop(0)
        logger.info('sending new pad %s, still %s in pool' % (pad_infos['path'], len(cls.pool)))
        send_msg('/new_pad', pad_infos['path'])
        if len(PadScraper.pool) < PadScraper.pool_min_size: PadScraper.wake_up_scrapers()


if __name__ == '__main__':
    # Start scrapers
    for i in range(3): LoopScraper().start()
    for i in range(2): PadScraper().start()

    # Start server
    server = OSC.OSCServer(('localhost', 9000))
    OSC.OSCServer.print_tracebacks = True

    # this registers a 'default' handler (for unmatched messages),
    # an /'error' handler, an '/info' handler.
    server.addDefaultHandlers()
    def init_handler(addr, tags, data, source):
        logger.info('*INIT* send init infos to the pd patch')
        send_msg('/init/pwd', settings.icecast_password)
    server.addMsgHandler('/init', init_handler)
    server.addMsgHandler('/gimme_loop', LoopScraper.gimme_loop_handler)
    server.addMsgHandler('/gimme_pad', PadScraper.gimme_pad_handler)

    # Starting the OSC server in a new thread
    def init_server():
        server.serve_forever()
    osc_server_thread = threading.Thread(target=init_server)
    osc_server_thread.daemon = True
    osc_server_thread.start()

    # starting the pd patch
    logger.info('*INIT* starting pd patch')
    subprocess.Popen(['pd-extended', '-nrt', settings.app_root + 'patch/main.pd'],
        stdout=open(os.devnull, 'w'),
        stderr=sys.stderr)

    # Hack to have a passive "sleep" that can be interrupted with ctrl-c
    # ... with `threading.Timer` it doesn't work.
    from Queue import Queue, Empty

    # Pre-downloading some sounds, and sending a message to the patch
    # when this is done.
    while(len(PadScraper.pool) < PadScraper.pool_min_size
          or len(LoopScraper.pool) < LoopScraper.pool_min_size / 3.0):
        q = Queue()
        try: q.get(True, 5)
        except Empty: pass
    send_msg('/init/ready')
    logger.info('*INIT* telling the patch things are ready')

    #from guppy import hpy; hp=hpy()
    while(True):
        q = Queue()
        try: q.get(True, 30)
        except Empty: pass
        #print hp.heap()
