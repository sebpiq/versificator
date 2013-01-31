# coding=utf8
# Copyright 2012 - 2013 Sébastien Piquemal <sebpiq@gmail.com>
#
# This file is part of Versificator.
#
# Versificator is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# Versificator is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Versificator.  If not, see <http://www.gnu.org/licenses/>.

import time
import random
random.seed(time.time())
import os
import logging
import threading
import sys
import traceback
import gc

import settings
logger = settings.logger

import numpy as np
import requests
requests_log = logging.getLogger('requests')
requests_log.setLevel(logging.WARNING)
import soundcloud
client = soundcloud.Client(client_id=settings.soundcloud_api_key)
from pyechonest import track as echonest_track
from pyechonest.util import EchoNestAPIError
from pyechonest import config
config.ECHO_NEST_API_KEY = settings.echonest_api_key
from pychedelic import Sound


params = {
    'seg': {
        'confidence_low': 0.1
    },
    'beat': {
        'confidence_low': 0.1
    },
    'bar': {
        'confidence_low': 0.1
    },
}



class SoundScraper(threading.Thread):

    pool_lock = threading.RLock()   # Lock to access the pool
    sample_length = 20              # Length (in s.) to sample from the original sound

    def __init__(self, *args, **kwargs):
        super(SoundScraper, self).__init__(*args, **kwargs)
        self.daemon = True

    def run(self):
        while True: # TODO
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
        track_id, filename = get_sound()
        logger.info('uploading track %s to the echonest' % track_id)
        track = echonest_track.track_from_filename(filename)

        segments = filter(lambda seg: seg['confidence'] > params['seg']['confidence_low'], track.segments)
        bars = filter(lambda bar: bar['confidence'] > params['bar']['confidence_low'], track.bars)
        beats = filter(lambda beat: beat['confidence'] > params['beat']['confidence_low'], track.beats)
        segments = map(lambda seg: AudioQuantum(seg), segments)
        bars = map(lambda bar: AudioQuantum(bar), bars)
        beats = map(lambda beat: AudioQuantum(beat), beats)

        for bar in bars:
            bar_segments = filter(lambda seg: seg.overlap(bar), segments)
            bar['tempo'] = track.tempo # TODO: better tempo ?
            timbres = map(lambda seg: seg['timbre'], bar_segments)
            timbres = np.array(timbres)

            # Calculates a loop quality attribute :
            # we take the standard deviation of timbre over all segments
            # of the bar. If too much segments, we just give up.
            if len(bar_segments) == 1:
                bar['loop_quality'] = 0
            else:
            #elif len(bar_segments) < 20:
                bar['loop_quality'] = timbres.std(axis=0).mean()
            #else:
            #    continue

            #import pdb; pdb.set_trace()
            #bar['timbre'] = timbres.mean(axis=0)

        # Filter only bars that make good loops
        loops = filter(lambda bar: bar['loop_quality'] < 60, bars)
        for loop in loops:
            loop['track_id'] = track_id
            settings.db.loops.insert(loop)
        logger.info('extracted %s loops' % len(loops))

    @classmethod
    def wake_up(cls, how_many=1):
        logger.info('waking up scrapers %s' % cls)
        for i in range(how_many): cls().start()


def get_sound():
    """
    Downloads a random sound from soundcloud, saves it and returns 
    the trackid and the filename.
    """
    track, resp = None, None
    while (True):
        # Get a random track
        while (True):
            track_id = random.randint(0, 100000)
            try:
                track = client.get('/tracks/%s' % track_id)
            except requests.exceptions.HTTPError as exc:
                if exc.response.status_code in [404, 401]:
                    logger.info('%s : %s' % (exc, '/tracks/%s' % track_id))
                else:
                    logger.error('%s - %s' % (exc, track_id))
                continue
            else: break

        # Downloading track.
        # We don't want tracks longer than 15mns.
        if track.duration > 60 * 15000: continue
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
        return track_id, filename


class AudioQuantum(dict):

    def __init__(self, *args, **kwargs):
        super(AudioQuantum, self).__init__(*args, **kwargs)
        self.start = self['start']
        self.duration = self['duration']
        self.end = self.start + self.duration

    def __eq__(self, other):
        if isinstance(other, AudioQuantum):
            return (self.start == other.start and 
                    self.duration == other.duration)
        else: raise TypeError(type(other))

    def __le__(self, other):
        if isinstance(other, AudioQuantum):
            return self == other or self < other
        else: raise TypeError(type(other))

    def __lt__(self, other): 
        if isinstance(other, AudioQuantum):
            return (self.start >= other.start and 
                    self.end <= other.end and
                    not self == other)
        else: raise TypeError(type(other))

    def overlap(self, other):
        return (self <= other or other <= self
          or (self.start > other.start and self.start < other.end)
          or (self.end > other.start and self.end < other.end))


def euclidian_distance(a, b):
    return np.linalg.norm(np.array(a) - np.array(b))
