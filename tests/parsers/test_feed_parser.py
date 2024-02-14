from pyxavi.config import Config
from pyxavi.storage import Storage
from mastofeed.lib.queue_post import QueuePost, QueuePostMedia
from mastofeed.parsers.parser_protocol import ParserProtocol
from mastofeed.parsers.feed_parser import FeedParser
import feedparser
from datetime import datetime
from time import localtime
from dateutil import parser
from unittest.mock import patch, Mock
from unittest import TestCase
import pytest
from logging import Logger as BuiltInLogger
import copy
from string import Template

CONFIG = {
    "logger": {
        "name": "custom_logger"
    },
    "feed_parser": {
        "storage_file": "feeds.yaml",
        # "sites": [
        #     {
        #         "name": "News",
        #         "url": "https://www.example.cat/rss/my_feed",
        #         "language_default": "ca_ES",
        #         "keywords_filter_profile": "talamanca",
        #         "show_name": True
        #     }
        # ]
    }
}

# This is to emulate the temporary function load_sources()
#   As it is quickly adapted to allocate the listener functionality.
# The problem is that the values then are hardcoded in the class,
#   and for all sources, so testing here language, keywords and show_name
#   stay emulated for the next iteration, where I expect to anyhow bring back
#   the functionality.
SOURCES = {
    "news": {
        "name": "News",
        "url": "https://www.example.cat/rss/my_feed",
        "language_default": "en",  # "language_default": "ca_ES",
        "language_overwrite": False,
        "keywords_filter_profile": "talamanca",
        "show_name": False,
        "max_summary_length": 4500
    }
}

# This keeps the state of already seen
FEEDS = {
    "news": {
        "name": "News",
        "site_url": "https://www.example.cat/",
        "feed_url": "https://www.example.cat/rss/my_feed",
    }
}


@pytest.fixture(autouse=True)
def setup_function():

    global CONFIG, FEEDS, SOURCES

    backup_config = copy.deepcopy(CONFIG)
    backup_feeds = copy.deepcopy(FEEDS)
    backup_sources = copy.deepcopy(SOURCES)

    yield

    FEEDS = backup_feeds
    CONFIG = backup_config
    SOURCES = backup_sources


def patch_storage_read_file(self):
    self._content = FEEDS


@patch.object(Storage, "read_file", new=patch_storage_read_file)
def get_instance() -> FeedParser:
    config = Config(params=CONFIG)

    return FeedParser(config=config)


def test_instantiation():

    instance = get_instance()

    assert isinstance(instance, FeedParser)
    assert isinstance(instance, ParserProtocol)
    assert isinstance(instance._config, Config)
    assert isinstance(instance._logger, BuiltInLogger)
    assert isinstance(instance._feeds_storage, Storage)
    for source, params in instance._sources.items():
        for key, value in params.items():
            assert params[key] == SOURCES[source][key]


def test_get_sources():
    instance = get_instance()

    for source, params in instance.get_sources().items():
        for key, value in params.items():
            assert params[key] == SOURCES[source][key]


def test_get_raw_content_for_source_no_entries_incoming():
    source = list(SOURCES.keys())[0]

    instance = get_instance()

    mocked_feedparser_parse = Mock()
    mocked_feedparser_parse.return_value = {"entries": []}
    with patch.object(feedparser, "parse", new=mocked_feedparser_parse):
        raw_content = instance.get_raw_content_for_source(source)

    mocked_feedparser_parse.assert_called_once_with(SOURCES["news"]["url"])
    assert raw_content == []


def test_get_raw_content_for_source_bad_source():
    source = "wrong"

    instance = get_instance()

    with TestCase.assertRaises(FeedParser, RuntimeError):
        _ = instance.get_raw_content_for_source(source)


@pytest.fixture
def entry_1():
    # summary, language and published_parsed
    return {
        "title": "I am a title 1",
        "summary": "I am a summary 1",
        "link": "http://domain.com/path/page_1.html",
        # "published_parsed": localtime(datetime(2023, 11, 24, 14, 00, 00).timestamp())
        "published_parsed": datetime(2023, 11, 24, 14, 00, 00)
    }


@pytest.fixture
def entry_2():
    # summary, published and no language
    return {
        "title": "I am a title 2",
        "summary": "I am a summary 2 <img src=\"http://domain.com/img/dos.png\" />",
        "link": "http://domain.com/path/page_2.html",
        "published": "Thu, 09 Nov 2023 07:00:00 +0100"
    }


@pytest.fixture
def entry_3():
    # summary, no date nor language
    # should discard
    return {
        "title": "I am a title 3",
        "summary": "I am a summary 3 <img src=\"http://domain.com/img/tres.png\" />",
        "link": "http://domain.com/path/page_3.html"
    }


@pytest.fixture
def entry_4():
    # description, published_parsed and no language
    return {
        "title": "I am a title 4",
        "description": "I am a summary 4 <img src=\"http://domain.com/img/quatre.png\" />",
        "link": "http://domain.com/path/page_4.html",
        # "published_parsed": localtime(datetime(2023, 11, 24, 14, 15, 00).timestamp())
        "published_parsed": datetime(2023, 11, 24, 14, 15, 00)
    }


@pytest.fixture
def entry_5():
    # no summary nor description, published_parsed and no language
    # Should discard
    return {
        "title": "I am a title 5",
        "link": "http://domain.com/path/page_5.html",
        # "published_parsed": localtime(datetime(2023, 11, 24, 14, 25, 00).timestamp())
        "published_parsed": datetime(2023, 11, 24, 14, 25, 00)
    }


def __prepare_published_parsed_for_entries(entries: list) -> list:
    result = []
    for entry in entries:
        # Remember, Python assigns by reference by default
        new_entry = copy.deepcopy(entry)
        if "published_parsed" in new_entry:
            new_entry["published_parsed"] = localtime(new_entry["published_parsed"].timestamp())
        result.append(new_entry)
    return result


def __prepare_expected_entries_for_entries(
    entries: list, indexes: list, expected_language: str
) -> dict:

    expected_entry = {}
    for index in indexes:
        # Calculate the index
        idx = int(index) - 1

        # Prepare the content to expect according to what we have in the incoming entries
        summary = entries[idx]["summary"] if "summary" in entries[idx] else entries[idx][
            "description"]
        published_at = entries[idx]["published_parsed"]\
            if "published_parsed" in entries[idx] else\
            parser.parse(entries[idx]["published"])

        # Build the expected item
        expected_entry[index] = QueuePost(
            id=entries[idx]["link"].replace("http:", ""),
            raw_content={
                "url": entries[idx]["link"],
                "title": entries[idx]["title"],
                "body": summary,
            },
            raw_combined_content=f"{entries[idx]['title']} {summary}",
            published_at=published_at,
            language=expected_language
        )

    return expected_entry


def test_get_raw_content_for_source_with_language_overwrite(
    entry_1, entry_2, entry_3, entry_4, entry_5
):
    source = list(SOURCES.keys())[0]
    SOURCES["news"]["language_overwrite"] = True
    SOURCES["news"]["language_default"] = "es"
    # Let's put them all together in a list. It will be useful for further preps
    entries = [entry_1, entry_2, entry_3, entry_4, entry_5]

    # Now let's prepare the struct_date meant to be returned by feedparser.parse
    #   We do it like this so we can reuse the datetime set up in each entry
    parsed_feed = {
        "entries": __prepare_published_parsed_for_entries(entries),
        "feed": {
            "language": "es"
        },
    }

    # Now we prepare the returned elements
    indexes = ["1", "2", "4"]
    expected_entry = __prepare_expected_entries_for_entries(
        entries, indexes, SOURCES["news"]["language_default"]
    )
    expected_result = [expected_entry["1"], expected_entry["2"], expected_entry["4"]]

    instance = get_instance()

    mocked_feedparser_parse = Mock()
    mocked_feedparser_parse.return_value = parsed_feed
    with patch.object(feedparser, "parse", new=mocked_feedparser_parse):
        raw_content = instance.get_raw_content_for_source(source)

    raw_content_titles = [x.raw_content["title"] for x in raw_content]
    expected_titles = [x.raw_content["title"] for x in expected_result]

    mocked_feedparser_parse.assert_called_once_with(SOURCES["news"]["url"])
    assert raw_content_titles == expected_titles

    for idx in range(0, len(indexes)):
        assert isinstance(raw_content[idx], QueuePost)
        assert raw_content[idx].id == expected_entry[indexes[idx]].id
        assert raw_content[idx].raw_content == expected_entry[indexes[idx]].raw_content
        assert raw_content[idx].raw_combined_content == expected_entry[indexes[idx]
                                                                       ].raw_combined_content
        assert raw_content[idx].published_at == expected_entry[indexes[idx]].published_at
        assert raw_content[idx].language == expected_entry[indexes[idx]].language


def test_get_raw_content_for_source_without_language_overwrite(
    entry_1, entry_2, entry_3, entry_4, entry_5
):
    source = list(SOURCES.keys())[0]
    # Let's put them all together in a list. It will be useful for further preps
    entries = [entry_1, entry_2, entry_3, entry_4, entry_5]

    # Now let's prepare the struct_date meant to be returned by feedparser.parse
    #   We do it like this so we can reuse the datetime set up in each entry
    parsed_feed = {
        "entries": __prepare_published_parsed_for_entries(entries),
        "feed": {
            "language": "es"
        },
    }

    # Now we prepare the returned elements
    indexes = ["1", "2", "4"]
    expected_entry = __prepare_expected_entries_for_entries(
        entries, indexes, parsed_feed["feed"]["language"]
    )
    expected_result = [expected_entry["1"], expected_entry["2"], expected_entry["4"]]

    instance = get_instance()

    mocked_feedparser_parse = Mock()
    mocked_feedparser_parse.return_value = parsed_feed
    with patch.object(feedparser, "parse", new=mocked_feedparser_parse):
        raw_content = instance.get_raw_content_for_source(source)

    raw_content_titles = [x.raw_content["title"] for x in raw_content]
    expected_titles = [x.raw_content["title"] for x in expected_result]

    mocked_feedparser_parse.assert_called_once_with(SOURCES["news"]["url"])
    assert raw_content_titles == expected_titles

    for idx in range(0, len(indexes)):
        assert isinstance(raw_content[idx], QueuePost)
        assert raw_content[idx].id == expected_entry[indexes[idx]].id
        assert raw_content[idx].raw_content == expected_entry[indexes[idx]].raw_content
        assert raw_content[idx].raw_combined_content == expected_entry[indexes[idx]
                                                                       ].raw_combined_content
        assert raw_content[idx].published_at == expected_entry[indexes[idx]].published_at
        assert raw_content[idx].language == expected_entry[indexes[idx]].language


def test_get_raw_content_for_source_without_language_overwrite_nor_default_nor_in_feed(
    entry_1, entry_2, entry_3, entry_4, entry_5
):
    # Remove the language default
    del (SOURCES["news"]["language_default"])

    source = list(SOURCES.keys())[0]
    # Let's put them all together in a list. It will be useful for further preps
    entries = [entry_1, entry_2, entry_3, entry_4, entry_5]

    # Now let's prepare the struct_date meant to be returned by feedparser.parse
    #   We do it like this so we can reuse the datetime set up in each entry
    parsed_feed = {"entries": __prepare_published_parsed_for_entries(entries)}

    # Now we prepare the returned elements
    indexes = ["1", "2", "4"]
    expected_entry = __prepare_expected_entries_for_entries(entries, indexes, "en")
    expected_result = [expected_entry["1"], expected_entry["2"], expected_entry["4"]]

    instance = get_instance()

    mocked_feedparser_parse = Mock()
    mocked_feedparser_parse.return_value = parsed_feed
    with patch.object(feedparser, "parse", new=mocked_feedparser_parse):
        raw_content = instance.get_raw_content_for_source(source)

    raw_content_titles = [x.raw_content["title"] for x in raw_content]
    expected_titles = [x.raw_content["title"] for x in expected_result]

    mocked_feedparser_parse.assert_called_once_with(SOURCES["news"]["url"])
    assert raw_content_titles == expected_titles

    for idx in range(0, len(indexes)):
        assert isinstance(raw_content[idx], QueuePost)
        assert raw_content[idx].id == expected_entry[indexes[idx]].id
        assert raw_content[idx].raw_content == expected_entry[indexes[idx]].raw_content
        assert raw_content[idx].raw_combined_content == expected_entry[indexes[idx]
                                                                       ].raw_combined_content
        assert raw_content[idx].published_at == expected_entry[indexes[idx]].published_at
        assert raw_content[idx].language == expected_entry[indexes[idx]].language


def test_get_raw_content_for_source_without_language_overwrite_nor_language_in_feed(
    entry_1, entry_2, entry_3, entry_4, entry_5
):

    source = list(SOURCES.keys())[0]
    # Let's put them all together in a list. It will be useful for further preps
    entries = [entry_1, entry_2, entry_3, entry_4, entry_5]

    # Now let's prepare the struct_date meant to be returned by feedparser.parse
    #   We do it like this so we can reuse the datetime set up in each entry
    parsed_feed = {"entries": __prepare_published_parsed_for_entries(entries)}

    # Now we prepare the returned elements
    indexes = ["1", "2", "4"]
    expected_entry = __prepare_expected_entries_for_entries(
        entries, indexes, SOURCES["news"]["language_default"]
    )
    expected_result = [expected_entry["1"], expected_entry["2"], expected_entry["4"]]

    instance = get_instance()

    mocked_feedparser_parse = Mock()
    mocked_feedparser_parse.return_value = parsed_feed
    with patch.object(feedparser, "parse", new=mocked_feedparser_parse):
        raw_content = instance.get_raw_content_for_source(source)

    raw_content_titles = [x.raw_content["title"] for x in raw_content]
    expected_titles = [x.raw_content["title"] for x in expected_result]

    mocked_feedparser_parse.assert_called_once_with(SOURCES["news"]["url"])
    assert raw_content_titles == expected_titles

    for idx in range(0, len(indexes)):
        assert isinstance(raw_content[idx], QueuePost)
        assert raw_content[idx].id == expected_entry[indexes[idx]].id
        assert raw_content[idx].raw_content == expected_entry[indexes[idx]].raw_content
        assert raw_content[idx].raw_combined_content == expected_entry[indexes[idx]
                                                                       ].raw_combined_content
        assert raw_content[idx].published_at == expected_entry[indexes[idx]].published_at
        assert raw_content[idx].language == expected_entry[indexes[idx]].language


def test_is_id_already_seen_for_source_no_stack():

    source = list(SOURCES.keys())[0]

    instance = get_instance()

    assert instance.is_id_already_seen_for_source(source, 123) is False


def test_is_id_already_seen_for_source_match():
    global FEEDS

    source = list(SOURCES.keys())[0]
    id = "//domain.com/blog_entry_1.html"

    FEEDS["news"]["urls_seen"] = [id]

    instance = get_instance()

    assert instance.is_id_already_seen_for_source(source, id) is True


def test_is_id_already_seen_for_source_not_match():
    source = list(SOURCES.keys())[0]
    id = "//domain.com/blog_entry_1.html"

    instance = get_instance()
    instance._feeds_storage.set(
        param_name="news.urls_seen", value=["//domain.com/blog_entry_2.html"]
    )

    assert instance.is_id_already_seen_for_source(source, id) is False


def test_set_ids_as_seen_for_source_from_scratch():
    source = list(SOURCES.keys())[0]
    id1 = "//domain.com/blog_entry_1.html"
    id2 = "//domain.com/blog_entry_2.html"
    id3 = "//domain.com/blog_entry_3.html"
    id4 = "//domain.com/blog_entry_4.html"

    instance = get_instance()

    assert instance.is_id_already_seen_for_source(source, id1) is False
    assert instance.is_id_already_seen_for_source(source, id2) is False
    assert instance.is_id_already_seen_for_source(source, id3) is False
    assert instance.is_id_already_seen_for_source(source, id4) is False

    mocked_storage_write_file = Mock()
    with patch.object(Storage, "write_file", new=mocked_storage_write_file):
        instance.set_ids_as_seen_for_source(source, [id1, id2, id3, id4])

    mocked_storage_write_file.assert_called_once()

    assert instance.is_id_already_seen_for_source(source, id1) is True
    assert instance.is_id_already_seen_for_source(source, id2) is True
    assert instance.is_id_already_seen_for_source(source, id3) is True
    assert instance.is_id_already_seen_for_source(source, id4) is True


def test_set_ids_as_seen_for_source_adding_some():
    global FEEDS

    source = list(SOURCES.keys())[0]
    id1 = "//domain.com/blog_entry_1.html"
    id2 = "//domain.com/blog_entry_2.html"
    id3 = "//domain.com/blog_entry_3.html"
    id4 = "//domain.com/blog_entry_4.html"
    FEEDS["news"]["urls_seen"] = [id1, id2]

    instance = get_instance()

    assert instance.is_id_already_seen_for_source(source, id1) is True
    assert instance.is_id_already_seen_for_source(source, id2) is True
    assert instance.is_id_already_seen_for_source(source, id3) is False
    assert instance.is_id_already_seen_for_source(source, id4) is False

    mocked_storage_write_file = Mock()
    with patch.object(Storage, "write_file", new=mocked_storage_write_file):
        instance.set_ids_as_seen_for_source(source, [id3, id4])

    mocked_storage_write_file.assert_called_once()

    assert instance.is_id_already_seen_for_source(source, id1) is True
    assert instance.is_id_already_seen_for_source(source, id2) is True
    assert instance.is_id_already_seen_for_source(source, id3) is True
    assert instance.is_id_already_seen_for_source(source, id4) is True


def test_post_process_for_source_do_nothing():

    posts = [QueuePost()]

    instance = get_instance()

    assert instance.post_process_for_source("source", posts) == posts


def test_parse_media_has_no_media():
    post = QueuePost(raw_combined_content="bla")

    instance = get_instance()

    assert post.media is None
    assert instance.parse_media(post) is None
    assert post.media == []


def test_parse_media_has_one_media():
    summary = "I am a summary 2 <img src=\"http://domain.com/img/dos.png\"" +\
        " alt=\"alternative text\" />"
    post = QueuePost(raw_combined_content=summary)

    instance = get_instance()

    assert post.media is None

    instance.parse_media(post)

    assert len(post.media) == 1
    assert isinstance(post.media[0], QueuePostMedia)
    assert post.media[0].url == "http://domain.com/img/dos.png"
    assert post.media[0].alt_text == "alternative text"


def test_parse_media_has_two_media():
    summary = "I am a summary 2 <img src=\"http://domain.com/img/dos.png\"" +\
        " alt=\"alternative text\" /><img src=\"http://domain.com/img/tres.png\" />"
    post = QueuePost(raw_combined_content=summary)

    instance = get_instance()

    assert post.media is None

    instance.parse_media(post)

    assert len(post.media) == 2
    assert isinstance(post.media[0], QueuePostMedia)
    assert isinstance(post.media[1], QueuePostMedia)
    assert post.media[0].url == "http://domain.com/img/dos.png"
    assert post.media[0].alt_text == "alternative text"
    assert post.media[1].url == "http://domain.com/img/tres.png"
    assert post.media[1].alt_text is None


@pytest.mark.parametrize(
    argnames=('body', 'expected_body'),
    argvalues=[
        ("I am the  body  ", "I am the body"),
        ("I am the <strong>body</strong>", "I am the body"),
        ("I am the <a href=\"http://domain.com/\">body</a>", "I am the body"),
        ("<p>I am the <br />body</p>", "I am the body"),
        ("I am the\n\n\nbody", "I am the body"),
    ],
)
def test_format_post_for_source_clean_body(body, expected_body):
    title = "I am a title"
    link = "http://domain.com/blog_post_1.html"
    source = list(SOURCES.keys())[0]
    post = QueuePost(raw_content={"title": title, "body": body, "url": link})
    SOURCES["news"] = {"name": source}

    instance = get_instance()

    expected_title = title
    expected_body = Template(instance.TEMPLATE_SUMMARY_CONTENT).substitute(
        body=expected_body, link=link
    )

    instance.format_post_for_source(source, post)

    assert post.summary == expected_title
    assert post.text == expected_body


def test_format_post_for_source_show_name():
    title = "I am a title"
    body = "I am the body"
    link = "http://domain.com/blog_post_1.html"
    source = list(SOURCES.keys())[0]
    post = QueuePost(raw_content={"title": title, "body": body, "url": link})
    SOURCES["news"]["show_name"] = True

    instance = get_instance()
    # This is needed now while we have the _load_sources emulating method
    instance._sources["news"]["show_name"] = True

    expected_title = Template(instance.TEMPLATE_TITLE_WITH_ORIGIN).substitute(
        title=title, origin=SOURCES["news"]["name"]
    )
    expected_body = Template(instance.TEMPLATE_SUMMARY_CONTENT).substitute(body=body, link=link)

    instance.format_post_for_source(source, post)

    assert post.summary == expected_title
    assert post.text == expected_body


def test_format_post_for_source_show_name_max_length_above():
    title = "I am a title"
    body = "I am the body"
    link = "http://domain.com/blog_post_1.html"
    source = list(SOURCES.keys())[0]
    post = QueuePost(raw_content={"title": title, "body": body, "url": link})
    SOURCES["news"]["show_name"] = True
    SOURCES["news"]["max_summary_length"] = 500

    instance = get_instance()
    # This is needed now while we have the _load_sources emulating method
    instance._sources["news"]["show_name"] = True

    expected_title = Template(instance.TEMPLATE_TITLE_WITH_ORIGIN).substitute(
        title=title, origin=SOURCES["news"]["name"]
    )
    expected_body = Template(instance.TEMPLATE_SUMMARY_CONTENT).substitute(body=body, link=link)

    instance.format_post_for_source(source, post)

    assert post.summary == expected_title
    assert post.text == expected_body


def test_format_post_for_source_show_name_max_length_cut_by_source():
    title = "I am a title"
    body = "I am the body"
    link = "http://domain.com/blog_post_1.html"
    source = list(SOURCES.keys())[0]
    post = QueuePost(raw_content={"title": title, "body": body, "url": link})
    # This is unused now while we have the _load_sources emulating method
    # SOURCES["news"]["show_name"] = True
    # SOURCES["news"]["max_summary_length"] = 45

    instance = get_instance()
    # This is needed now while we have the _load_sources emulating method
    instance._sources["news"]["show_name"] = True
    instance._sources["news"]["max_summary_length"] = 45

    expected_title = Template(instance.TEMPLATE_TITLE_WITH_ORIGIN).substitute(
        title=title, origin=SOURCES["news"]["name"]
    )
    expected_body = Template(instance.TEMPLATE_SUMMARY_CONTENT).substitute(
        body="I am t...", link=link
    )

    instance.format_post_for_source(source, post)

    assert post.summary == expected_title
    assert post.text == expected_body
    assert len(post.text) == 45


def test_format_post_for_source_show_name_max_length_cut_by_param():
    title = "I am a title"
    body = "I am the body"
    link = "http://domain.com/blog_post_1.html"
    source = list(SOURCES.keys())[0]
    post = QueuePost(raw_content={"title": title, "body": body, "url": link})
    SOURCES["news"]["show_name"] = True
    CONFIG["default"] = {"max_length": 45}

    instance = get_instance()
    # This is needed now while we have the _load_sources emulating method
    instance._sources["news"]["show_name"] = True
    del (instance._sources["news"]["max_summary_length"])

    expected_title = Template(instance.TEMPLATE_TITLE_WITH_ORIGIN).substitute(
        title=title, origin=SOURCES["news"]["name"]
    )
    expected_body = Template(instance.TEMPLATE_SUMMARY_CONTENT).substitute(
        body="I am t...", link=link
    )

    instance.format_post_for_source(source, post)

    assert post.summary == expected_title
    assert post.text == expected_body
    assert len(post.text) == 45


def test_format_post_for_source_show_name_max_length_cut_by_default():
    title = "I am a title"
    body = "I am the body"
    link = "http://domain.com/blog_post_1.html"
    source = list(SOURCES.keys())[0]
    post = QueuePost(raw_content={"title": title, "body": body, "url": link})
    SOURCES["news"]["show_name"] = True

    instance = get_instance()
    # This is needed now while we have the _load_sources emulating method
    instance._sources["news"]["show_name"] = True
    del (instance._sources["news"]["max_summary_length"])

    instance.MAX_SUMMARY_LENGTH = 45

    expected_title = Template(instance.TEMPLATE_TITLE_WITH_ORIGIN).substitute(
        title=title, origin=SOURCES["news"]["name"]
    )
    expected_body = Template(instance.TEMPLATE_SUMMARY_CONTENT).substitute(
        body="I am t...", link=link
    )

    instance.format_post_for_source(source, post)

    assert post.summary == expected_title
    assert post.text == expected_body
    assert len(post.text) == 45


def test_format_post_for_source_no_show_name_missing_param():
    title = "I am a title"
    body = "I am the body"
    link = "http://domain.com/blog_post_1.html"
    source = list(SOURCES.keys())[0]
    post = QueuePost(raw_content={"title": title, "body": body, "url": link})
    SOURCES["news"] = {"name": source}

    instance = get_instance()

    expected_title = title
    expected_body = Template(instance.TEMPLATE_SUMMARY_CONTENT).substitute(body=body, link=link)

    instance.format_post_for_source(source, post)

    assert post.summary == expected_title
    assert post.text == expected_body


def test_format_post_for_source_no_show_name():
    title = "I am a title"
    body = "I am the body"
    link = "http://domain.com/blog_post_1.html"
    source = list(SOURCES.keys())[0]
    post = QueuePost(raw_content={"title": title, "body": body, "url": link})
    SOURCES["news"] = {"name": source, "show_name": False}

    instance = get_instance()

    expected_title = title
    expected_body = Template(instance.TEMPLATE_SUMMARY_CONTENT).substitute(body=body, link=link)

    instance.format_post_for_source(source, post)

    assert post.summary == expected_title
    assert post.text == expected_body


def test_format_post_for_source_merge_content():
    title = "I am a title"
    body = "I am the body"
    link = "http://domain.com/blog_post_1.html"
    source = list(SOURCES.keys())[0]
    post = QueuePost(raw_content={"title": title, "body": body, "url": link})
    SOURCES["news"] = {"name": source, "show_name": False}
    CONFIG["default"] = {"merge_content": True}

    instance = get_instance()

    expected_title = None
    expected_body = Template(instance.TEMPLATE_SUMMARY_CONTENT).substitute(body=body, link=link)
    expected_body = Template(instance.TEMPLATE_MERGED_CONTENT).substitute(
        body=expected_body, title=title
    )

    instance.format_post_for_source(source, post)

    assert post.summary == expected_title
    assert post.text == expected_body
