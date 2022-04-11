from common import *

import numpy as np

class Client:
    def __init__(self):

        self.options = options.SoundOptions

        self.buffer = np.empty((self.options.BUFFER_SIZE, self.options.CHANNELS), dtype=self.options.WORD_TYPE)
