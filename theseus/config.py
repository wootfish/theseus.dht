"""
config.py

Provides a simple, no-fuss interface for accessing configuration settings from
a local config directory.

Default directory is os.path.expanduser("~/.theseus").

Suggested usage:

    # to import correctly:
    from .config import config

    # to access config values
    value = config["key"]

    # to set (and save!) a config value
    config["key"] = newval

"""

from twisted.logger import Logger

import os
import json


class Config:
    log = Logger()

    theseus_dir = os.path.expanduser(os.getenv("THESEUSHOME", "~/.theseus/"))
    config_file = os.path.join(theseus_dir, "theseus_config")
    data_file = os.path.join(theseus_dir, "data_store")

    config_defaults = {
        "config_version": "1",
        "protocol_version": "0",
        "listen_port_range": [1337, 42000],
        "ports_to_avoid": [
            1080, 1093, 1094, 1099, 1109, 1127, 1178, 1194, 1210, 1214, 1236, 1241,
            1300, 1313, 1314, 1352, 1433, 1434, 1524, 1525, 1529, 1645, 1646, 1649,
            1677, 1701, 1812, 1813, 1863, 1957, 1958, 1959, 2000, 2003, 2010, 2049,
            2053, 2086, 2101, 2102, 2103, 2104, 2105, 2111, 2119, 2121, 2135, 2150,
            2401, 2430, 2431, 2432, 2433, 2583, 2600, 2601, 2602, 2603, 2604, 2605,
            2606, 2607, 2608, 2628, 2792, 2811, 2947, 2988, 2989, 3050, 3130, 3260,
            3306, 3493, 3632, 3689, 3690, 4031, 4094, 4190, 4224, 4353, 4369, 4373,
            4500, 4557, 4559, 4569, 4600, 4691, 4899, 4949, 5002, 5050, 5051, 5052,
            5060, 5061, 5151, 5190, 5222, 5269, 5308, 5353, 5354, 5355, 5432, 5555,
            5556, 5666, 5667, 5671, 5672, 5674, 5675, 5680, 5688, 6000, 6001, 6002,
            6003, 6004, 6005, 6006, 6007, 6346, 6347, 6444, 6445, 6446, 6514, 6566,
            6667, 7001, 7002, 7003, 7004, 7005, 7006, 7007, 7008, 7009, 7100, 8021,
            8080, 8081, 8088, 9098, 9101, 9102, 9103, 9359, 9418, 9667, 9673,
            10000, 10050, 10051, 10080, 10081, 10082, 10083, 10809, 11112, 11201,
            11371, 13720, 13721, 13722, 13724, 13782, 13783, 15345, 17001, 17002,
            17003, 17004, 17500, 20011, 20012, 22125, 22128, 22273, 24554, 27374,
            30865, 57000, 60177, 60179
            ]
    }

    def __init__(self):
        self._load_config()

    def __getitem__(self, key):
        return self._config[key]

    def __setitem__(self, key, value):
        self._config[key] = value
        self._write_config()

    def get(self, key, default=None):
        return self._config.get(key, default)

    def _write_config(self):
        with open(self.config_file, "w+") as f:
            f.write(json.dumps(self._config, sort_keys=True, indent=4))
            f.write("\n")

    def _load_config(self):
        # check whether config dir exists yet
        if not os.path.isdir(self.theseus_dir):
            self.log.info("Config dir not found at {path} -- creating...", path=self.theseus_dir)
            os.mkdir(self.theseus_dir)

        # load config file if it exists, else create it
        if os.path.exists(self.config_file):
            self.log.info("Loading config file from {path}", path=self.config_file)
            try:
                with open(self.config_file) as f:
                    contents = f.read()
                json_contents = json.loads(contents)
            except:
                self.log.warn("Bad config file at {path}", path=self.config_file)
            else:
                self._config = self.dict_merge(
                        self.config_defaults,
                        json_contents,
                        )
                return  # success!

        self._config = self.config_defaults.copy()
        self.log.info("Config file not found at {path} -- creating...", path=self.config_file)
        self._write_config()

    @staticmethod
    def dict_merge(dic1, dic2):
        """
        Merges two dictionaries together -- and if they have sub-dictionaries
        under the same key, it merges those too! The merge is returned. Neither
        of the source dictionaries are modified.
        """

        merged = dic1.copy()
        for k in dic2:
            if isinstance(dic2[k], dict) and k in dic1 and isinstance(dic1[k], dict):
                merged[k] = Config.dict_merge(dic1[k], dic2[k])
            else:
                merged[k] = dic2[k]
        return merged


config = Config()
