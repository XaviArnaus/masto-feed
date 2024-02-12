from pyxavi.config import Config
from pyxavi.storage import Storage
from pyxavi.media import Media
from pyxavi.url import Url
from mastofeed.parsers.parser_protocol import ParserProtocol
from mastofeed.lib.queue_post import QueuePost, QueuePostMedia
from datetime import datetime
from dateutil import parser
from bs4 import BeautifulSoup
from time import mktime
from string import Template
import feedparser
import logging
import re


class FeedParser(ParserProtocol):
    '''
    Parses the posts from the registered RSS feeds
    and write in a queue list the content and other valuable data of the posts to toot

    '''
    MAX_SUMMARY_LENGTH = 300
    DEFAULT_LANGUAGE = "en"
    DEFAULT_STORAGE_FILE = "storage/feeds.yaml"
    # DEFAULT_QUEUE_FILE = "storage/queue.yaml"

    # This template only adds origin into the title
    TEMPLATE_TITLE_WITH_ORIGIN = "$origin\t$title"
    # At this point title comes with origin if it should
    TEMPLATE_MERGED_CONTENT = "$title\n\n$body"
    # Whatever we have in body, we add the link to it
    TEMPLATE_SUMMARY_CONTENT = "$body\n\n$link"

    def __init__(self, config: Config) -> None:
        self._config = config
        self._logger = logging.getLogger(config.get("logger.name"))
        self._feeds_storage = Storage(
            self._config.get("feed_parser.storage_file", self.DEFAULT_STORAGE_FILE)
        )
        self._sources = {x["name"]: x for x in self._config.get("feed_parser.sites", [])}
        self._already_seen = {}  # type: dict[str, list]

    def format_post_for_source(self, source: str, post: QueuePost) -> None:

        # Cleaning title
        title = ""
        if "title" in post.raw_content:
            title_only_chars = re.sub("^[A-Za-z]*", "", post.raw_content["title"])
            if title_only_chars == title_only_chars.upper():
                title = " ".join(
                    [
                        word.capitalize()
                        for word in post.raw_content["title"].lower().split(" ")
                    ]
                )
            else:
                title = post.raw_content["title"]

        # Cleaning body
        body = ""
        if "body" in post.raw_content and post.raw_content["body"] != "":
            body = post.raw_content["body"] + "\n\n"
            body = ''.join(BeautifulSoup(body, "html.parser").findAll(string=True))
            body = body.replace("\n\n\n", "\n\n")
            body = re.sub(r'\s+', ' ', body)
            body = body.strip(" ")

        # Do we need to add the source name into the title?
        if "show_name" in self._sources[source] and self._sources[source]["show_name"]:
            title = Template(self.TEMPLATE_TITLE_WITH_ORIGIN).substitute(
                origin=source, title=title
            )

        # Do we need to merge all fields into the body
        #   or we want to have the title separated?
        if self._config.get("default.merge_content", False):
            body = Template(self.TEMPLATE_MERGED_CONTENT).substitute(title=title, body=body)
            title = None

        # Cutting the body as per max length
        max_length = self._config.get("default.max_length", self.MAX_SUMMARY_LENGTH)
        if "max_summary_length" in self._sources[source] and\
           self._sources[source]["max_summary_length"]:
            max_length = self._sources[source]["max_summary_length"]
        # The max_length is only the space we have for the mastodon status.
        #   The template has a link added...
        #   we have to calculate how much the link will occupy, plus the \n
        url_len = len(post.raw_content["url"]) + len("\n\n")
        post_len = len(body)
        if post_len + url_len > max_length:
            overall_cut_length = max_length - url_len - 3
            body = (body[:overall_cut_length] + '...')

        # Finally applying everything into the last template
        post.summary = title
        post.text = Template(self.TEMPLATE_SUMMARY_CONTENT).substitute(
            body=body, link=post.raw_content["url"]
        )

    def get_sources(self) -> dict:
        return self._sources

    def __datetime_from_struct_date(self, struct_time: tuple) -> datetime:

        # struct_time has a tuple-style:
        # ->  Thu, 09 Nov 2023 07:00:00 +0100
        # "published_parsed": (struct_time[9])[
        #   (int)2023, (int)11, (int)9, (int)6, (int)0, (int)0, (int)3, (int)313, (int)0
        # ]
        return datetime.fromtimestamp(mktime(struct_time))

    def __choose_language_for_source(self, source: str, parsed_content: dict) -> str:
        default_language = self._sources[source]["language_default"]\
            if "language_default" in self._sources[source] else None

        shall_override_with_default_language = self._sources[source]["language_override"]\
            if "language_override" in self._sources[source] else False

        # Priority order:
        #   overriding language > content language > source parameters language > class language
        #   But we always want to have a language
        language = self.DEFAULT_LANGUAGE

        # If we have a default language defined in the parameters of the source
        if default_language is not None:
            language = default_language

        # If the parameters say that we need to override the language,
        #   no matter what it comes, we do
        if shall_override_with_default_language and default_language is not None:
            return default_language

        # Now, if we actually have a language in the feed, use it.
        #   Again, this is not a language per post, is a language per feed!
        if "feed" in parsed_content and "language" in parsed_content["feed"]:
            language = parsed_content["feed"]["language"]

        return language

    def get_raw_content_for_source(self, source: str) -> list[QueuePost]:

        # Do we have this source defined?
        if source not in self._sources:
            raise RuntimeError(f"Source of data [{source}] not found.")

        # Load the site data
        site = self._sources[source]

        # initialising
        metadata = {}
        list_of_raw_posts = []
        discarded_posts = 0

        self._logger.debug("Parsing site %s", source)
        parsed_site = feedparser.parse(site["url"])

        # This site may not have posts
        if "entries" not in parsed_site or not parsed_site["entries"]:
            self._logger.warning("No entries in this feed, skipping.")
            return list_of_raw_posts

        # Maybe we have a language setting at site level
        metadata["language"] = self.__choose_language_for_source(source, parsed_site)

        for post in parsed_site["entries"]:

            # We try to gather here everything that is needed for a Post
            post_url = Url.clean(post["link"], {"scheme": True})

            # In some cases we don't have a 'summary', but a 'description' field
            summary = post["summary"] if "summary" in post else None
            if summary is None and "description" in post:
                self._logger.debug("Making out a [summary] from a [description]")
                summary = post["description"]
            # If we still don't have a summary, the post is useless
            if summary is None:
                self._logger.debug("Could not fix not present [summary]. Discarding.")
                discarded_posts += 1
                continue

            # We need the published date to be able to calculate how old is it.
            post_date = self.__datetime_from_struct_date(post["published_parsed"])\
                if "published_parsed" in post and post["published_parsed"] else None
            if post_date is None and "published" in post and post["published"]:
                post_date = parser.parse(post["published"])
            # We still don't have a post date
            if post_date is None:
                self._logger.debug("No usable published date. Discarding")
                discarded_posts += 1
                continue

            list_of_raw_posts.append(
                QueuePost(
                    id=post_url,
                    raw_content={
                        "url": post["link"],
                        "title": post["title"],
                        "body": summary,
                    },
                    raw_combined_content=f"{post['title']} {summary}",
                    published_at=post_date,
                    language=metadata["language"]
                    if metadata is not None and "language" in metadata else None
                )
            )

            self._logger.debug(f"Discarded {discarded_posts} invalid posts from {source}")

        return list_of_raw_posts

    def is_id_already_seen_for_source(self, source: str, id: any) -> bool:
        """Identifies if this ID is already registered in the state"""

        if source not in self._already_seen or self._already_seen[source] is None:
            self._logger.debug("Getting possible stored data for %s", source)
            site_data = self._feeds_storage.get_hashed(self._sources[source]["url"], None)
            self._already_seen[source] = site_data["urls_seen"]\
                if site_data and "urls_seen" in site_data else []

        return True if id in self._already_seen[source] else False

    def set_ids_as_seen_for_source(self, source: str, list_of_ids: list) -> None:
        """Performs the saving of the seen state"""

        for new_url in list_of_ids:
            self._already_seen[source].append(new_url)

        self._logger.debug(f"Updating seen URLs for {source}")
        self._feeds_storage.set_hashed(
            self._sources[source]["url"], {"urls_seen": self._already_seen[source]}
        )
        self._feeds_storage.write_file()

    def post_process_for_source(self, source: str, posts: list[QueuePost]) -> list[QueuePost]:
        return posts

    def parse_media(self, post: QueuePost) -> None:
        """
        Parses the media attached to the content, if exists

        If so, will update the referenced post's media field
        Otherwise does nothing.

        This method not necessarily downloads the media. The Publisher
        can do that. It is left to the parser to decide
        """
        # Initiate
        result = []

        # Discover if we have a link to an image
        images = Media().get_image_url_from_text(post.raw_combined_content)

        if images:
            for image_object in images:
                result.append(
                    QueuePostMedia(
                        url=image_object["url"],
                        alt_text=image_object["alt_text"] if image_object["alt_text"] else None
                    )
                )

        # And now set the list into the post field
        #   It should be returned by reference.
        post.media = result
