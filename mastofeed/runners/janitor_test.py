from pyxavi.config import Config
from pyxavi.janitor import Janitor
from mastofeed.runners.runner_protocol import RunnerProtocol
import socket
import logging

#######
# This tests that the Janitor Wrapper for errors is working properly
##


class JanitorTest(RunnerProtocol):

    def __init__(
        self, config: Config, logger: logging, params: dict = None
    ) -> None:
        self._config = config
        self._logger = logger

    def run(self):
        if self._config.get("janitor.active", False):
            remote_url = self._config.get("janitor.remote_url")
            if remote_url is not None and not self._config.get("publisher.dry_run"):
                app_name = self._config.get("app.name")
                Janitor(remote_url).error(
                    message="```This is a test```",
                    summary=f"Echo bot [{app_name}] test in host: {socket.gethostname()}"
                )
            elif remote_url is None:
                self._logger.info("The remote URL is None. Set it in the config")
            elif self._config.get("publisher.dry_run"):
                self._logger.info("Publisher is set to dry run. Set it in the config")
            else:
                self._logger.info("Janitor does not run. Please check.")
        else:
            self._logger.info("Janitor is inactive. Activate it in the config")
