import os, sys
sys.path.append(os.path.abspath('..'))
import unittest
import numpy as np


class VersTestCase(unittest.TestCase):

    def assertEqual(self, first, second):
        if isinstance(first, np.ndarray) or isinstance(second, np.ndarray):
            first = np.array(first)
            second = np.array(second)
            super(VersTestCase, self).assertEqual(first.shape, second.shape)
            ma = (first == second)
            if isinstance(ma, bool):
                return self.assertTrue(ma)            
            return self.assertTrue(ma.all())
        else:
            return super(VersTestCase, self).assertEqual(first, second)
