from pyxavi.config import Config
from pyxavi.janitor import Janitor
from pyxavi.debugger import full_stack
from pyxavi.terminal_color import TerminalColor
from pyxavi.mastodon_helper import MastodonHelper, MastodonConnectionParams
from mastofeed.lib.mentions_listener import MentionsListener
from mastofeed.runners.runner_protocol import RunnerProtocol
from definitions import ROOT_DIR
import logging
from urllib3.exceptions import ReadTimeoutError


class Listener(RunnerProtocol):
    '''
    Starts the Mastodon Streaming listener. It will kidnap the thread, so you better
    run it as a separated command and leave it running in the background.
    '''

    def __init__(self, config: Config, logger: logging, params: dict = None) -> None:
        self._config = config
        self._logger = logger

    def run(self) -> None:

        self._logger.info(f"{TerminalColor.MAGENTA}MastoFeed listener{TerminalColor.END}")
        try:

            # Instantiate the classes
            mastodon_instance = self._get_default_mastodon_instance()
            mention_listener = MentionsListener()
            mention_listener.load_config(config=self._config)

            # Set the listener for the Streaming for User stuff
            mastodon_instance.stream_user(mention_listener)
        
        except ReadTimeoutError as e:
            # Yeah, the servers may give a Timeout from time to time.
            #   How important is that?
            self._notify_through_janitor(e)
            # Log the error in a smaller way
            self._logger.error(f"Server Timeout: {e}")
            # Let's try an infinite loop
            self.run()

        except Exception as e:
            self._notify_through_janitor(e)
            # Log the exception
            self._logger.exception(e)
            # Let's try an infinite loop
            self.run()

    def _get_default_mastodon_instance(self, named_account="default"):
        return MastodonHelper.get_instance(
            connection_params=MastodonConnectionParams.from_dict(
                self._config.get(f"mastodon.named_accounts.{named_account}")
            ),
            logger=self._logger,
            base_path=ROOT_DIR
        )

    def _notify_through_janitor(self, e):
        is_janitor_active = self._config.get("janitor.active", False)
        is_dry_run = self._config.get("publisher.dry_run", True)
        remote_url = self._config.get("janitor.remote_url", None)

        if is_janitor_active and not is_dry_run and remote_url is not None:
            app_name = self._config.get("app.name")
            Janitor(remote_url).error(
                message="```\n" + full_stack() + "\n```",
                summary=f"MastoFeed Listener [{app_name}] failed: {e}"
            )


if __name__ == '__main__':
    Listener().run()
