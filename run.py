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
from sound import Sound
from pychedelic.utils import convert_file

from tools import get_sound, send_msg, loop_distance


class ScraperType(type):
    
    def __new__(cls, name, bases, attrs):
        # For each subclass of `BaseScraper`, we add new attributes,
        # and we don't want those to be shared between subclasses.
        defaults = dict(
            pool = {},                      # Pool containing the loops
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
            path = settings.app_root + 'sounds/' + filename
            self.__class__.name_counter = (self.__class__.name_counter + 1) % 1000
            return path


# TODO: log thread ids
# -------- LOOPS --------#
class LoopScraper(BaseScraper):
    sample_length = 20              # Length (in s.) to sample from the original sound
    filename_prefix = 'loop'
    pool_min_size = 50
    pd_loopers = {}
    old_loops = {}
    old_loops_lock = threading.Lock()

    def scrape(self):
        id_counter = 0
        track_id, filename, sound_length = get_sound()

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
                loops = sample.extract_loops()
                for loop in loops:
                    if id_counter > 10:
                        offset = upper_limit
                        break
                    id_counter += 1
                    loop_id = '%s_%s' % (track_id, id_counter)
                    loop_path = self._get_free_path()
                    logger.info('loop extracted to %s' % loop_path)
                    loop.to_file(loop_path)
                    #key, key_confidence, length = loop.echonest.key, loop.echonest.key_confidence, loop.length

                    with self.pool_lock:
                        self.pool[loop_id] = dict(loop.loop_infos, **{
                            'path': loop_path,
                            'length': loop.length,
                            'loop_id': loop_id,
                            'track_id': track_id,
                            'timbre_start': loop.loop_infos['timbre_start'],
                            'timbre_end': loop.loop_infos['timbre_end']
                            #'key': (key, key_confidence)
                        })

                # Increment values for next loop
                offset += self.sample_length

                # Delete the sounds to save memory
                # We also have to collect manually because of a "bug" in pandas:
                # https://github.com/pydata/pandas/issues/2659
                if 'loop' in locals(): del loop
                del sample
                gc.collect()

    @classmethod
    def gimme_loop_handler(cls, addr, tags, data, source):
        # time in seconds; key between 0 (for C) and 11 (for B)
        pd_looper_id, required_tempo, required_key = data[0], data[1], data[2]
        
        # If the track hasn't been registered yet, we do that
        pd_looper_infos = cls.pd_loopers.setdefault(pd_looper_id, {
            'current_loop_id': None,
            'track_ids': [],
            'tempo': None,
        })
        current_loop_id = pd_looper_infos['current_loop_id']

        # Picking the new loop in the pool
        with cls.pool_lock:

            # prefilter available loops (those whose track haven't been picked already)
            available_loops = cls.pool.values()
            forbidden_tracks = cls.forbidden_tracks(pd_looper_id)
            available_loops = filter(lambda l: l['track_id'] not in forbidden_tracks, available_loops)

            # Select the most suitable next loop according to the current loop.
            if current_loop_id is not None:
                def sort_key(l):
                    timbre_dist = loop_distance(cls.old_loops[current_loop_id], l)
                    tempo_dist = abs(1 - l['tempo'] / float(required_tempo)) * 40
                    return timbre_dist + tempo_dist
                loop_infos = sorted(available_loops, key=lambda l: sort_key)[0]
            else:
                loop_infos = available_loops[0]

            # Remove the loop from the pool, reserving the loop's track for this looper
            cls.pool.pop(loop_infos['loop_id'])
            pd_looper_infos['track_ids'].append(loop_infos['track_id'])
        pd_looper_infos['current_loop_id'] = loop_infos['loop_id']

        # Adding the picked looped to `old_loops`, so that we remember it
        # but it cannot be used again.
        with cls.old_loops_lock:
            cls.old_loops[loop_infos['loop_id']] = loop_infos
            if current_loop_id is not None: cls.old_loops.pop(current_loop_id)

        # Preparing the loop
        logger.info('sending new loop %s to looper %s, left : %s' % (loop_infos['path'], pd_looper_id, len(cls.pool)))
        loop = Sound.from_file(loop_infos['path'])
        required_length = loop.length * float(required_tempo) / loop_infos['tempo']
        beat_length = 60.0 / required_tempo
        required_length = round(required_length / beat_length) * beat_length
        loop = loop.time_stretch(required_length).fade(in_dur=0.002, out_dur=0.002)
        loop.to_file(loop_infos['path'])

        # Sending loop, and fill-up the pool if necessary.
        send_msg('/new_loop', pd_looper_id, loop_infos['path'], int(round(loop.length * 1000)), loop_infos['loop_id'])
        if len(LoopScraper.pool) < LoopScraper.pool_min_size: LoopScraper.wake_up_scrapers()

    @classmethod
    def forbidden_tracks(cls, looper_id):
        """
        Returns a list of the tracks that the looper `looper_id` cannot use
        """
        loopers_infos = dict(**cls.pd_loopers)
        loopers_infos.pop(looper_id)
        track_ids = []
        return reduce(lambda memo, elem: memo + elem['track_ids'], loopers_infos.values(), [])


class PadScraper(BaseScraper):

    pool_min_size = 3
    filename_prefix = 'pad'

    def scrape(self):
        track_id, pad_path, pad_length = get_sound()
        new_pad_path = self._get_free_path()
        pad_id = '%s' % (track_id)
        sound = Sound.from_file(pad_path, end=min(30, pad_length))
        sound = sound.remove_beats()
        sound.to_file(new_pad_path)
        logger.info('pad extracted to %s' % new_pad_path)
        '''pad.to_file(pad_path)

        # Delete the sound to save memory
        # We also have to collect manually because of a "bug" in pandas:
        # https://github.com/pydata/pandas/issues/2659 
        del pad
        gc.collect()'''

        with self.pool_lock:
            self.pool[pad_id] = {
                'path': new_pad_path,
                'pad_id': pad_id
            }
        
    @classmethod
    def gimme_pad_handler(cls, addr, tags, data, source):
        with cls.pool_lock:
            pad_infos = cls.pool.values().pop(0)
            cls.pool.pop(pad_infos['pad_id'])
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
          or len(LoopScraper.pool) < LoopScraper.pool_min_size / 30.0):
        q = Queue()
        try: q.get(True, 2)
        except Empty: pass
    send_msg('/init/ready')
    logger.info('*INIT* telling the patch things are ready')

    #from guppy import hpy; hp=hpy()
    while(True):
        q = Queue()
        try: q.get(True, 30)
        except Empty: pass
        #print hp.heap()
