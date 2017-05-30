import configparser
import logging
import logging.config
import os

from sdk.softfire.grpc import messages_pb2

TESTBED_MAPPING = {
    'fokus': messages_pb2.FOKUS,
    'fokus-dev': messages_pb2.FOKUS_DEV,
    'ericsson': messages_pb2.ERICSSON,
    'ericsson-dev': messages_pb2.ERICSSON_DEV,
    'surrey': messages_pb2.SURREY,
    'surrey-dev': messages_pb2.SURREY_DEV,
    'ads': messages_pb2.ADS,
    'ads-dev': messages_pb2.ADS_DEV,
    'dt': messages_pb2.DT,
    'dt-dev': messages_pb2.DT_DEV,
    'any': messages_pb2.ANY
}


def get_config_parser(config_file_path):
    """
    Get the ConfigParser object containing the system configurations

    :return: ConfigParser object containing the system configurations
    """
    config = configparser.ConfigParser()
    if os.path.exists(config_file_path) and os.path.isfile(config_file_path):
        config.read(config_file_path)
        return config
    else:
        logging.error("Config file not found, please create %s" % config_file_path)
        exit(1)


def get_config(section, key, config_file_path, default=None):
    config = get_config_parser(config_file_path)
    if default is None:
        return config.get(section=section, option=key)
    try:
        return config.get(section=section, option=key)
    except configparser.NoOptionError:
        return default
