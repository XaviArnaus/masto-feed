from pyxavi.config import Config
from pyxavi.janitor import Janitor
from pyxavi.debugger import full_stack
from pyxavi.terminal_color import TerminalColor
from pyxavi.mastodon_helper import MastodonHelper, MastodonConnectionParams
from mastofeed.lib.mentions_listener import MentionsListener
from mastofeed.runners.runner_protocol import RunnerProtocol
from definitions import ROOT_DIR
import logging


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
            # mastodon_instance.stream_user(mention_listener, run_async=True, reconnect_async=True)
            mastodon_instance.stream_user(mention_listener)

        except Exception as e:
            if self._config.get("janitor.active", False):
                remote_url = self._config.get("janitor.remote_url")
                if remote_url is not None and not self._config.get("publisher.dry_run"):
                    app_name = self._config.get("app.name")
                    Janitor(remote_url).error(
                        message="```" + full_stack() + "```",
                        summary=f"Echo bot [{app_name}] failed: {e}"
                    )

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


if __name__ == '__main__':
    Listener().run()
