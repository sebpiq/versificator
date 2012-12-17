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

    # -------- LOOPS --------#
    LOOP_POOL = []
    LOOP_POOL_MIN = 5
    LOOP_IND = 0
    LOOP_READ = [] # TODO
    SAMPLE_LENGTH = 20

    def fill_loop_pool():
        """
        This fills up the loop pool until there is at least `LOOP_POOL_MIN` loops in it. 
        """
        logger.info('filling-up loop pool')
        global LOOP_IND

        # We always have min 2 loops in our pool
        while len(LOOP_POOL) < LOOP_POOL_MIN:
            sound = get_sound()

            # Check if the sound is long enough, and if yes we extract some loops from it.
            if sound.length > 2 * SAMPLE_LENGTH:
                offset = 0
                upper_limit = sound.length - 2 * SAMPLE_LENGTH
                while(offset + 2 * SAMPLE_LENGTH < upper_limit):

                    # Calculate a random offset where the loop will start
                    offset = random.randint(offset, int(min(offset + sound.length * 0.2, upper_limit)))

                    # Extracting a loop and saving it to 'loop<n>.wav'
                    loop_filename = 'loop%s.wav' % LOOP_IND
                    loop_path = settings.app_root + 'patch/' + loop_filename
                    sample = sound.ix[float(offset):float(offset+SAMPLE_LENGTH)]
                    loop = extract_loop(sample)
                    if loop is not None:
                        logger.info('loop extracted to %s' % loop_path)
                        loop.to_file(loop_path)
                        LOOP_POOL.append({'path': loop_path, 'length': loop.length})
                        LOOP_IND = (LOOP_IND + 1) % 1000 # rotate between loop file names

                    # Increment values for next loop
                    offset += SAMPLE_LENGTH


    def new_loop_handler(addr, tags, data, source):
        required_length = data[0]

        # Picking loop in the pool with closest required length
        # time stretching it, apply some fade in / out.
        loop_infos = sorted(LOOP_POOL, key=lambda l: abs(l['length'] - required_length))[0]
        loop = Sound.from_file(loop_infos['path'])
        loop.time_stretch(required_length).fade(in_dur=0.003, out_dur=0.003).to_file(loop_infos['path'])

        # Sending loop, removing it from the pool
        # and filling up the pool if necessary.
        logger.info('sending new loop %s, still %s in pool' % (loop_infos['path'], len(LOOP_POOL)))
        send_msg('/new_loop', loop_infos['path'])
        LOOP_POOL.pop(LOOP_POOL.index(loop_infos))
        if len(LOOP_POOL) < LOOP_POOL_MIN: fill_loop_pool()


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
    fill_loop_pool()
    fill_pad_pool()
    send_msg('/init/ready')
    logger.info('*INIT* telling the patch things are ready')

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
