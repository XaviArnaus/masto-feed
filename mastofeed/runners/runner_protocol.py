from typing import Protocol, runtime_checkable
from pyxavi.config import Config
import logging


@runtime_checkable
class RunnerProtocol(Protocol):

    def __init__(
        self, config: Config, logger: logging, params: dict = None
    ) -> None:
        """Initializing the class"""

    def run(self) -> None:
        """Method that will be called to trigger the runner"""
