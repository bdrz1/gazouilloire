import json
import os
import sys
from shutil import copyfile
import logging
from datetime import datetime

log = logging.getLogger("gazouilloire")
log.setLevel(logging.INFO)

# create console handler with the lowest log level
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
log.addHandler(console_handler)


def create_file_handler(path):
    # create file handler for logs in daemon mode
    file_path = os.path.join(
        os.path.realpath(path),
        "logs",
        datetime.strftime(datetime.now(), "%Y%m%d-%H%M.log")
    )
    log.info("From now on, logs will print to {}".format(file_path))
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    file_handler = logging.FileHandler(file_path)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    log.addHandler(file_handler)


def load_conf(dir_path, daemon=False):
    file_path = os.path.join(os.path.realpath(dir_path), "config.json")
    if os.path.isfile(file_path):
        try:
            with open(file_path, "r") as confile:
                conf =  required_format(json.load(confile))
        except Exception as e:
            log.error('Could not open %s: %s %s' % (file_path, type(e), e))
            sys.exit(1)
        if daemon:
            create_file_handler(dir_path)
        return conf
    else:
        log.error('file {} does not exist. Try running the following command:\ngazouilloire init <your_path>'
                  .format(file_path))
        sys.exit(1)


def create_conf_example(dir_path):
    file_path = os.path.join(dir_path, "config.json")
    if not os.path.isfile(file_path):
        copyfile(os.path.join(os.path.dirname(__file__), "config.json.example"), file_path)
    else:
        log.warning('A file named config.json already exists in %s' % os.path.realpath(dir_path))


def required_format(conf):
    subfields = {
        "twitter": ["key", "secret", "oauth_token", "oauth_secret"],
        "database": ["host", "port", "db_name"],
        "timezone": []
    }
    for field in subfields:
        if field not in conf:
            log.error('required element %s is missing in config.json' % field)
            sys.exit(1)
        for subfield in subfields[field]:
            if subfield not in conf[field]:
                log.error('required element %s is missing in config.json' % subfield)
                sys.exit(1)
    query_terms = ['keywords', 'url_pieces', 'time_limited_keywords']
    for k in query_terms:
        if k not in conf:
            conf[k] = []
    if all(len(conf[k]) == 0 for k in query_terms):
        log.error(
            'at least one of the query fields (keywords, url_pieces, time_limited_keywords) must be filled in '
            'in config.json '
        )
        sys.exit(1)
    if conf["debug"]:
        log.setLevel(logging.DEBUG)
    return conf
