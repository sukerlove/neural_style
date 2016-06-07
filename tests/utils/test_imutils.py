import os, sys, unittest
import numpy as np

dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(dir + '/../..')

from utils.imutils import (load_images, load_image, load_mean, 
                            preprocess, deprocess, create_noise_tensor)
from scipy import misc

from keras import backend as K

dir = os.path.dirname(os.path.realpath(__file__))

class TestImUtils(unittest.TestCase):

    def test_load_mean_tf(self):
        mean = load_mean()
        real_mean = np.array([[[[103.939, 116.779, 123.68]]]])

        self.assertEqual(True, (mean==real_mean).all())

    def test_load_mean_th(self):
        mean = load_mean(dim_ordering='th')
        real_mean = np.array([[[[103.939]], [[116.779]], [[123.68]]]])

        self.assertEqual(True, (mean==real_mean).all())

    # def test_load_mean_exception(self):
    #     self.assertRaises(Exception, load_mean('test'))

    def test_preprocess_tf(self):
        blue_im = misc.imread(dir + '/../fixture/blue.png')
        red_im = np.array(misc.imread(dir + '/../fixture/red.png').astype(K.floatx()))
        red_im = (red_im - load_mean()[0]).astype('uint8')
        new_red_im = preprocess(blue_im, dim_ordering='tf').astype('uint8')

        self.assertEqual(True, (red_im==new_red_im).all())

    def test_load_image(self):
        blue_im = load_image(dir + '/../fixture/blue.png')

        self.assertEqual(blue_im.shape, (600, 600, 3))

    def test_load_image_th(self):
        blue_im = load_image(dir + '/../fixture/blue.png', dim_ordering='th')

        self.assertEqual(blue_im.shape, (3, 600, 600))

    def test_load_images(self):
        files = load_images(dir + '/../fixture')

        self.assertEqual(files.shape, (4, 600, 600, 3))

    def test_load_images_limit(self):
        file = load_images(dir + '/../fixture', 1)

        self.assertEqual(file.shape, (1, 600, 600, 3))

    def test_deprocess(self):
        blue_im = misc.imread(dir + '/../fixture/blue.png')
        im = preprocess(blue_im)
        im = deprocess(im)

        self.assertEqual(True, (blue_im==im).all())

    def test_create_noise_tensor(self):
        file = create_noise_tensor(4, 5 ,3)
        self.assertEqual(file.shape, (1, 4, 5, 3))
        

if __name__ == '__main__':
    unittest.main()