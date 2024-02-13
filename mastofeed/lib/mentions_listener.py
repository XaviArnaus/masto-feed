from __future__ import annotations
from mastodon import StreamListener
from pyxavi.config import Config
from pyxavi.logger import Logger
from pyxavi.storage import Storage
from pyxavi.mastodon_helper import StatusPost, StatusPostVisibility
from pyxavi.debugger import dd
from mastofeed.lib.publisher import Publisher
from definitions import ROOT_DIR
from slugify import slugify
from urllib.parse import urlparse
from bs4 import BeautifulSoup as bs4
import requests
import feedparser


class MentionsListener(StreamListener):

    NOTIFICATION_TYPE_MENTION = "mention"

    def load_config(self, config: Config):
        self._config = config
    
    def on_notification(self, notification):
        
        # Discard notifications that are not mentions
        if notification.type != self.NOTIFICATION_TYPE_MENTION:
            return False
        
        # There we go
        mention_parser = MentionParser(config=self._config)

        # Load the mention notification. It will already validate the params
        mention_parser.load_mention(notification=notification)

        # Now we parse the notification to get what do we need to do
        mention_parser.parse()

        # Now we execute the action we parsed
        mention_parser.execute()

        # And finally we answer back
        mention_parser.answer_back()
        

class MentionParser:

    ERROR_INVALID_ACTION = "I don't understand the action."
    ERROR_INVALID_URL = "The given URL does not seem to be valid"
    ERROR_INVALID_RSS = "I could not get a valid RSS feed from the given URL"
    ERROR_INVALID_ALIAS = "The alias can only be letters, numbers and hypens"
    ERROR_ALIAS_ALREADY_EXISTS = "The alias is already taken"
    ERROR_NOT_FOUND_ALIAS = "I can't find that Alias in my records"
    INFO_ADDED = "Added"
    INFO_UPDATED = "Updated"
    INFO_REMOVED = "Removed"
    INFO_HELLO = "I am an RSS Feeder bot. You can use the following commands with me:\n\n" +\
        "add [site-url] [alias] -> Will register a new RSS\n" +\
        "update [alias] [site-url] -> Will change the URL for an alias\n" +\
        "remove [alias] -> Will remove the record\n" +\
        "test [site-url] -> Will test the URL searching for RSSs\n" +\
        "list -> Will show all the records I have"
    INFO_LIST_HEADER = "The registered Feeds are:\n\n"

    DEFAULT_STORAGE_FILE = "storage/feeds.yaml"

    mention: Mention = None
    action: MentionAction = None
    complements: {}
    error: str = None
    answer: StatusPost = None

    def __init__(self, config: Config) -> None:

        self._config = config
        self._logger = Logger(config=config).get_logger()
        self._feeds_storage = Storage(
            self._config.get("feed_parser.storage_file", self.DEFAULT_STORAGE_FILE)
        )
        self._publisher = Publisher(
            config=config,
            base_path=ROOT_DIR
        )

    def load_mention(self, notification) -> None:
        self._logger.debug("Loading mention")
        self.mention = Mention.from_streaming_notification(notification)
    
    def parse(self) -> bool:

        self._logger.debug("Parsing mention")

        if self.mention is None:
            raise RuntimeError("Load the mention successfully before trying to parse it")
        
        # Before doing anything, remove ourself from the mention
        content = self.mention.content.replace(self.mention.username_to, "")

        # ... and trim spaces
        content = content.strip()

        # We work by words, so split the mentionby spaces:
        words = content.split()

        # First word must be the verb/action, from the valid ones
        self.action = MentionAction.valid_or_none(words.pop(0))
        self._logger.debug(f"Got an action: {self.action}")

        # If we don't have a proper action, mark it and stop here
        if self.action == None:
            self.error = self.ERROR_INVALID_ACTION
            return False

        # And then the rest must be any possible complements.
        #   Because the complements needs change per action, this becomes more complex.
        #   The answer of this subcall is the answer of the call
        return self.parse_complements(words=words)
    
    def execute(self) -> bool:

        self._logger.debug("Executing what the mention requests")

        # First of all, do we have any errors?
        if self.error is not None:
            # Let's prepare the answer with the error
            self.answer = StatusPost.from_dict({
                "status": self._format_answer(f"{self.error}\n\n{self.INFO_HELLO}"),
                "in_reply_to_id": self.mention.status_id,
                "visibility": self.mention.visibility
            })
            return True
        
        # So, let's answer according to the action
        match self.action:

            case MentionAction.HELLO:
                self.answer = StatusPost.from_dict({
                    "status": self._format_answer(self.INFO_HELLO),
                    "in_reply_to_id": self.mention.status_id,
                    "visibility": self.mention.visibility
                })
                return True
            
            case MentionAction.ADD:
                self._feeds_storage.set_slugged(self.complements["alias"], {
                    "site_url": self.complements["site_url"],
                    "feed_url": self.complements["feed_url"]
                })
                self._feeds_storage.write_file()
                self.answer = StatusPost.from_dict({
                    "status": self._format_answer(self.INFO_ADDED),
                    "in_reply_to_id": self.mention.status_id,
                    "visibility": self.mention.visibility
                })
                return True
            
            case MentionAction.UPDATE:
                self._feeds_storage.set_slugged(self.complements["alias"], {
                    "site_url": self.complements["site_url"],
                    "feed_url": self.complements["feed_url"]
                })
                self._feeds_storage.write_file()
                self.answer = StatusPost.from_dict({
                    "status": self._format_answer(self.INFO_UPDATED),
                    "in_reply_to_id": self.mention.status_id,
                    "visibility": self.mention.visibility
                })
                return True
            
            case MentionAction.REMOVE:
                self._feeds_storage.delete(self.complements["alias"])
                self._feeds_storage.write_file()
                self.answer = StatusPost.from_dict({
                    "status": self._format_answer(self.INFO_REMOVED),
                    "in_reply_to_id": self.mention.status_id,
                    "visibility": self.mention.visibility
                })
                return True
            
            case MentionAction.LIST:
                aliases = self._feeds_storage.get_all()
                registers = [f"{alias}: {feed['url']}" for alias, feed in aliases.items()]
                self.answer = StatusPost.from_dict({
                    "status": self._format_answer(f"{self.INFO_LIST_HEADER}{registers}"),
                    "in_reply_to_id": self.mention.status_id,
                    "visibility": self.mention.visibility
                })
                return True

            case MentionAction.TEST:
                self.answer = StatusPost.from_dict({
                    "status": self._format_answer(
                        f"The site URL {self.complements['site_url']} appears to have " +\
                        f"a valid feed at {self.complements['feed_url']}"
                    ),
                    "in_reply_to_id": self.mention.status_id,
                    "visibility": self.mention.visibility
                })
                return True


    def answer_back(self) -> bool:

        self._logger.debug("answering to the mention")

        return self._publisher.publish_status_post(status_post=self.answer)


    def _format_answer(self, text: str) -> str:

        return f"{self.mention.username_from} {text}"

    def parse_complements(self, words: list) -> None:

        self._logger.debug("Parsing complements")

        # So let's check the given complements as per every action needs.
        match self.action:

            case MentionAction.HELLO:
                # It does not need complements.
                return True
            
            case MentionAction.ADD:
                # First word needs to be a valid URL
                first_word = words.pop(0)
                if not self.is_url_valid(first_word):
                    self.error = self.ERROR_INVALID_URL
                    return False
                # Second, needs to be a valid RSS
                list_of_possible_rss_urls = self.findfeed(first_word)
                if list_of_possible_rss_urls == 0:
                    self.error = self.ERROR_INVALID_RSS
                # We have something. Let's see, we pick the first occurrence.
                rss_url = list_of_possible_rss_urls[0]
                # There can be an optional second word,
                #   that will be used as an "alias" or "feed name"
                alias = None
                if len(words) > 0:
                    alias = words.pop(0)
                    # The alias has to be valid
                    if not self.is_alias_valid(alias=alias):
                        self.error = self.ERROR_INVALID_ALIAS
                        return False
                    # The alias must not exists already
                    if self._feeds_storage.key_exists(alias):
                        self.error = self.ERROR_ALIAS_ALREADY_EXISTS
                        return False
                # And finally, set all of them as complements
                self.complements = {
                    "alias": alias,
                    "site_url": first_word,
                    "feed_url": rss_url
                }
                return True
            
            case MentionAction.UPDATE:
                # First word needs to be an alias
                first_word = words.pop(0)
                if not self._feeds_storage.key_exists(first_word):
                    self.error = self.ERROR_NOT_FOUND_ALIAS
                    return False
                # Second needs to be a valid URL
                second_word = words.pop(0)
                if not self.is_url_valid(second_word):
                    self.error = self.ERROR_INVALID_URL
                    return False
                # ... and contain a RSS
                list_of_possible_rss_urls = self.findfeed(second_word)
                if list_of_possible_rss_urls == 0:
                    self.error = self.ERROR_INVALID_RSS
                rss_url = list_of_possible_rss_urls[0]
                # And finally, set all of them as complements
                self.complements = {
                    "alias": first_word,
                    "site_url": second_word,
                    "feed_url": rss_url
                }
                return True
            
            case MentionAction.REMOVE:
                # First word needs to be an alias
                first_word = words.pop(0)
                if not self._feeds_storage.key_exists(first_word):
                    self.error = self.ERROR_NOT_FOUND_ALIAS
                    return False
                # Set it as complements
                self.complements = {
                    "alias": first_word
                }
                return True
            
            case MentionAction.LIST:
                # It does not need complements.
                return True
            
            case MentionAction.TEST:
                # First word needs to be a valid URL
                first_word = words.pop(0)
                if not self.is_url_valid(first_word):
                    self.error = self.ERROR_INVALID_URL
                    return False
                # Second, needs to be a valid RSS
                list_of_possible_rss_urls = self.findfeed(first_word)
                if list_of_possible_rss_urls == 0:
                    self.error = self.ERROR_INVALID_RSS
                # We have something. Let's see, we pick the first occurrence.
                rss_url = list_of_possible_rss_urls[0]
                # And finally, set all of them as complements
                self.complements = {
                    "site_url": first_word,
                    "feed_url": rss_url
                }
                return True


    def is_url_valid(self, url) -> bool:
        parsed_url = urlparse(url)
        return True if parsed_url.scheme and parsed_url.netloc else False
    
    def is_alias_valid(self, alias) -> bool:
        return alias == slugify(alias)

    def findfeed(self, site):
        """
        It returns a list of URLs found in the given site's URL that have entries.
        so be prepared to receive an array.
        """
        # kindly stolen from
        #   https://alexmiller.phd/posts/python-3-feedfinder-rss-detection-from-url/
        raw = requests.get(site).text
        result = []
        possible_feeds = []
        html = bs4(raw)
        feed_urls = html.findAll("link", rel="alternate")
        if len(feed_urls) > 1:
            for f in feed_urls:
                t = f.get("type",None)
                if t:
                    if "rss" in t or "xml" in t:
                        href = f.get("href",None)
                        if href:
                            possible_feeds.append(href)
        parsed_url = urlparse(site)
        base = parsed_url.scheme+"://"+parsed_url.hostname
        atags = html.findAll("a")
        for a in atags:
            href = a.get("href",None)
            if href:
                if "xml" in href or "rss" in href or "feed" in href:
                    possible_feeds.append(base+href)
        for url in list(set(possible_feeds)):
            f = feedparser.parse(url)
            if len(f.entries) > 0:
                if url not in result:
                    result.append(url)
        return(result)




class MentionAction:

    HELLO = "hello"
    ADD = "add"
    UPDATE = "update"
    REMOVE = "remove"
    LIST = "list"
    TEST = "test"

    def get_valid() -> list:
        return [
            MentionAction.HELLO,
            MentionAction.ADD,
            MentionAction.UPDATE,
            MentionAction.REMOVE,
            MentionAction.LIST,
            MentionAction.TEST
        ]

    def valid_or_raise(value: str) -> str:
        valid_items = MentionAction.get_valid()

        if value not in valid_items:
            raise RuntimeError(f"Value [{value}] is not a valid MentionAction")

        return value

    def valid_or_none(value: str) -> str:
        try:
            return MentionAction.valid_or_raise(value)
        except RuntimeError as e:
            return None


class Mention:

    status_id: int = None
    content: str = None
    username_from: str = None
    username_to: str = None
    visibility: StatusPostVisibility = None

    def __init__(
        self,
        status_id: int = None,
        content: str = None,
        username_from: str = None,
        username_to: str = None,
        visibility: StatusPostVisibility = None
    ) -> None:
        self.status_id = status_id
        self.content = content
        self.username_from = username_from
        self.username_to = username_to
        self.visibility = visibility if visibility is not None\
            else StatusPostVisibility.PUBLIC
    
    def to_dict(self) -> dict:
        return {
            "status_id": self.status_id,
            "content": self.content,
            "username_from": self.username_from,
            "username_to": self.username_to,
            "visibility": self.visibility
        }
    
    def from_dict(mention: dict) -> Mention:
        return Mention(
            mention["status_id"] if "status_id" in mention else None,
            mention["content"] if "content" in mention else None,
            mention["username_from"] if "username_from" in mention else None,
            mention["username_to"] if "username_to" in mention else None,
            StatusPostVisibility.valid_or_raise(mention["visibility"])
            if "visibility" in mention else None,
        )

    def from_streaming_notification(notification) -> Mention:
        return Mention.from_dict({
            "status_id": notification.status.id,
            "content": notification.status.content,
            "username_from": notification.account.acct,
            "username_to": notification.status.acct,
            "visibility": notification.status.visibility
        })