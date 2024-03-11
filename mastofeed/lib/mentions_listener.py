from __future__ import annotations
from mastodon import StreamListener
from pyxavi.config import Config
from pyxavi.logger import Logger
from pyxavi.storage import Storage
from pyxavi.mastodon_helper import StatusPost, StatusPostVisibility
from pyxavi.url import Url
from mastofeed.lib.publisher import Publisher
from definitions import ROOT_DIR
from slugify import slugify
from bs4 import BeautifulSoup
import re


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
    ERROR_INVALID_URL = "The given URL does not seem to be valid. Don't forget the schema."
    ERROR_INVALID_RSS = "I could not get a valid RSS feed from the given URL. " +\
        "Perhaps it is in a /blog subdirectory?"
    ERROR_INVALID_ALIAS = "The alias can only be letters, numbers and hypens"
    ERROR_ALIAS_ALREADY_EXISTS = "The alias is already taken"
    ERROR_NOT_FOUND_ALIAS = "I can't find that Alias in my records"
    ERROR_NOT_ALLOWED = "You're not allowed to Create, Update or Remove records."
    ERROR_NO_COMMAND = "hi! 👋🏼"
    ERROR_MISSING_PARAMS = "Seems like you forgot parameters"
    INFO_ADDED = "Added"
    INFO_UPDATED = "Updated"
    INFO_REMOVED = "Removed"
    INFO_HELLO = "I am an RSS Feeder bot. You can use the following commands with me:\n\n" +\
        "add [site-url] [alias] \"name of the feed\" -> Will register a new RSS\n" +\
        "update [alias] [site-url] \"name of the feed\" " +\
        "-> Will change the URL for an alias\n" +\
        "remove [alias] -> Will remove the record\n" +\
        "test [site-url] -> Will test the URL searching for RSSs\n" +\
        "list -> Will show all the records I have"
    INFO_LIST_HEADER = "The registered Feeds are:\n\n"

    DEFAULT_STORAGE_FILE = "storage/feeds.yaml"
    REGEXP_TEXT_WITHIN_QUOTES = r'"([\w+_\./\\\'\’\`\s\-]*)"'

    mention: Mention = None
    action: MentionAction = None
    complements: dict = {}
    error: str = None
    answer: StatusPost = None
    me: str = None

    def __init__(self, config: Config) -> None:

        self._config = config
        self._logger = Logger(config=config).get_logger()
        self._feeds_storage = Storage(
            self._config.get("feed_parser.storage_file", self.DEFAULT_STORAGE_FILE)
        )
        self._publisher = Publisher(config=config, base_path=ROOT_DIR)
        self.me = config.get("app.user")
        if self.me is None:
            RuntimeError("Please define app.user in the config")
        self.admin = config.get("app.admin")
        self._restrict_writes = config.get("app.restrict_writes", True)
        if self._restrict_writes and self.admin is None:
            RuntimeError("Please define app.admin in the config to restrict writes")

    def load_mention(self, notification) -> None:
        self._logger.debug("Loading mention")
        self.mention = Mention.from_streaming_notification(notification)

    def parse(self) -> bool:

        self._logger.debug("Parsing mention")

        if self.mention is None:
            raise RuntimeError("Load the mention successfully before trying to parse it")

        # Before anything, remove the HTML stuff
        content = BeautifulSoup(self.mention.content, features="html.parser").get_text()

        # Removing the self username from the mention, so we have a clean string to parse
        username_position, content = self.remove_self_username_from_content(content=content)

        # If the username was NOT in the beginning, we assume that this is an organic mention,
        #   meaning that it does not contain a command. Let's be polite and say Hi!
        if username_position > 0:
            self.error = self.ERROR_NO_COMMAND
            return False

        # ... and trim spaces
        content = content.strip()

        # Before getting the words, get the possible text inside quotes
        #   we'll use it for ADD and UPDATE to assign a Name
        quoted_text = self.get_text_inside_quotes(content)
        if quoted_text is not None:
            content = content.replace(quoted_text, "")
            content = content.replace("\"", "")

        # We work by words, so split the mentionby spaces:
        words = content.split()

        # If the mention was empty, behave polite like an organinc mention.
        if len(words) == 0:
            self.error = self.ERROR_NO_COMMAND
            return False

        # First word must be the verb/action, from the valid ones
        self.action = MentionAction.valid_or_none(words.pop(0))
        self._logger.debug(f"Got an action: {self.action}")

        # If we don't have a proper action, mark it and stop here
        if self.action is None:
            self._logger.debug("No action, then complaining")
            self.error = self.ERROR_INVALID_ACTION
            return False

        # And then the rest must be any possible complements.
        #   Because the complements needs change per action, this becomes more complex.
        #   The answer of this subcall is the answer of the call
        return self.parse_complements(words=words, quoted_text=quoted_text)

    def execute(self) -> bool:

        self._logger.debug("Executing what the mention requests")

        # First of all, do we have any errors?
        if self.error is not None:
            # Let's prepare the answer with the error
            #   We add the HELLO in case of unknown action only
            if self.error == self.ERROR_INVALID_ACTION:
                self._logger.debug("Error: Invalid action")
                text = f"{self.error}\n\n{self.INFO_HELLO}"
            else:
                self._logger.debug(f"Error: General: {self.error}")
                text = self.error
            self.answer = StatusPost.from_dict(
                {
                    "status": self._format_answer(text),
                    "in_reply_to_id": self.mention.status_id,
                    "visibility": self.mention.visibility
                }
            )
            return True

        # So, let's answer according to the action
        elif self.action == MentionAction.HELLO:
            self._logger.debug("Action HELLO")
            self.answer = StatusPost.from_dict(
                {
                    "status": self._format_answer(self.INFO_HELLO),
                    "in_reply_to_id": self.mention.status_id,
                    "visibility": self.mention.visibility
                }
            )
            return True

        elif self.action == MentionAction.ADD:
            self._logger.debug("Action ADD")
            if not self.user_can_write():
                self._logger.debug("not allowed to write write")
                self.answer = StatusPost.from_dict(
                    {
                        "status": self._format_answer(self.ERROR_NOT_ALLOWED),
                        "in_reply_to_id": self.mention.status_id,
                        "visibility": self.mention.visibility
                    }
                )
                return True

            self._feeds_storage.set_slugged(
                self.complements["alias"],
                {
                    "site_url": self.complements["site_url"],
                    "feed_url": self.complements["feed_url"],
                    "name": self.complements["name"]
                }
            )
            self._feeds_storage.write_file()
            self.answer = StatusPost.from_dict(
                {
                    "status": self._format_answer(self.INFO_ADDED),
                    "in_reply_to_id": self.mention.status_id,
                    "visibility": self.mention.visibility
                }
            )
            return True

        elif self.action == MentionAction.UPDATE:
            self._logger.debug("Action UPDATE")
            if not self.user_can_write():
                self._logger.debug("not allowed to write write")
                self.answer = StatusPost.from_dict(
                    {
                        "status": self._format_answer(self.ERROR_NOT_ALLOWED),
                        "in_reply_to_id": self.mention.status_id,
                        "visibility": self.mention.visibility
                    }
                )
                return True

            self._feeds_storage.set_slugged(
                self.complements["alias"],
                {
                    "site_url": self.complements["site_url"],
                    "feed_url": self.complements["feed_url"],
                    "name": self.complements["name"]
                }
            )
            self._feeds_storage.write_file()
            self.answer = StatusPost.from_dict(
                {
                    "status": self._format_answer(self.INFO_UPDATED),
                    "in_reply_to_id": self.mention.status_id,
                    "visibility": self.mention.visibility
                }
            )
            return True

        elif self.action == MentionAction.REMOVE:
            self._logger.debug("Action REMOVE")
            if not self.user_can_write():
                self._logger.debug("not allowed to write write")
                self.answer = StatusPost.from_dict(
                    {
                        "status": self._format_answer(self.ERROR_NOT_ALLOWED),
                        "in_reply_to_id": self.mention.status_id,
                        "visibility": self.mention.visibility
                    }
                )
                return True

            self._feeds_storage.delete(self.complements["alias"])
            self._feeds_storage.write_file()
            self.answer = StatusPost.from_dict(
                {
                    "status": self._format_answer(self.INFO_REMOVED),
                    "in_reply_to_id": self.mention.status_id,
                    "visibility": self.mention.visibility
                }
            )
            return True

        elif self.action == MentionAction.LIST:
            self._logger.debug("Action LIST")
            aliases = self._feeds_storage.get_all()
            if len(aliases) > 0:
                registers = [
                    f"[{alias}] {feed['name']}: {feed['site_url']} ({feed['feed_url']})"
                    for alias,
                    feed in aliases.items()
                ]
            else:
                registers = ["No registers yet"]
            registers = "\n".join(registers)
            self.answer = StatusPost.from_dict(
                {
                    "status": self._format_answer(f"{self.INFO_LIST_HEADER}{registers}"),
                    "in_reply_to_id": self.mention.status_id,
                    "visibility": self.mention.visibility
                }
            )
            return True

        elif self.action == MentionAction.TEST:
            self._logger.debug("Action TEST")
            if self.complements['site_url'] == self.complements['feed_url']:
                text = f"The site URL {self.complements['site_url']} appears to be " +\
                        "a valid feed itself"
            else:
                text = f"The site URL {self.complements['site_url']} appears to have " +\
                        f"a valid feed at {self.complements['feed_url']}"
            self.answer = StatusPost.from_dict(
                {
                    "status": self._format_answer(text),
                    "in_reply_to_id": self.mention.status_id,
                    "visibility": self.mention.visibility
                }
            )
            return True

    def answer_back(self) -> bool:

        self._logger.debug("answering to the mention")

        return self._publisher.publish_status_post(status_post=self.answer)

    def _format_answer(self, text: str) -> str:

        return f"@{self.mention.username} {text}"

    def parse_complements(self, words: list, quoted_text: str = None) -> bool:

        self._logger.debug("Parsing complements")

        # So let's check the given complements as per every action needs.
        if self.action == MentionAction.HELLO:
            # It does not need complements.
            return True

        elif self.action == MentionAction.ADD:
            # Do we have actually words to parse?
            if len(words) == 0:
                self.error = self.ERROR_MISSING_PARAMS
                return False
            # First word needs to be a valid URL
            first_word = words.pop(0)
            if not Url.is_valid(first_word):
                self.error = self.ERROR_INVALID_URL
                return False
            # It could be already a RSS URL
            if Url.is_a_valid_feed(first_word):
                rss_url = first_word
            else:
                # Second, needs to be a valid RSS
                list_of_possible_rss_urls = Url.findfeeds(first_word)
                if len(list_of_possible_rss_urls) == 0:
                    self.error = self.ERROR_INVALID_RSS
                    return False
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
            else:
                alias = slugify(rss_url)
            # We could also have received a quoted text,
            #    which will be used as a feed name
            # And finally, set all of them as complements
            self.complements = {
                "alias": alias,
                "site_url": first_word,
                "feed_url": rss_url,
                "name": quoted_text
            }
            return True

        elif self.action == MentionAction.UPDATE:
            # Do we have actually words to parse?
            if len(words) == 0:
                self.error = self.ERROR_MISSING_PARAMS
                return False
            # First word needs to be an alias
            first_word = words.pop(0)
            if not self._feeds_storage.key_exists(first_word):
                self.error = self.ERROR_NOT_FOUND_ALIAS
                return False
            # We check again if we still have words
            if len(words) == 0:
                self.error = self.ERROR_MISSING_PARAMS
                return False
            # Second needs to be a valid URL
            second_word = words.pop(0)
            if not Url.is_valid(second_word):
                self.error = self.ERROR_INVALID_URL
                return False
            # It could be already a RSS URL
            if Url.is_a_valid_feed(first_word):
                rss_url = second_word
            else:
                # ... and contain a RSS
                list_of_possible_rss_urls = Url.findfeeds(second_word)
                if len(list_of_possible_rss_urls) == 0:
                    self.error = self.ERROR_INVALID_RSS
                    return False
                rss_url = list_of_possible_rss_urls[0]
            # We could also have received a quoted text,
            #    which will be used as a feed name
            # And finally, set all of them as complements
            self.complements = {
                "alias": first_word,
                "site_url": second_word,
                "feed_url": rss_url,
                "name": quoted_text
            }
            return True

        elif self.action == MentionAction.REMOVE:
            # Do we have actually words to parse?
            if len(words) == 0:
                self.error = self.ERROR_MISSING_PARAMS
                return False
            # First word needs to be an alias
            first_word = words.pop(0)
            if not self._feeds_storage.key_exists(first_word):
                self.error = self.ERROR_NOT_FOUND_ALIAS
                return False
            # Set it as complements
            self.complements = {"alias": first_word}
            return True

        elif self.action == MentionAction.LIST:
            # It does not need complements.
            return True

        elif self.action == MentionAction.TEST:
            # Do we have actually words to parse?
            if len(words) == 0:
                self.error = self.ERROR_MISSING_PARAMS
                return False
            # First word needs to be a valid URL
            first_word = words.pop(0)
            if not Url.is_valid(first_word):
                self.error = self.ERROR_INVALID_URL
                return False
            # It could be already a RSS URL
            if Url.is_a_valid_feed(first_word):
                rss_url = first_word
            else:
                # Second, needs to be a valid RSS
                list_of_possible_rss_urls = Url.findfeeds(first_word)
                if len(list_of_possible_rss_urls) == 0:
                    self.error = self.ERROR_INVALID_RSS
                    return False
                # We have something. Let's see, we pick the first occurrence.
                rss_url = list_of_possible_rss_urls[0]
            # And finally, set all of them as complements
            self.complements = {"site_url": first_word, "feed_url": rss_url}
            return True

    def is_alias_valid(self, alias) -> bool:
        return alias == slugify(alias)

    def small_user(self, username) -> str:
        # Generalising having the username with or without the @ in front
        username = username.lstrip("@")
        return f"@{username.split('@')[0]}"

    def user_can_write(self) -> str:
        return self._restrict_writes and (
            self.mention.username == self.admin.lstrip("@") or
            self.mention.username == self.small_user(self.admin).lstrip("@")
        )

    def get_text_inside_quotes(self, content) -> str:
        m = re.search(self.REGEXP_TEXT_WITHIN_QUOTES, content, re.UNICODE)
        if m is None:
            return None
        else:

            return m.group(1)

    def remove_self_username_from_content(self, content: str) -> tuple:
        """
        Removes the self username from the content.

        It returns a tuple where:
        - index 0 is the position where the username was found
        - index 1 is the content once cleaned
        """

        # This is a mention. There has to be ALWAYS the self username anywhere in the content.
        #   The username is expressed as short @feeder or long @feeder@social.arnaus.net.
        #   Let's start with the long one, as it's the one we have without calculations.

        # First we try to find the long username
        username = self.me
        username_position = content.find(username)
        if username_position < 0:
            # Not found, then we try the short username
            username = self.small_user(self.me)
            username_position = content.find(username)
            if username_position < 0:
                # Not found either, which is strange as it is a mention!
                #   then return as is.
                return -1, content

        # Now just remove the found username
        content = content.replace(username, "")

        # Apply some string cleanings,
        #   as removing may have left unwanted spaces
        content = content.replace("  ", " ").lstrip()

        # Return position and cleaned content
        return username_position, content.replace("  ", " ").lstrip()


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
        except RuntimeError:
            return None


class Mention:

    status_id: int = None
    content: str = None
    username: str = None
    visibility: StatusPostVisibility = None

    def __init__(
        self,
        status_id: int = None,
        content: str = None,
        username: str = None,
        visibility: StatusPostVisibility = None
    ) -> None:
        self.status_id = status_id
        self.content = content
        self.username = username
        self.visibility = visibility if visibility is not None\
            else StatusPostVisibility.PUBLIC

    def to_dict(self) -> dict:
        return {
            "status_id": self.status_id,
            "content": self.content,
            "username": self.username,
            "visibility": self.visibility
        }

    def from_dict(mention: dict) -> Mention:
        return Mention(
            mention["status_id"] if "status_id" in mention else None,
            mention["content"] if "content" in mention else None,
            mention["username"] if "username" in mention else None,
            StatusPostVisibility.valid_or_raise(mention["visibility"])
            if "visibility" in mention else None,
        )

    def from_streaming_notification(notification) -> Mention:
        return Mention.from_dict(
            {
                "status_id": notification.status.id,
                "content": notification.status.content,
                "username": notification.account.acct,
                "visibility": notification.status.visibility
            }
        )
