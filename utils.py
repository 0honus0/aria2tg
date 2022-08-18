import yaml
import math
import os.path
import hashlib

def dfs_showdir(path : str , depth : int) -> str:
    text = ""
    if depth == 0:
        text += "" + path + "\n"
 
    for item in os.listdir(path):
        text += "|  " * depth + "|--" + item + "\n"

        newitem = path +'/'+ item
        if os.path.isdir(newitem):
            dfs_showdir(newitem, depth +1)
    return text

def load_config() -> dict:
    with open("config.yaml") as f:
        config = yaml.safe_load(f)
    return config

def pybyte(size : float , dot : int = 2 ) -> float:
    size = float(size)
    if 0 <= size < 1:
        human_size = str(round(size / 0.125, dot)) + 'b'
    elif 1 <= size < 1024:
        human_size = str(round(size, dot)) + 'B'
    elif math.pow(1024, 1) <= size < math.pow(1024, 2):
        human_size = str(round(size / math.pow(1024, 1), dot)) + 'KB'
    elif math.pow(1024, 2) <= size < math.pow(1024, 3):
        human_size = str(round(size / math.pow(1024, 2), dot)) + 'MB'
    elif math.pow(1024, 3) <= size < math.pow(1024, 4):
        human_size = str(round(size / math.pow(1024, 3), dot)) + 'GB'
    elif math.pow(1024, 4) <= size < math.pow(1024, 5):
        human_size = str(round(size / math.pow(1024, 4), dot)) + 'TB'
    else:
        raise ValueError('{}() takes number than or equal to 0, but less than 0 given.'.format(size))
    return human_size

def md5( string : str) -> str:
    return hashlib.md5(string.encode('utf-8')).hexdigest()[8:-8]