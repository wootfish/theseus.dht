from twisted.trial import unittest

import os
import tempfile
import shutil
import importlib


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "theseus_home")
        os.environ["THESEUSHOME"] = self.path

        # force a fresh load of the module, just in case it was imported (and
        # Config's class variables thus initialized) as part of a previous test
        import theseus.config
        importlib.reload(theseus.config)

    def test_suite(self):
        from theseus.config import config, Config

        self.assertEqual(config.theseus_dir, self.path)

        for key, value in Config.config_defaults.items():
            self.assertEqual(config[key], value)

        config["newkey"] = "newvalue"
        self.assertEqual(config.get("newkey"), "newvalue")
        self.assertEqual(config.get("nonkey"), None)

        config2 = Config()
        for key, value in Config.config_defaults.items():
            self.assertEqual(config2[key], value)
        self.assertEqual(config2.get("newkey"), "newvalue")
        self.assertEqual(config2["newkey"], "newvalue")

    def test_bad_config_file(self):
        from theseus.config import Config

        doomed_config = Config()
        doomed_config.config_file += "_bad"

        with open(doomed_config.config_file, "w+") as f:
            f.write("lol this is so totally not json")

        doomed_config._load_config()

        for key, value in Config.config_defaults.items():
            self.assertEqual(doomed_config[key], value)

    def tearDown(self):
        shutil.rmtree(self.path)
