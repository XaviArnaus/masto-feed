from pyxavi.config import Config
from pyxavi.storage import Storage
from pyxavi.queue_stack import Queue
from pyxavi.url import Url
from mastofeed.lib.publisher import Publisher
from mastofeed.lib.mentions_listener import MentionParser, Mention, MentionAction
from pyxavi.mastodon_helper import StatusPostVisibility
from logging import Logger as BuiltInLogger
from unittest.mock import patch, Mock
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
        ("@feeder@social.arnaus.net list", 0, "list"),
        ("Ola @feeder@social.arnaus.net k ase", 4, "Ola k ase"),
        ("Ola k ase", -1, "Ola k ase"),
    ],
)
def test_remove_self_username_from_content(content, expected_position, expected_content):

    instance = get_mention_parser()

    assert instance.remove_self_username_from_content(content) == (
        expected_position, expected_content
    )


@pytest.mark.parametrize(
    argnames=(
        'content',
        'action',
        'complements',
        'error',
        'returned',
        'is_a_valid_feed',
        'findfeeds',
        "username"
    ),
    argvalues=[
        # An example of a correct full normal one
        (
            "@feeder add https://xavier.arnaus.net/blog xavi \"Xavi's blog\"",
            MentionAction.ADD,
            {
                "alias": "xavi",
                "site_url": "https://xavier.arnaus.net/blog",
                "feed_url": "https://xavier.arnaus.net/blog.rss",
                "name": "Xavi's blog"
            },
            None,  # No error
            True,  # return for parse()
            False,  # The site_url is not a valid feed itself
            ["https://xavier.arnaus.net/blog.rss", "https://xavier.arnaus.net/blog.atom"],
            "@xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Content comes with HTML, even invalid, once cleaned has an action
        (
            "<p><small>@feeder</small> <strong>list</strong>",
            MentionAction.LIST,
            {},  # No complements
            None,  # No error
            True,  # return for parse()
            False,  # The site_url is not a valid feed itself
            [],  # No Feeds found
            "@xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Content comes with HTML, once cleaned does not have an action
        (
            "<p><small>@feeder</small> <strong>unknown</strong>",
            None,  # No action
            {},  # No complements
            MentionParser.ERROR_INVALID_ACTION,  # No action error
            False,  # return for parse()
            False,  # The site_url is not a valid feed itself
            [],  # No Feeds found
            "@xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # It's an organic mention, does not mean an action
        (
            "I am working in my @feeder project",
            None,  # No action
            {},  # No complements
            MentionParser.ERROR_NO_COMMAND,  # No command error
            False,  # return for parse()
            False,  # The site_url is not a valid feed itself
            [],  # No Feeds found
            "@xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # The mention does not come with any other word
        (
            "@feeder",
            None,  # No action
            {},  # No complements
            MentionParser.ERROR_NO_COMMAND,  # No command error
            False,  # return for parse()
            False,  # The site_url is not a valid feed itself
            [],  # No Feeds found
            "@xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # The first word after the non-organic mention is not an action
        (
            "@feeder caca",
            None,  # No action
            {},  # No complements
            MentionParser.ERROR_INVALID_ACTION,  # No action error
            False,  # return for parse()
            False,  # The site_url is not a valid feed itself
            [],  # No Feeds found
            "@xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action HELLO, nice and clean
        (
            "@feeder hello",
            MentionAction.HELLO,  # hello
            {},  # No complements
            None,  # No error
            True,  # return for parse()
            False,  # The site_url is not a valid feed itself
            [],  # No Feeds found
            "@xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action HELLO, whatever comes after the action is ignored
        (
            "@feeder hello everybody",
            MentionAction.HELLO,  # hello
            {},  # No complements
            None,  # No error
            True,  # return for parse()
            False,  # The site_url is not a valid feed itself
            [],  # No Feeds found
            "@xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action LIST, nice and clean
        (
            "@feeder list",
            MentionAction.LIST,  # list
            {},  # No complements
            None,  # No error
            True,  # return for parse()
            False,  # The site_url is not a valid feed itself
            [],  # No Feeds found
            "@xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action LIST, whatever comes after the action is ignored
        (
            "@feeder list me everything you have",
            MentionAction.LIST,  # list
            {},  # No complements
            None,  # No error
            True,  # return for parse()
            False,  # The site_url is not a valid feed itself
            [],  # No Feeds found
            "@xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action ADD, missing parameters
        (
            "@feeder add",
            MentionAction.ADD,  # add
            {},  # No complements
            MentionParser.ERROR_MISSING_PARAMS,
            False,  # return for parse()
            False,  # The site_url is not a valid feed itself
            [],  # No Feeds found
            "@xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action ADD, the site URL is invalid. The schema is mandatory
        (
            "@feeder add xavi.com",
            MentionAction.ADD,  # add
            {},  # No complements
            MentionParser.ERROR_INVALID_URL,
            False,  # return for parse()
            False,  # The site_url is not a valid feed itself
            [],  # No Feeds found
            "@xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action ADD, the site URL is invalid. Random 1
        (
            "@feeder add http://xavi,com",
            MentionAction.ADD,  # add
            {},  # No complements
            MentionParser.ERROR_INVALID_URL,
            False,  # return for parse()
            False,  # The site_url is not a valid feed itself
            [],  # No Feeds found
            "@xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action ADD, the site URL is also the feed URL
        (
            "@feeder add https://xavier.arnaus.net/blog.rss",
            MentionAction.ADD,  # add
            {
                "alias": "https-xavier-arnaus-net-blog-rss",
                "site_url": "https://xavier.arnaus.net/blog.rss",
                "feed_url": "https://xavier.arnaus.net/blog.rss",
                "name": None
            },
            None,
            True,  # return for parse()
            True,  # The site_url is a valid feed itself
            [],  # No Feeds found
            "@xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action ADD, the feed URL is discovered, taking the first item
        (
            "@feeder add https://xavier.arnaus.net/blog",
            MentionAction.ADD,  # add
            {
                "alias": "https-xavier-arnaus-net-blog-rss",
                "site_url": "https://xavier.arnaus.net/blog",
                "feed_url": "https://xavier.arnaus.net/blog.rss",
                "name": None
            },
            None,
            True,  # return for parse()
            False,  # The site_url is not a valid feed itself
            ["https://xavier.arnaus.net/blog.rss", "https://xavier.arnaus.net/blog.atom"],
            "@xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action ADD, the site URL is also the feed URL. Defining alias.
        (
            "@feeder add https://xavier.arnaus.net/blog.rss xavi",
            MentionAction.ADD,  # add
            {
                "alias": "xavi",
                "site_url": "https://xavier.arnaus.net/blog.rss",
                "feed_url": "https://xavier.arnaus.net/blog.rss",
                "name": None
            },
            None,
            True,  # return for parse()
            True,  # The site_url is a valid feed itself
            [],  # No Feeds found
            "@xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action ADD, the site URL is also the feed URL. Defining invalid alias.
        (
            "@feeder add https://xavier.arnaus.net/blog.rss xavi's",
            MentionAction.ADD,  # add
            {},  # when error, there are no complements
            MentionParser.ERROR_INVALID_ALIAS,
            False,  # return for parse()
            True,  # The site_url is a valid feed itself
            [],  # No Feeds found
            "@xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action ADD, the site URL is also the feed URL. Defining existing alias.
        (
            "@feeder add https://xavier.arnaus.net/blog.rss existing-key",
            MentionAction.ADD,  # add
            {},  # when error, there are no complements
            MentionParser.ERROR_ALIAS_ALREADY_EXISTS,
            False,  # return for parse()
            True,  # The site_url is a valid feed itself
            [],  # No Feeds found
            "@xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action ADD, the site URL is also the feed URL. Defining name.
        (
            "@feeder add https://xavier.arnaus.net/blog.rss \"Xavi's blog\"",
            MentionAction.ADD,  # add
            {
                "alias": "https-xavier-arnaus-net-blog-rss",
                "site_url": "https://xavier.arnaus.net/blog.rss",
                "feed_url": "https://xavier.arnaus.net/blog.rss",
                "name": "Xavi's blog"
            },
            None,
            True,  # return for parse()
            True,  # The site_url is a valid feed itself
            [],  # No Feeds found
            "@xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action ADD, the site URL is also the feed URL. Defining alias and name.
        (
            "@feeder add https://xavier.arnaus.net/blog.rss xavi \"Xavi's blog\"",
            MentionAction.ADD,  # add
            {
                "alias": "xavi",
                "site_url": "https://xavier.arnaus.net/blog.rss",
                "feed_url": "https://xavier.arnaus.net/blog.rss",
                "name": "Xavi's blog"
            },
            None,
            True,  # return for parse()
            True,  # The site_url is a valid feed itself
            [],  # No Feeds found
            "@xavi@social.arnaus.net"  # Who is actually mentioning
        ),
    ],
)
def test_parse(
    content: str,
    action: str,
    complements: dict,
    error: str,
    returned: bool,
    is_a_valid_feed: bool,
    findfeeds: list,
    username: str
):

    # Set up the mentioning environment
    instance = get_mention_parser()
    mention = Mention.from_dict(
        {
            "status_id": 1234,
            "content": content,
            "username": username,
            "visibility": StatusPostVisibility.PUBLIC
        }
    )
    instance.mention = mention
    instance._feeds_storage.set("existing-key", {})

    # Mock the external calls and trigger the parse
    mocked_url_findfeeds = Mock()
    mocked_url_findfeeds.return_value = findfeeds
    mocked_url_is_a_valid_feed = Mock()
    mocked_url_is_a_valid_feed.return_value = is_a_valid_feed
    with patch.object(Url, "findfeeds", new=mocked_url_findfeeds):
        with patch.object(Url, "is_a_valid_feed", new=mocked_url_is_a_valid_feed):
            parsed_result = instance.parse()

    # Assert that the parse outcomed what we expect
    assert instance.action == action
    assert instance.complements == complements
    assert instance.error == error
    assert parsed_result == returned
