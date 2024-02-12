from pyxavi.config import Config
from pyxavi.storage import Storage
from pyxavi.queue_stack import Queue
from mastofeed.runners.main import Main
from mastofeed.runners.runner_protocol import RunnerProtocol
from mastofeed.lib.publisher import Publisher
from logging import Logger as BuiltInLogger, getLogger
from unittest.mock import patch, Mock
from unittest import TestCase
import copy
import pytest

CONFIG = {
    "logger": {
        "name": "custom_logger"
    },
    "telegram_parser": {
        "storage_file": "telegram.yaml",
        "api_id": "123",
        "api_hash": "abcdef1234567890",
        "ignore_offsets": False,
        "channels": [{
            "id": -12345678, "name": "News", "show_name": True
        }]
    },
    "feed_parser": {
        "storage_file": "feeds.yaml",
        "sites": [
            {
                "name": "News",
                "url": "https://www.example.cat/rss/my_feed",
                "language_default": "ca_ES",
                "keywords_filter_profile": "talamanca",
                "show_name": True
            }
        ]
    },
    "app": {
        "name": "Test"
    },
    "mastodon": {
        "named_accounts": {
            "default": {
                "api_base_url": "https://mastodont.cat",
                "instance_type": "mastodon",
                "credentials": {
                    "client_file": "client.secret",
                    "user_file": "user.secret",
                },
                "user": {
                    "email": "bot+syscheck@my-fancy.site",
                    "password": "SuperSecureP4ss",
                }
            }
        }
    },
    "publisher": {
        "media_storage": "storage/media/",
        # This is the old parameter, set in this Publisher class
        "only_older_toot": False,
        # This is the new parameter, set in pyxavi's Publisher class
        "only_oldest_post_every_iteration": False,
        "dry_run": False
    },
    "queue_storage": {
        "file": "storage/queue_file.yaml"
    }
}

# This keeps the state of already seen
STORAGE = {}

@pytest.fixture(autouse=True)
def setup_function():

    global CONFIG

    backup_config = copy.deepcopy(CONFIG)

    yield

    CONFIG = backup_config

def patch_storage_read_file(self):
    self._content = STORAGE

@patch.object(Storage, "read_file", new=patch_storage_read_file)
def get_instance() -> Main:
    config = Config(params=CONFIG)
    logger = getLogger(name=CONFIG["logger"]["name"])

    return Main(config=config, logger=logger)

def test_instantiation():

    instance = get_instance()

    assert isinstance(instance, Main)
    assert isinstance(instance, RunnerProtocol)
    assert isinstance(instance._config, Config)
    assert isinstance(instance._logger, BuiltInLogger)
    assert isinstance(instance._publisher, Publisher)
    assert isinstance(instance._queue, Queue)

@patch.object(Storage, "read_file", new=patch_storage_read_file)
def test_instance_() -> Main:
    config = Config(params=CONFIG)
    logger = getLogger(name=CONFIG["logger"]["name"])

    return Main(config=config, logger=logger)