# config.py

import os
from configparser import ConfigParser

CONFIG_FILE = os.path.join(os.getcwd(), 'config.ini')

def load_config():
    parser = ConfigParser()
    parser.read(CONFIG_FILE, encoding='utf-8')
    cfg = {sec: dict(parser.items(sec)) for sec in parser.sections()}
    # убираем устаревшую секцию THEME, если она есть
    cfg.pop('THEME', None)
    return cfg

def save_config(cfg: dict):
    parser = ConfigParser()
    for section, vals in cfg.items():
        parser[section] = vals
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        parser.write(f)