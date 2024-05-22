from configparser import ConfigParser
import os


def initialize_config():
    """ Parse env variables or config file to find program config params

    Function that search and parse program configuration parameters in the
    program environment variables first and the in a config file.
    If at least one of the config parameters is not found a KeyError exception
    is thrown. If a parameter could not be parsed, a ValueError is thrown.
    If parsing succeeded, the function returns a ConfigParser object
    with config parameters
    """

    config = ConfigParser(os.environ)
    # If config.ini does not exists original config object is not modified
    config.read("config.ini")

    config_params = {}
    try:
        config_params["token"] = os.getenv("TOKEN", config["DEFAULT"]["TOKEN"])
        config_params["logging_level"] = os.getenv(
            'LOGGING_LEVEL', config["DEFAULT"]["LOGGING_LEVEL"])
        config_params["log_file"] = os.getenv(
            'LOG_FILE', config["DEFAULT"]["LOG_FILE"])

        config_params["env"] = os.getenv(
            'ENV', config["DEFAULT"]["ENV"])

        config_params["port"] = os.getenv(
            'PORT', config["DEFAULT"]["PORT"])

    except KeyError as e:
        raise KeyError(
            "Key was not found. Error: {} .Aborting server".format(e))

    return config_params
