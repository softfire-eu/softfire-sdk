import configparser
import logging
import logging.config
import os


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
