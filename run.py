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

import sys
import subprocess
import threading
from Queue import Queue, Empty

import numpy as np

from scrapers import SoundScraper


def wait(time):
    """
    Passive waiting that can be broken with "ctrl-c".
    """
    q = Queue()
    try: q.get(True, time)
    except Empty: pass


sound_queue = Queue(maxsize=100)
SoundScraper.wake_up(1)
wait(60)    

'''
producer = SoundProducer()
producer.start()
consumer = SoundConsumer()
t = threading.Timer(2.0, consumer.start)
t.start()'''

while(True): wait(30)
