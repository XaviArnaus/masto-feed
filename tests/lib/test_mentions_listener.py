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
        "admin": "xavi@social.arnaus.net",
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
        ("xavi@social.arnaus.net", "@xavi"), ("xavi@social.arnaus.net", "@xavi"),
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
            "xavi@social.arnaus.net"  # Who is actually mentioning
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
            "xavi@social.arnaus.net"  # Who is actually mentioning
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
            "xavi@social.arnaus.net"  # Who is actually mentioning
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
            "xavi@social.arnaus.net"  # Who is actually mentioning
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
            "xavi@social.arnaus.net"  # Who is actually mentioning
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
            "xavi@social.arnaus.net"  # Who is actually mentioning
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
            "xavi@social.arnaus.net"  # Who is actually mentioning
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
            "xavi@social.arnaus.net"  # Who is actually mentioning
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
            "xavi@social.arnaus.net"  # Who is actually mentioning
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
            "xavi@social.arnaus.net"  # Who is actually mentioning
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
            "xavi@social.arnaus.net"  # Who is actually mentioning
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
            "xavi@social.arnaus.net"  # Who is actually mentioning
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
            "xavi@social.arnaus.net"  # Who is actually mentioning
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
            "xavi@social.arnaus.net"  # Who is actually mentioning
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
            "xavi@social.arnaus.net"  # Who is actually mentioning
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
            "xavi@social.arnaus.net"  # Who is actually mentioning
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
            "xavi@social.arnaus.net"  # Who is actually mentioning
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
            "xavi@social.arnaus.net"  # Who is actually mentioning
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
            "xavi@social.arnaus.net"  # Who is actually mentioning
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
            "xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action UPDATE, missing parameters
        (
            "@feeder update",
            MentionAction.UPDATE,  # update
            {},  # No complements
            MentionParser.ERROR_MISSING_PARAMS,
            False,  # return for parse()
            False,  # The site_url is not a valid feed itself
            [],  # No Feeds found
            "xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action UPDATE, the key does not exist
        (
            "@feeder update xavi",
            MentionAction.UPDATE,  # update
            {},  # No complements
            MentionParser.ERROR_NOT_FOUND_ALIAS,
            False,  # return for parse()
            False,  # The site_url is not a valid feed itself
            [],  # No Feeds found
            "xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action UPDATE, we have an alias but not what to update
        (
            "@feeder update existing-key",
            MentionAction.UPDATE,  # update
            {},  # No complements
            MentionParser.ERROR_MISSING_PARAMS,
            False,  # return for parse()
            False,  # The site_url is not a valid feed itself
            [],  # No Feeds found
            "xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action UPDATE, the site URL is invalid. The schema is mandatory
        (
            "@feeder update existing-key xavi.com",
            MentionAction.UPDATE,  # update
            {},  # No complements
            MentionParser.ERROR_INVALID_URL,
            False,  # return for parse()
            False,  # The site_url is not a valid feed itself
            [],  # No Feeds found
            "xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action UPDATE, the site URL is invalid. Random 1
        (
            "@feeder update existing-key http://xavi,com",
            MentionAction.UPDATE,  # update
            {},  # No complements
            MentionParser.ERROR_INVALID_URL,
            False,  # return for parse()
            False,  # The site_url is not a valid feed itself
            [],  # No Feeds found
            "xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action UPDATE, the site URL is also the feed URL
        (
            "@feeder update existing-key https://xavier.arnaus.net/blog.rss",
            MentionAction.UPDATE,  # update
            {
                "alias": "existing-key",
                "site_url": "https://xavier.arnaus.net/blog.rss",
                "feed_url": "https://xavier.arnaus.net/blog.rss",
                "name": None
            },
            None,
            True,  # return for parse()
            True,  # The site_url is a valid feed itself
            [],  # No Feeds found
            "xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action UPDATE, the feed URL is discovered, taking the first item
        (
            "@feeder update existing-key https://xavier.arnaus.net/blog",
            MentionAction.UPDATE,  # update
            {
                "alias": "existing-key",
                "site_url": "https://xavier.arnaus.net/blog",
                "feed_url": "https://xavier.arnaus.net/blog.rss",
                "name": None
            },
            None,
            True,  # return for parse()
            False,  # The site_url is not a valid feed itself
            ["https://xavier.arnaus.net/blog.rss", "https://xavier.arnaus.net/blog.atom"],
            "xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action UPDATE, the site URL is also the feed URL. Defining name.
        (
            "@feeder update existing-key https://xavier.arnaus.net/blog.rss \"Xavi's blog\"",
            MentionAction.UPDATE,  # update
            {
                "alias": "existing-key",
                "site_url": "https://xavier.arnaus.net/blog.rss",
                "feed_url": "https://xavier.arnaus.net/blog.rss",
                "name": "Xavi's blog"
            },
            None,
            True,  # return for parse()
            True,  # The site_url is a valid feed itself
            [],  # No Feeds found
            "xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action TEST, missing parameters
        (
            "@feeder test",
            MentionAction.TEST,  # test
            {},  # No complements
            MentionParser.ERROR_MISSING_PARAMS,
            False,  # return for parse()
            False,  # The site_url is not a valid feed itself
            [],  # No Feeds found
            "xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action TEST, the site URL is invalid. The schema is mandatory
        (
            "@feeder test xavi.com",
            MentionAction.TEST,  # test
            {},  # No complements
            MentionParser.ERROR_INVALID_URL,
            False,  # return for parse()
            False,  # The site_url is not a valid feed itself
            [],  # No Feeds found
            "xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action TEST, the site URL is invalid. Random 1
        (
            "@feeder test http://xavi,com",
            MentionAction.TEST,  # test
            {},  # No complements
            MentionParser.ERROR_INVALID_URL,
            False,  # return for parse()
            False,  # The site_url is not a valid feed itself
            [],  # No Feeds found
            "xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action TEST, the site URL is also the feed URL
        (
            "@feeder test https://xavier.arnaus.net/blog.rss",
            MentionAction.TEST,  # test
            {
                "site_url": "https://xavier.arnaus.net/blog.rss",
                "feed_url": "https://xavier.arnaus.net/blog.rss"
            },
            None,
            True,  # return for parse()
            True,  # The site_url is a valid feed itself
            [],  # No Feeds found
            "xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action TEST, the feed URL is discovered, taking the first item
        (
            "@feeder test https://xavier.arnaus.net/blog",
            MentionAction.TEST,  # test
            {
                "site_url": "https://xavier.arnaus.net/blog",
                "feed_url": "https://xavier.arnaus.net/blog.rss"
            },
            None,
            True,  # return for parse()
            False,  # The site_url is not a valid feed itself
            ["https://xavier.arnaus.net/blog.rss", "https://xavier.arnaus.net/blog.atom"],
            "xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action REMOVE, missing parameters
        (
            "@feeder remove",
            MentionAction.REMOVE,  # remove
            {},  # No complements
            MentionParser.ERROR_MISSING_PARAMS,
            False,  # return for parse()
            False,  # The site_url is not a valid feed itself
            [],  # No Feeds found
            "xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action REMOVE, the key does not exist
        (
            "@feeder remove xavi",
            MentionAction.REMOVE,  # remove
            {},  # No complements
            MentionParser.ERROR_NOT_FOUND_ALIAS,
            False,  # return for parse()
            False,  # The site_url is not a valid feed itself
            [],  # No Feeds found
            "xavi@social.arnaus.net"  # Who is actually mentioning
        ),
        # Action REMOVE, we have an alias
        (
            "@feeder remove existing-key",
            MentionAction.REMOVE,  # remove
            {
                "alias": "existing-key"
            },
            None,
            True,  # return for parse()
            False,  # The site_url is not a valid feed itself
            [],  # No Feeds found
            "xavi@social.arnaus.net"  # Who is actually mentioning
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


@pytest.mark.parametrize(
    argnames=(
        'content',
        'action',
        'complements',
        'error',
        'returned',
        'user_can_write',
        'status',
        "username",
        "entry"
    ),
    argvalues=[
        # Action ADD, an example of a correct full normal one
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
            True,  # return for execute()
            True,  # The user has rights to write
            f"@xavi@social.arnaus.net {MentionParser.INFO_ADDED}",
            "xavi@social.arnaus.net",  # Who is actually mentioning
            {
                "xavi": {
                    "site_url": "https://xavier.arnaus.net/blog",
                    "feed_url": "https://xavier.arnaus.net/blog.rss",
                    "name": "Xavi's blog"
                }
            }
        ),
        # Action ADD, the user does not have rights to write
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
            True,  # return for execute()
            False,  # The user does not rights to write
            f"@xavi@social.arnaus.net {MentionParser.ERROR_NOT_ALLOWED}",
            "xavi@social.arnaus.net",  # Who is actually mentioning
            {
                "xavi": {
                    "site_url": "https://xavier.arnaus.net/blog",
                    "feed_url": "https://xavier.arnaus.net/blog.rss",
                    "name": "Xavi's blog"
                }
            }
        ),
        # Action UPDATE, correct and success
        (
            "@feeder update xavi https://xavier.arnaus.net/blog \"Xavi's blog\"",
            MentionAction.UPDATE,
            {
                "alias": "xavi",
                "site_url": "https://xavier.arnaus.net/blog",
                "feed_url": "https://xavier.arnaus.net/blog.rss",
                "name": "Xavi's blog"
            },
            None,  # No error
            True,  # return for execute()
            True,  # The user has rights to write
            f"@xavi@social.arnaus.net {MentionParser.INFO_UPDATED}",
            "xavi@social.arnaus.net",  # Who is actually mentioning
            {
                "xavi": {
                    "site_url": "https://xavier.arnaus.net/blog",
                    "feed_url": "https://xavier.arnaus.net/blog.rss",
                    "name": "Xavi's blog"
                }
            }
        ),
        # Action UPDATE, the user does not have rights to write
        (
            "@feeder update xavi https://xavier.arnaus.net/blog \"Xavi's blog\"",
            MentionAction.UPDATE,
            {
                "alias": "xavi",
                "site_url": "https://xavier.arnaus.net/blog",
                "feed_url": "https://xavier.arnaus.net/blog.rss",
                "name": "Xavi's blog"
            },
            None,  # No error
            True,  # return for execute()
            False,  # The user does not rights to write
            f"@xavi@social.arnaus.net {MentionParser.ERROR_NOT_ALLOWED}",
            "xavi@social.arnaus.net",  # Who is actually mentioning
            {
                "xavi": {
                    "site_url": "https://xavier.arnaus.net/blog",
                    "feed_url": "https://xavier.arnaus.net/blog.rss",
                    "name": "Xavi's blog"
                }
            }
        ),
        # Action REMOVE, correct and success
        (
            "@feeder remove xavi",
            MentionAction.REMOVE,
            {
                "alias": "xavi"
            },
            None,  # No error
            True,  # return for execute()
            True,  # The user has rights to write
            f"@xavi@social.arnaus.net {MentionParser.INFO_REMOVED}",
            "xavi@social.arnaus.net",  # Who is actually mentioning
            {
                "xavi": {}
            }
        ),
        # Action UPDATE, the user does not have rights to write
        (
            "@feeder remove xavi",
            MentionAction.REMOVE,
            {
                "alias": "xavi"
            },
            None,  # No error
            True,  # return for execute()
            False,  # The user does not rights to write
            f"@xavi@social.arnaus.net {MentionParser.ERROR_NOT_ALLOWED}",
            "xavi@social.arnaus.net",  # Who is actually mentioning
            {
                "xavi": {}
            }
        ),
        # HELLO does not have any stack change
        (
            "@feeder hello",
            MentionAction.HELLO,
            {},
            None,  # No error
            True,  # return for execute()
            True,  # The user has rights to write (does not matter here)
            f"@xavi@social.arnaus.net {MentionParser.INFO_HELLO}",
            "xavi@social.arnaus.net",  # Who is actually mentioning
            {
                "xavi": {}
            }
        ),
        # LIST does not have any stack change. Check the code for the setting.
        (
            "@feeder list",
            MentionAction.LIST,
            {},
            None,  # No error
            True,  # return for execute()
            True,  # The user has rights to write (does not matter here)
            f"@xavi@social.arnaus.net {MentionParser.INFO_LIST_HEADER}" +
            "[xavi] Old Blog: https://old.url " + "(https://old.url/blog.rss)",
            "xavi@social.arnaus.net",  # Who is actually mentioning
            {
                "xavi": {}
            }
        ),
        # Error for invalid action. Will complain and show also the HELLO
        (
            "@feeder unknown",
            None,
            {},
            MentionParser.ERROR_INVALID_ACTION,  # Invalid action
            True,  # return for execute()
            True,  # The user has rights to write (does not matter here)
            f"@xavi@social.arnaus.net {MentionParser.ERROR_INVALID_ACTION}" +
            f"\n\n{MentionParser.INFO_HELLO}",
            "xavi@social.arnaus.net",  # Who is actually mentioning
            {
                "xavi": {}
            }
        ),
        # Error for anything else. Will complain only
        (
            "@feeder unknown",
            None,
            {},
            MentionParser.ERROR_INVALID_RSS,  # Just any error for the test
            True,  # return for execute()
            True,  # The user has rights to write (does not matter here)
            f"@xavi@social.arnaus.net {MentionParser.ERROR_INVALID_RSS}",
            "xavi@social.arnaus.net",  # Who is actually mentioning
            {
                "xavi": {}
            }
        ),
    ],
)
def test_execute(
    content: str,
    action: str,
    complements: dict,
    error: str,
    returned: bool,
    user_can_write: bool,
    status: str,
    username: str,
    entry: dict
):
    old_entry = {
        "site_url": "https://old.url",
        "feed_url": "https://old.url/blog.rss",
        "name": "Old Blog"
    }

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
    instance.action = action
    instance.complements = complements
    instance.error = error

    # For some actions, we should have something already in the stack
    if action in [MentionAction.UPDATE, MentionAction.REMOVE, MentionAction.LIST]:
        old_key = list(entry.keys())[0]
        instance._feeds_storage.set(param_name=old_key, value=old_entry)
        assert instance._feeds_storage.key_exists(old_key)
        old_stuff = instance._feeds_storage.get(param_name=old_key)
        assert old_stuff["site_url"] == "https://old.url"
        assert old_stuff["feed_url"] == "https://old.url/blog.rss"
        assert old_stuff["name"] == "Old Blog"

    # Mock the external calls and trigger the parse
    mocked_storage_write_file = Mock()
    mocked_listener_user_can_write = Mock()
    mocked_listener_user_can_write.return_value = user_can_write
    with patch.object(Storage, "write_file", new=mocked_storage_write_file):
        with patch.object(instance, "user_can_write", new=mocked_listener_user_can_write):
            parsed_result = instance.execute()

    # Assert that the parse outcomed what we expect
    assert instance.answer.status == status
    assert parsed_result == returned
    assert instance.answer.visibility == StatusPostVisibility.PUBLIC
    assert instance.answer.in_reply_to_id == 1234

    # Now assert that the data is correctly applied into the stack
    key = list(entry.keys())[0]
    if user_can_write is True:
        if action == MentionAction.REMOVE:
            assert instance._feeds_storage.key_exists(key) is False
        elif action in [MentionAction.ADD, MentionAction.UPDATE]:
            saved_stuff = instance._feeds_storage.get(param_name=key)
            assert saved_stuff["site_url"] == entry[key]["site_url"]
            assert saved_stuff["feed_url"] == entry[key]["feed_url"]
            assert saved_stuff["name"] == entry[key]["name"]
    else:
        if action == MentionAction.REMOVE:
            assert instance._feeds_storage.key_exists(key) is True
        elif action == MentionAction.ADD:
            assert instance._feeds_storage.key_exists(key) is False
        elif action == MentionAction.UPDATE:
            saved_stuff = instance._feeds_storage.get(param_name=key)
            assert saved_stuff["site_url"] == old_entry["site_url"]
            assert saved_stuff["feed_url"] == old_entry["feed_url"]
            assert saved_stuff["name"] == old_entry["name"]
