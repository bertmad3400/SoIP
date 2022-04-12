class SoundOptions:
    SAMPLE_RATE = 8000
    CHANNELS = 1
    WORD_TYPE = "float32"
    BUFFER_SIZE = 1024

    def as_dict():
        return {
                "sample_rate" : SoundOptions.SAMPLE_RATE,
                "channels" : SoundOptions.CHANNELS,
                "word_type" : SoundOptions.WORD_TYPE,
                "buffer_size" : SoundOptions.BUFFER_SIZE
                }
