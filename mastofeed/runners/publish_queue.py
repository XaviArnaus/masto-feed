from pyxavi.config import Config
from pyxavi.terminal_color import TerminalColor
from mastofeed.lib.publisher import Publisher
from mastofeed.runners.runner_protocol import RunnerProtocol
from definitions import ROOT_DIR
import logging


class QueuePublisher(RunnerProtocol):
    '''
    Main Runner of the Echo bot
    '''

    def __init__(
        self, config: Config, logger: logging, params: dict = None
    ) -> None:
        self._config = config
        self._logger = logger
        self._publisher = Publisher(config=self._config, base_path=ROOT_DIR)

    def run(self):
        '''
        Just publishes the queue
        '''
        try:
            self._logger.info(
                f"{TerminalColor.MAGENTA}Publishing whole queue{TerminalColor.END}"
            )
            self._publisher.publish_all_from_queue()
        except Exception as e:
            self._logger.exception(e)
