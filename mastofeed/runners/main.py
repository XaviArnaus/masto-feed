from pyxavi.config import Config
from pyxavi.janitor import Janitor
from pyxavi.debugger import full_stack
from pyxavi.terminal_color import TerminalColor
from pyxavi.queue_stack import Queue
from mastofeed.lib.publisher import Publisher
from mastofeed.lib.keywords_filter import KeywordsFilter
from mastofeed.runners.runner_protocol import RunnerProtocol
from mastofeed.lib.queue_post import QueuePost
from definitions import ROOT_DIR
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pytz
import logging

from mastofeed.parsers.parser_protocol import ParserProtocol
from mastofeed.parsers.feed_parser import FeedParser


class Main(RunnerProtocol):
    '''
    Main Runner of the MastoFeed bot
    '''

    PARSERS = {
        "RSS Feed": {
            "module": FeedParser,
        },
    }
    MONTHS_POST_TOO_OLD = 6
    DEFAULT_QUEUE_FILE = "storage/queue.yaml"
    # Be careful, these parameters are not completelly merged here.
    #   There are still values defined in the module classes!
    DEFAULT = {
        "max_length": 400,
        "max_media_per_status": 4,
        "language": "en",
        "merge_content": True,
        "publish_only_older_toot": False
    }

    def __init__(self, config: Config, logger: logging, params: dict = None) -> None:
        self._config = config
        self._logger = logger

        self._keywords_filter = KeywordsFilter(config)
        self._queue = Queue(
            logger=self._logger,
            storage_file=config.get("queue_storage.file", self.DEFAULT_QUEUE_FILE)
        )
        self._publisher = Publisher(
            config=self._config,
            base_path=ROOT_DIR,
            only_oldest=self._config.get(
                "publisher.only_older_toot", self.DEFAULT["publish_only_older_toot"]
            ),
            queue=self._queue
        )

    def run(self) -> None:

        self._logger.info(f"{TerminalColor.MAGENTA}Main MastoFeed run{TerminalColor.END}")
        try:

            # Get the parsers that are active from the defined ones above.
            parsers = self.load_active_parsers()  # type: dict[str, ParserProtocol]

            # Get a config object specially prepared for the parsers
            parsers_config = self.prepare_config_for_parsers()

            for name, module in parsers.items():
                self._logger.info(f"{TerminalColor.YELLOW}Processing {name}{TerminalColor.END}")
                # Instantiate this parser
                instance = module(config=parsers_config)  # type: ParserProtocol

                # Walk through all sources defined in the parser's config
                for source, parameters in instance.get_sources().items():

                    self._logger.info(
                        f"{TerminalColor.BLUE}Processing source {source}{TerminalColor.END}"
                    )

                    # Get all the raw data related to this source
                    posts = instance.get_raw_content_for_source(source)
                    self._logger.debug(f"Ready to process {len(posts)} posts.")

                    # Walk the posts to process them
                    valid_posts = []  # type: list[QueuePost]
                    discarded_posts = 0
                    for post in posts:

                        # Apply filters
                        if self.is_post_invalid(post=post,
                                                source=source,
                                                instance=instance,
                                                source_params=parameters):
                            discarded_posts += 1
                            continue

                        valid_posts.append(post)

                    color = TerminalColor.END if discarded_posts == 0 else TerminalColor.RED
                    self._logger.info(
                        f"{color}Discarded {discarded_posts} posts.{TerminalColor.END}"
                    )

                    # At this point, we should add these new posts into the state
                    instance.set_ids_as_seen_for_source(source, [x.id for x in valid_posts])

                    # In some cases the instance wants to post process the resulting list.
                    processed_posts = instance.post_process_for_source(source, valid_posts)

                    # And finally walk them to download media and apply format
                    for post in processed_posts:

                        # Parse the content searching for media.
                        #   Some parsers would download them, some others would just
                        #   identify them and let the Publisher download them.
                        instance.parse_media(post)

                        # Format the post, according to what the instance wants.
                        instance.format_post_for_source(source, post)

                        # And finally, add it into the queue
                        self._queue.append(post)

                # Trying to isolate the possible issues between parsers,
                #   we secure the current queue before we move to the next parser.
                self._queue.deduplicate()
                self._queue.sort()
                self._queue.save()

                # Now publish the queue, according to the config preferences.
                self._publisher.publish_all_from_queue()

        except Exception as e:
            if self._config.get("janitor.active", False):
                remote_url = self._config.get("janitor.remote_url")
                if remote_url is not None and not self._config.get("publisher.dry_run"):
                    app_name = self._config.get("app.name")
                    Janitor(remote_url).error(
                        message="```" + full_stack() + "```",
                        summary=f"MastoFeed [{app_name}] failed: {e}"
                    )

            self._logger.exception(e)

    def load_active_parsers(self) -> dict:
        """Get the list of parsers that are active"""
        return {
            name: x["module"]
            for name,
            x in self.PARSERS.items() if "active" not in x or x["active"] is True
        }

    def prepare_config_for_parsers(self) -> Config:
        parsers_config = Config(params=self._config.get_all())
        parsers_config.merge_from_dict(
            parameters={
                "mastodon": self._publisher._mastodon, "default": self.DEFAULT
            }
        )
        return parsers_config

    def is_post_invalid(
        self, post: QueuePost, source: str, instance: ParserProtocol, source_params: dict
    ) -> bool:

        result = False
        if self._is_already_seen(post=post, source=source, instance=instance):
            result = True
        if not self._is_valid_date(post=post):
            result = True
        if not self._is_valid_keyword_profile(post=post, source_params=source_params):
            result = True

        return result

    def _is_valid_date(self, post: QueuePost) -> bool:
        # From the post we receive a datetime in the [published_at]
        #   Careful, the datetime is not UTF safe.
        initial_outdated_day = datetime.now().replace(tzinfo=pytz.UTC)\
            - relativedelta(months=self.MONTHS_POST_TOO_OLD)

        # Ensure we're measuring dates in UTC
        post_date_in_utc = post.published_at.replace(tzinfo=pytz.UTC)

        # Ensure that we have valid dates to perform the comparison.
        if not isinstance(post_date_in_utc, datetime):
            self._logger.warning(
                f"Discarding post {post.id}: Date {str(post.published_at)} is not a valid datetime"
            )
            return False

        # Let me debug the comparison.
        format = "%Y-%m-%d"
        self._logger.debug(
            f"{initial_outdated_day.strftime(format)} < " +\
            f"{post.published_at.replace(tzinfo=pytz.UTC).strftime(format)}: " +\
            f"{'Valid' if initial_outdated_day < post.published_at.replace(tzinfo=pytz.UTC) else 'Too Old'}")

        # Ok, now the proper comparison.
        if initial_outdated_day < post.published_at.replace(tzinfo=pytz.UTC):
            return True

        self._logger.debug(
            f"Discarding post {post.id}: Older than {self.MONTHS_POST_TOO_OLD} months"
        )
        return False

    def _is_valid_keyword_profile(self, post: QueuePost, source_params: dict) -> bool:
        # From the source_params we receive a str in [keywords_filter_profile]
        #   it can be str or None
        if "keywords_filter_profile" not in source_params:
            return True

        # The content to analyse comes in [raw_combined_body]
        #   and it is unclean, so it could come unnormalized.
        if self._keywords_filter.profile_allows_text(source_params["keywords_filter_profile"],
                                                     post.raw_combined_content):
            return True

        self._logger.debug(
            f"Discarding post {post.id}: Do not pass keywords profile " +
            f"{post.filters['keywords_profile']}"
        )
        return False

    def _is_already_seen(self, post: QueuePost, source: str, instance: ParserProtocol) -> bool:
        # From the post we get the ID. should never be None
        if instance.is_id_already_seen_for_source(source=source, id=post.id):
            self._logger.debug(f"Discarding post {post.id}: Already seen")
            return True

        return False


if __name__ == '__main__':
    Main().run()
