import time
import random
random.seed(time.time())
import os
import OSC
import requests
import settings
import soundcloud
import traceback
import logging
import numpy as np
logger = logging.getLogger('versificator')
# Less log messages from requests
requests_log = logging.getLogger('requests')
requests_log.setLevel(logging.WARNING)

from pychedelic import Sound


def get_sound():
    """
    Downloads a random sound from soundcloud, saves it and returns 
    the filename and the sound length in seconds.
    """

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
        sound_length = track.duration
        if sound_length > 60 * 5000: continue
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
        return track_id, filename, sound_length / 1000.0


def euclidian_distance(a, b):
    return np.linalg.norm(np.array(a) - np.array(b))


def loop_distance(loop_infos1, loop_infos2):
    """
    Simple measure of the timbral distance between end of loop1 and start of loop2.
    """
    return euclidian_distance(loop_infos1['timbre_start'], loop_infos2['timbre_end'])


def send_msg(address, *args):
    client = OSC.OSCClient()
    client.connect(('localhost', 9001))
    msg = OSC.OSCMessage(address)
    for arg in args:
        msg.append(arg)
    client.send(msg)
