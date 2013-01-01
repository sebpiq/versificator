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
            threads = [],                   # All loop scrapers threads
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
        self.more_loops_event = threading.Event()   # Event to set to send the thread back to work 
        self.daemon = True
        self.__class__.threads.append(self)

    def run(self):
        """
        This fills up the loop pool until there is at least `pool_min_size` loops in it.
        The method which actually fills-up the pool is `scrape`.
        """
        while (True):
            # Protect from exceptions
            try:
                # We always have at least `pool_min_size` loops in our pool
                while len(self.pool) < self.pool_min_size: self.scrape()
                self.sleep()
            except:
                print traceback.format_exc()

    def scrape(self):
        """
        This is called in a loop by `run` to fill-up the pool.
        """
        raise NotImplementedError()

    def sleep(self):
        self.more_loops_event.wait()
        self.more_loops_event.clear()

    def wake_up(self):
        self.more_loops_event.set()

    @classmethod
    def wake_up_scrapers(cls):
        for t in cls.threads: t.wake_up()

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

    def scrape(self):
        sound = get_sound()

        # Check if the sound is long enough, and if yes we extract some loops from it.
        if sound.length > 2 * self.sample_length:
            offset = 0
            upper_limit = sound.length - 2 * self.sample_length
            while(offset + 2 * self.sample_length < upper_limit):

                # Calculate a random offset where the loop will start
                offset = random.randint(offset, int(min(offset + sound.length * 0.2, upper_limit)))

                # Extracting a loop and saving it to 'loop<n>.wav'
                sample = sound.ix[float(offset):float(offset+self.sample_length)]
                loop = extract_loop(sample)
                if loop is not None:
                    loop_path = self._get_free_path()
                    logger.info('loop extracted to %s' % loop_path)
                    loop.to_file(loop_path)
                    key, key_confidence = loop.echonest.key, loop.echonest.key_confidence
                    with self.pool_lock:
                        self.pool.append({
                            'path': loop_path,
                            'length': loop.length,
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
# Start 3 loop scrapers
for i in range(3): LoopScraper().start()


class PadScraper(BaseScraper):

    pool_min_size = 5
    filename_prefix = 'pad'

    def scrape(self):
        pad = get_sound()
        pad_path = self._get_free_path()
        logger.info('pad extracted to %s' % pad_path)
        pad.to_file(pad_path)
        with self.pool_lock:
            self.pool.append({
                'path': pad_path
            })
        
    @classmethod
    def gimme_pad_handler(cls, addr, tags, data, source):
        with cls.pool_lock:
            pad_infos = self.pool.pop(0)
        logger.info('sending new pad %s' % pad_infos['path'])
        send_msg('/new_pad', pad_infos['path'])
        if len(PadScraper.pool) < PadScraper.pool_min_size: PadScraper.wake_up_scrapers()
# Start 2 pad scrapers
for i in range(3): PadScraper().start()


# -------- SERVER --------#
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

# Pre-downloading some sounds, and sending a message to the patch
# when this is done.
# TODO: doesn't work anymore now that separate threads handle scraping
send_msg('/init/ready')
logger.info('*INIT* telling the patch things are ready')


# Hack to have a passive "sleep" that can be interrupted with ctrl-c
# ... with `threading.Timer` it doesn't work.
from Queue import Queue, Empty
while(True):
    q = Queue()
    try: q.get(True, 30)
    except Empty: pass
