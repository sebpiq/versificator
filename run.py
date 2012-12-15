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
LOG_LEVEL = logging.INFO
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
logger.setLevel(LOG_LEVEL)
handler.setLevel(LOG_LEVEL)
logger.addHandler(handler)

import soundcloud
import requests

sys.path.append(os.path.abspath('./soundlab'))
from soundlab import Sound, DataSet
from BeatFinder import get_tempo
import OSC

import settings


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
            filename = './downloads/%s.mp3' % track_id
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
            sound.track_id = track_id
            return sound
    

def extract_loop(sound):
    bpms, energies = get_tempo(sound)
    bpms_data = DataSet(bpms, data=energies)
    bpms_data = bpms_data.smooth().maxima()
    bpm = bpms_data.axes[0][bpms_data.data == np.amax(bpms_data.data)][0]
    while(True):
        bpm /= 2.0
        lower = bpm - bpm * 0.02
        upper = bpm + bpm * 0.02
        for possible in bpms_data.axes[0]:
            if possible > lower and possible < upper: break
        else: break
    loop_length = 60.0 / bpm
    offset = sound.axes[0][0]
    sound = sound[offset:offset + loop_length]

    window_size = 100
    sustain = np.ones(sound.sample_count - window_size)
    fade = (np.exp(np.linspace(0, np.log(100), window_size)) - 1) / (100 - 1)
    fade_in = np.hstack((fade, sustain))
    fade_out = np.hstack((sustain, fade[::-1]))
    sound._data[:,0] *= fade_in
    sound._data[:,0] *= fade_out
    return sound


def send_msg(address, *args):
    client = OSC.OSCClient()
    client.connect(('localhost', 9001))
    msg = OSC.OSCMessage(address)
    for arg in args:
        msg.append(arg)
    client.send(msg)


if __name__ == '__main__':

    # -------- LOOPS --------#
    loop_pool = {}
    sample_length = 10
    loop_file_ind = 0
    def fill_loop_pool():
        # We have max 2 sounds in our pool of sounds for loops
        while len(loop_pool) < 2:
            sound = get_sound()
            if sound.length > 2 * sample_length:
                loop_pool[sound.track_id] = {
                    'sound': sound,
                    'offset': 0,
                    'used': 0
                }

    def new_loop_handler(addr, tags, data, source):
        # Picking a random sound in the pool, calculate a random offset
        # where the loop will start
        sound_infos = random.choice(loop_pool.values())
        sound, offset = sound_infos['sound'], sound_infos['offset']
        upper_limit = sound.length - 2 * sample_length
        offset = random.randint(offset, int(min(offset + sound.length * 0.2, upper_limit)))

        # Extracting a loop and saving it to 'loop.wav'
        global loop_file_ind
        new_loop_filename = 'loop%s.wav' % loop_file_ind
        extract_loop(sound[offset:offset+sample_length]).to_file('patch/' + new_loop_filename)
        loop_file_ind = (loop_file_ind + 1) % 2 # rotate between loop file names
        logger.info('sending new loop %s' % new_loop_filename)
        send_msg('/new_loop', new_loop_filename)

        # If the sound has already been used twice for a loop,
        # or if the offset is too close to the end of the file,
        # we trash the sound.
        sound_infos['used'] = sound_infos['used'] + 1
        if sound_infos['used'] > 2 or offset + 2 * sample_length > upper_limit:
            loop_pool.pop(sound.track_id)
            logger.info('sound exhausted, getting new sounds ...')
            fill_loop_pool()
        else:
            sound_infos['offset'] = offset + sample_length # we don't want to pick same loop again


    # -------- PADS --------#
    pad_pool = []
    pad_file_ind = 0
    def fill_pad_pool():
        # We have max 2 sounds in our pool of sounds for pads
        while len(pad_pool) < 2:
            pad_pool.append(get_sound())

    def new_pad_handler(addr, tags, data, source):
        sound = pad_pool.pop(0)
        global pad_file_ind
        new_pad_filename = 'pad%s.wav' % pad_file_ind
        sound.to_file('patch/%s' % new_pad_filename)
        pad_file_ind = (pad_file_ind + 1) % 2 # rotate between pad file names
        logger.info('sending new pad %s' % new_pad_filename)
        send_msg('/new_pad', new_pad_filename)
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
    osc_server_thread.start()

    # starting the pd patch
    logger.info('*INIT* starting pd patch')
    subprocess.Popen(['pd-extended', '-nrt', '-nogui', 'patch/main.pd'],
        stdout=open(os.devnull, 'w'),
        stderr=open(os.devnull, 'w'))

    # Pre-downloading some sounds, and sending a message to the patch
    # when this is done. 
    fill_loop_pool()
    fill_pad_pool()
    send_msg('/init/ready')
    logger.info('*INIT* telling the patch things are ready')

    # Starting the main loop
    main_loop_event = threading.Event()
    main_loop_timer = threading.Timer(30.0, lambda: main_loop_event.set())
    while(True):
        main_loop_event.wait()
        print "MAIN LOOP"
        main_loop_event.clear()
    
