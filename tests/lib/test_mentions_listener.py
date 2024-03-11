from pyxavi.config import Config
from pyxavi.storage import Storage
from pyxavi.queue_stack import Queue
from mastofeed.lib.publisher import Publisher
from mastofeed.lib.mentions_listener import MentionParser, Mention
from pyxavi.mastodon_helper import StatusPostVisibility
from logging import Logger as BuiltInLogger
from unittest.mock import patch
import copy
import pytest

CONFIG = {
    "logger": {
        "name": "custom_logger"
    },
    "feed_parser": {
        "storage_file": "feeds.yaml"
    },
    "app": {
        "user": "@feeder@social.arnaus.net",
        "admin": "@xavi@social.arnaus.net",
        "restrict_writes": True
    }
}

# This keeps the state of already seen
STORAGE = {}


@pytest.fixture(autouse=True)
def setup_function():

    global CONFIG
    global STORAGE

    backup_config = copy.deepcopy(CONFIG)
    backup_storage = copy.deepcopy(STORAGE)

    yield

    STORAGE = backup_storage
    CONFIG = backup_config


def patch_storage_read_file(self):
    self._content = STORAGE


def patched_publisher_init(
    self,
    config: Config,
    named_account: str = "default",
    base_path: str = None,
    only_oldest: bool = False,
    queue: Queue = None
):
    pass


@patch.object(Storage, "read_file", new=patch_storage_read_file)
@patch.object(Publisher, "__init__", new=patched_publisher_init)
def get_mention_parser() -> MentionParser:
    config = Config(params=CONFIG)

    return MentionParser(config=config)


def test_instantiation():

    instance = get_mention_parser()

    assert isinstance(instance, MentionParser)
    assert isinstance(instance._config, Config)
    assert isinstance(instance._logger, BuiltInLogger)
    assert isinstance(instance._publisher, Publisher)


def test_format_answer():

    instance = get_mention_parser()
    mention = Mention.from_dict(
        {
            "status_id": 123,
            "content": f"{instance.me} this is a meaningless test",
            "username": "xavi@social.arnaus.net",
            "visibility": StatusPostVisibility.PUBLIC
        }
    )
    instance.mention = mention
    text = "I am a text"

    assert f"@{mention.username} {text}" == instance._format_answer(text)


@pytest.mark.parametrize(
    argnames=('alias', 'expected_result'),
    argvalues=[
        ("example", True), ("not working", False), ("https-social-arnaus-net", True),
        ("https://social.arnaus.net", False)
    ],
)
def test_is_alias_valid(alias, expected_result):

    instance = get_mention_parser()

    assert instance.is_alias_valid(alias) is expected_result


@pytest.mark.parametrize(
    argnames=('username', 'expected_small'),
    argvalues=[
        ("@xavi@social.arnaus.net", "@xavi"), ("xavi@social.arnaus.net", "@xavi"),
        ("@xavi", "@xavi"), ("xavi", "@xavi")
    ],
)
def test_small_user(username, expected_small):

    instance = get_mention_parser()

    assert instance.small_user(username) == expected_small


@pytest.mark.parametrize(
    argnames=('username', 'expected_result'),
    argvalues=[
        ("xavi@social.arnaus.net", True), ("pepe@social.arnaus.net", False), ("xavi", True),
        ("pepe", False)
    ],
)
def test_user_can_write(username, expected_result):

    instance = get_mention_parser()
    mention = Mention.from_dict(
        {
            "status_id": 123,
            "content": f"{instance.me} this is a meaningless test",
            "username": username,
            "visibility": StatusPostVisibility.PUBLIC
        }
    )
    instance.mention = mention

    assert instance.user_can_write() == expected_result


@pytest.mark.parametrize(
    argnames=('content', 'expected_result'),
    argvalues=[
        ("add https://google.com alias \"Xavi's blog\"", "Xavi's blog"),
        ("add https://google.com alias \"12345\"", "12345"),
        ("add https://google.com alias", None),
        ("add https://google.com alias \"Terence Eden’s Blog\"", "Terence Eden’s Blog"),
    ],
)
def test_get_text_inside_quotes(content, expected_result):

    instance = get_mention_parser()

    assert instance.get_text_inside_quotes(f"@feeder {content}") == expected_result


@pytest.mark.parametrize(
    argnames=('content', 'expected_position', 'expected_content'),
    argvalues=[
        (
            "@feeder add https://xavier.arnaus.net/blog alias \"Xavi's blog\"",
            0,
            "add https://xavier.arnaus.net/blog alias \"Xavi's blog\""
        ),
        ("Ola @feeder k ase", 4, "Ola k ase"),
        ("Ola k ase", -1, "Ola k ase"),
    ],
)
def test_remove_self_username_from_content(content, expected_position, expected_content):

    instance = get_mention_parser()

    assert instance.remove_self_username_from_content(content) == (
        expected_position, expected_content
    )
