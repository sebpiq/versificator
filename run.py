import time
import threading
import random
import numpy as np
import os
import threading
import subprocess
import sys
random.seed(time.time())
import logging
import signal

# Application logger
LOG_LEVEL = logging.INFO
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
logger.setLevel(LOG_LEVEL)
handler.setLevel(LOG_LEVEL)

import requests
# Less log messages from requests
requests_log = logging.getLogger('requests')
requests_log.setLevel(logging.WARNING)
import OSC
import settings
import soundcloud
from pyechonest import config
config.ECHO_NEST_API_KEY = settings.echonest_api_key
from pychedelic import Sound


def get_sound():
    # create a client object with your app credentials
    client = soundcloud.Client(client_id='YOUR_CLIENT_ID')
    track, resp = None, None
    while (True):
        # Get a random track
        while (True):
            track_id = random.randint(0, 100000)
            try:
                track = client.get('/tracks/%s' % track_id)
            except requests.exceptions.HTTPError as exc:
                if exc.response.status_code != 404: logger.error(exc)
                else: logger.debug('%s - %s' % (exc, track_id))
                continue
            else: break

        # Downloading track.
        # We don't want too long tracks because of memory pbs.
        if track.duration > 60 * 5000: continue
        if not hasattr(track, 'stream_url'): continue
        track_stream = client.get(track.stream_url, allow_redirects=False)
        logger.info('downloading track %s' % track.stream_url)
        resp = requests.get(track_stream.location)
        if resp.status_code == 200:
            filename = settings.app_root + 'downloads/%s.mp3' % track_id
            logger.info('saving track to %s' % filename)
            try:
                with open(filename, 'wb') as fd:
                    for chunk in resp.iter_content(64 * 1024):
                        fd.write(chunk)
            except Exception as exc:
                logger.error('file download failed : %s' % exc)
                continue
        else:
            logger.error('tried to download track, but got %s' % resp)
            continue

        # If the file is too big, this will fail
        try: 
            sound = Sound.from_file(filename)
            os.remove(filename)
        except MemoryError:
            continue
        else:
            return sound
    

def extract_loop(sound):
    """
    Takes a sound and extracts a loop from it. If no loop could be extracted, `None` is returned.
    """
    # Filter bars that only have a minimum confidence
    bars = sound.echonest.bars
    bars = filter(lambda bar: bar['confidence'] > 0.1, bars)
    if not bars: return

    # Extract the bar with the strongest confidence  
    bars = sorted(sound.echonest.bars, key=lambda bar: -bar['confidence'])
    return sound.ix[float(bars[0]['start']):float(bars[0]['start']+bars[0]['duration'])]


def send_msg(address, *args):
    client = OSC.OSCClient()
    client.connect(('localhost', 9001))
    msg = OSC.OSCMessage(address)
    for arg in args:
        msg.append(arg)
    client.send(msg)


if __name__ == '__main__':
    # TODO: log thread ids

    # -------- LOOPS --------#
    class LoopScraper(threading.Thread):
        pool = []                       # Pool containing the loops
        pool_lock = threading.RLock()   # Lock to access the pool
        names_lock = threading.RLock()  # Lock to get a unique name for a loop
        pool_min_size = 15              # Pool will always contain at least that much loops
        lcounter = 0                    # Counter used to "uniquely" name the loops
        threads = []                    # All loop scrapers threads
        sample_length = 20              # Length (in s.) to sample from the original sound

        def __init__(self, *args, **kwargs):
            super(LoopScraper, self).__init__(*args, **kwargs)
            self.more_loops_event = threading.Event()   # Event to set to send the thread back to work 
            self.daemon = True
            self.__class__.threads.append(self)

        def run(self):
            """
            This fills up the loop pool until there is at least `pool_min_size` loops in it. 
            """
            while (True):
                # We always have min 2 loops in our pool
                while len(self.pool) < self.pool_min_size:
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
                                loop_path = self._get_loop_path()
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
                self.more_loops_event.wait()
                self.more_loops_event.clear()

        def _get_loop_path(self):
            """
            This returns the filepath for the next loop to use.
            """
            with self.names_lock:
                loop_filename = 'loop%s.wav' % self.__class__.lcounter
                loop_path = settings.app_root + 'patch/' + loop_filename
                self.__class__.lcounter = (self.__class__.lcounter + 1) % 1000
                return loop_path

        @classmethod
        def gimme_loop(cls, length, key):
            with cls.pool_lock:
                loop_infos = sorted(cls.pool, key=lambda l: abs(l['length'] - required_length))[0]
                cls.loop.pop(cls.loop.index(loop_infos))
            logger.info('sending new loop %s, still %s in pool' % (loop_infos['path'], len(cls.pool)))
            return loop_infos

        @classmethod
        def scrape_more(cls):
            for t in cls.threads: t.more_loops_event.set()


    # Start 3 loop scrapers
    for i in range(3): LoopScraper().start()


    def new_loop_handler(addr, tags, data, source):
        # time in seconds; key between 0 (for C) and 11 (for B)
        required_length, required_key = data[0], data[1]

        # Picking loop in the pool with closest required length
        # time stretching it, apply some fade in / out.
        loop_infos = LoopScraper.gimme_loop(required_length, required_key)
        loop = Sound.from_file(loop_infos['path'])
        loop.time_stretch(required_length).fade(in_dur=0.003, out_dur=0.003).to_file(loop_infos['path'])

        # Sending loop, and fill-up the pool if necessary.
        send_msg('/new_loop', loop_infos['path'])
        if len(LoopScraper.loop_pool) < LoopScraper.pool_min_size: LoopScraper.scrape_more()

    '''
    # -------- PADS --------#
    pad_pool = []
    pad_file_ind = 0
    def fill_pad_pool():
        # We have max 2 sounds in our pool of sounds for pads
        while len(pad_pool) < 1:#2: TODO
            pad_pool.append(get_sound())

    def new_pad_handler(addr, tags, data, source):
        sound = pad_pool.pop(0)
        global pad_file_ind
        new_pad_filename = 'pad%s.wav' % pad_file_ind
        new_pad_path = settings.app_root + 'patch/' + new_pad_filename
        sound.to_file(new_pad_path)
        pad_file_ind = (pad_file_ind + 1) % 2 # rotate between pad file names
        logger.info('sending new pad %s' % new_pad_filename)
        send_msg('/new_pad', new_pad_path)
        fill_pad_pool()


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
    server.addMsgHandler('/gimme_loop', new_loop_handler)
    server.addMsgHandler('/gimme_pad', new_pad_handler)

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
    fill_pad_pool()
    send_msg('/init/ready')
    logger.info('*INIT* telling the patch things are ready')

    '''

    # Starting the main loop
    main_loop_event = threading.Event()
    # Hack for stopping the main loop when ctrlc is pressed
    stop_flag = False
    def ctrlc_handler(signal, frame):
        logger.info('stopping')
        global stop_flag
        stop_flag = True
    signal.signal(signal.SIGINT, ctrlc_handler)
    while(not stop_flag):
        main_loop_timer = threading.Timer(30.0, lambda: main_loop_event.set())
        main_loop_timer.start()
        main_loop_event.wait()
        main_loop_event.clear()
