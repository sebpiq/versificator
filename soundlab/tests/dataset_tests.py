import copy
import numpy as np
from __init__ import SoundLabTestCase
from soundlab import SampledDataSet, DataSet


class ThreeDDataSet(SampledDataSet):
    dimensions = ['x', 'y', 'z']


class DataSet_Test(SoundLabTestCase):

    def copy_test(self):
        dataset = SampledDataSet(data=[[1, 11], [2, 22], [3, 33], [4, 44], [5, 55], [6, 66], [7, 77], [8, 88]], sample_rate=2)
        copied = copy.copy(dataset)
        self.assertEqual(copied.data, dataset.data)
        self.assertEqual(copied.sample_rate, dataset.sample_rate)

        copied = dataset.__copy__(data=[[1], [2], [3]])
        self.assertEqual(copied.data, [[1], [2], [3]])
        self.assertEqual(dataset.data, [[1, 11], [2, 22], [3, 33], [4, 44], [5, 55], [6, 66], [7, 77], [8, 88]])
        self.assertEqual(copied.sample_rate, dataset.sample_rate)

    def maxima_test(self):
        dataset = SampledDataSet(data=[[1], [2], [1], [2], [5], [5], [3]], sample_rate=2)
        maxima = dataset.maxima()
        self.assertEqual(maxima.data, [2, 5])
        self.assertEqual(maxima.axes[0], [0.5, 2])

        # testing edges
        dataset = SampledDataSet(data=[[2], [0], [-1]], sample_rate=2)
        maxima = dataset.maxima()
        self.assertEqual(maxima.data, [2])
        self.assertEqual(maxima.axes[0], [0])
        dataset = SampledDataSet(data=[[-10], [-2], [-1]], sample_rate=2)
        maxima = dataset.maxima()
        self.assertEqual(maxima.data, [-1])
        self.assertEqual(maxima.axes[0], [1])
        dataset = SampledDataSet(data=[[-10], [-1], [-1]], sample_rate=2)
        maxima = dataset.maxima()
        self.assertEqual(maxima.data, [-1])
        self.assertEqual(maxima.axes[0], [0.5])
        dataset = SampledDataSet(data=[[10], [10], [-1]], sample_rate=2)
        maxima = dataset.maxima()
        self.assertEqual(maxima.data, [10])
        self.assertEqual(maxima.axes[0], [0])

        # testing channel
        dataset = SampledDataSet(data=[[1, 78], [2, 5], [1, 34], [2, 33], [3, 1], [5, 4], [3, 5]], sample_rate=2)
        maxima = dataset.maxima(1)
        self.assertEqual(maxima.data, [78, 34, 5])
        self.assertEqual(maxima.axes[0], [0, 1, 3])

        # testing take_edges
        maxima = dataset.maxima(1, take_edges=False)
        self.assertEqual(maxima.data, [34])
        self.assertEqual(maxima.axes[0], [1])

    def minima_test(self):
        dataset = SampledDataSet(data=[[1], [1], [2], [2], [3], [5], [3]], sample_rate=2)
        minima = dataset.minima()
        self.assertEqual(minima.data, [1, 3])
        self.assertEqual(minima.axes[0], [0, 3])
        minima = dataset.minima(take_edges=False)
        self.assertEqual(minima.data, [1])
        self.assertEqual(minima.axes[0], [0])

    def x_test(self):
        dataset = SampledDataSet(data=[[1], [0.5], [0], [-0.5], [-1]], sample_rate=2)
        self.assertEqual(dataset.axes[0], [0, 0.5, 1, 1.5, 2])
    
    def slice_test(self):
        # Slice stereo dataset
        dataset = SampledDataSet(data=[[1, 11], [2, 22], [3, 33], [4, 44], [5, 55], [6, 66], [7, 77], [8, 88]], sample_rate=2)
        dataset1 = dataset[1:3] # take a 2 second slice between time 1s and time 3s 
        self.assertEqual(dataset1.sample_rate, dataset.sample_rate)
        self.assertEqual(dataset1.data, [[3, 33], [4, 44], [5, 55], [6, 66]])
        self.assertEqual(dataset1.axes[0], [1, 1.5, 2, 2.5])

        # Slice mono dataset with start not on a sample
        dataset = SampledDataSet(data=[[1], [2], [3], [4], [5], [6], [7], [8]], sample_rate=2)
        dataset1 = dataset[0.99:3]
        self.assertEqual(dataset1.sample_rate, dataset.sample_rate)
        self.assertEqual(dataset1.data, [[3], [4], [5], [6]])
        self.assertEqual(dataset1.axes[0], [1, 1.5, 2, 2.5])

        # Slice mono dataset with only start
        dataset1 = dataset[0.51:]
        self.assertEqual(dataset1.sample_rate, dataset.sample_rate)
        self.assertEqual(dataset1.data, [[3], [4], [5], [6], [7], [8]])
        self.assertEqual(dataset1.axes[0], [1, 1.5, 2, 2.5, 3, 3.5])

        # Slice mono dataset with only stop
        dataset1 = dataset[:1.5]
        self.assertEqual(dataset1.sample_rate, dataset.sample_rate)
        self.assertEqual(dataset1.data, [[1], [2], [3]])
        self.assertEqual(dataset1.axes[0], [0, 0.5, 1])

        # Slice multi-dimensional dataset
        dataset = ThreeDDataSet(None, [0, 2], [1, 11, 111], data=[
            [[1, 11, 111], [111, 1111, 11111]],
            [[2, 22, 222], [222, 2222, 22222]],
            [[3, 33, 333], [333, 3333, 33333]],
            [[4, 44, 444], [444, 4444, 55555]],
        ], sample_rate=2)
        dataset1 = dataset.slice(1, 15, dimension=2) 
        self.assertEqual(dataset1.sample_rate, dataset.sample_rate)
        self.assertEqual(dataset1.data, 
            [[[1, 11], [111, 1111]],
             [[2, 22], [222, 2222]],
             [[3, 33], [333, 3333]],
             [[4, 44], [444, 4444]]])
        self.assertEqual(dataset1.axes[2], [1, 11])
    
    def sample_slice_test(self):
        # Slice stereo dataset
        dataset = SampledDataSet(data=[[1, 11], [2, 22], [3, 33], [4, 44], [5, 55], [6, 66], [7, 77], [8, 88]], sample_rate=2)
        dataset1 = dataset.sample_slice()
        self.assertEqual(dataset1.data, [[1, 11], [2, 22], [3, 33], [4, 44], [5, 55], [6, 66], [7, 77], [8, 88]])

        dataset1 = dataset.sample_slice(start=4)
        self.assertEqual(dataset1.data, [[5, 55], [6, 66], [7, 77], [8, 88]])

        dataset1 = dataset.sample_slice(end=4)
        self.assertEqual(dataset1.data, [[1, 11], [2, 22], [3, 33], [4, 44]])

        # Slice 3-d data set
        dataset = ThreeDDataSet(None, [0, 2], [1, 11, 111], data=[
            [[1, 11, 111], [111, 1111, 11111]],
            [[2, 22, 222], [222, 2222, 22222]],
            [[3, 33, 333], [333, 3333, 33333]],
            [[4, 44, 444], [444, 4444, 55555]],
        ], sample_rate=2)
        dataset1 = dataset.sample_slice(1, None, dimension=2) 
        self.assertEqual(dataset1.sample_rate, dataset.sample_rate)
        self.assertEqual(dataset1.data, [
            [[11, 111], [1111, 11111]],
            [[22, 222], [2222, 22222]],
            [[33, 333], [3333, 33333]],
            [[44, 444], [4444, 55555]],
        ])
        self.assertEqual(dataset1.axes[2], [11, 111])

    #def iter_frames_test(self):
    #    dataset = SampledDataSet(data=[[1, -11], [2, -22], [3, -33], [4, -44]], sample_rate=2)
    #    frames = []
    #    for frame in dataset.iter_frames():
    #        frames.append(frame)
    #    self.assertEqual(np.array(frames), [[0, 1, -11], [0.5, 2, -22], [1, 3, -33], [1.5, 4, -44]])

    def smooth_test(self):
        dataset = SampledDataSet(data=[[1, 4], [2, 1], [1, 3], [3, 1], [1, 4], [4, 1], [1, 8], [5, 1], [1, 7], [6, 1]], sample_rate=2)
        smoothen = dataset.smooth(window_size=4)
        smoothen.plot()
        
