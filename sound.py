import numpy as np

from pychedelic import Sound as PycheSound
from tools import euclidian_distance

import settings
from pyechonest import config
config.ECHO_NEST_API_KEY = settings.echonest_api_key


class Sound(PycheSound):

    def get_overlapping_segments(self, bar):
        """
        Returns the list of segments overlapping `bar` sorted by starting time. 
        """
        bar_start = bar['start']
        bar_end = bar_start + bar['duration']
        segments = sorted(self._echonest.segments, key=lambda seg: seg['start'])
        overlapping_segments = []
        for seg in segments:
            seg_start = seg['start']
            seg_end = seg['start'] + seg['duration']
            if seg_start > bar_end: break
            if ((bar_start > seg_start and bar_start < seg_end)
              or (bar_end > seg_start and bar_end < seg_end)):
                overlapping_segments.append(seg)
        return overlapping_segments

    @property
    def echonest(self):
        """
        Calculates some extra attributes for all bars.
        """
        echonest = super(Sound, self).echonest
        for bar_infos in echonest.bars:
            segments = self.get_overlapping_segments(bar_infos)
            bar_infos['tempo'] = echonest.tempo

            # Calculates a loop quality attribute
            if len(segments) == 1:
                bar_infos['loop_quality'] = 0
            elif len(segments) == 2:
                bar_infos['loop_quality'] = euclidian_distance(
                    np.array(segments[0]['timbre']),
                    np.array(segments[1]['timbre'])
                )
            else:
                bar_infos['loop_quality'] = 100000

            # Calculates the timbre values at the start of the loop,
            # and at the end of the loop. 
            if segments:            
                bar_infos['timbre_start'] = segments[0]['timbre']
                bar_infos['timbre_end'] = segments[-1]['timbre']
            else:
                bar_infos['timbre_start'] = None
                bar_infos['timbre_end'] = None
        return echonest

    def loop_from_bar_infos(self, bar_infos):
        return self.ix[float(bar_infos['start']):float(bar_infos['start']+bar_infos['duration'])]

    def extract_loops(self):
        """
        Takes a sound and extracts a loop from it. If no loop could be extracted, `None` is returned.
        """
        # Filter only bars that make good loops
        bars_infos = self.echonest.bars
        bars_infos = filter(lambda bar_info: bar_info['loop_quality'] < 60, bars_infos)
        if not bars_infos: return []
        else:
            loops = []
            for b in bars_infos:
                loop = self.loop_from_bar_infos(b)
                loop.loop_infos = b
                loops.append(loop)
            return loops

    def remove_beats(self):
        beat_times = [(b['start'], b['duration']) for b in self.echonest.beats]
        def criterion(time):
            for start, end in beat_times:
                if time > start and time < end:
                    return False
            return True
        return self._constructor(self.select(criterion, axis=0).values)
            
