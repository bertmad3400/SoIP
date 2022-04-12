import logging

class ProtocolOptions:
    TIMEOUT = 15_000

def configure_logging():
    logging.basicConfig(format="[%(asctime)s] %(levelname)s: %(message)s", level=logging.DEBUG)
