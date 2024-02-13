from argparse import ArgumentParser, Namespace
import pkg_resources
from mastofeed.runners.runner_protocol import RunnerProtocol
from pyxavi.terminal_color import TerminalColor
from pyxavi.config import Config
from pyxavi.logger import Logger
import os
from definitions import ROOT_DIR, CONFIG_DIR
from pyxavi.debugger import full_stack
from string import Template
import glob
import logging

from mastofeed.runners.main import Main
from mastofeed.runners.listener import Listener
from mastofeed.runners.publish_queue import QueuePublisher
from mastofeed.runners.publish_test import PublishTest
from mastofeed.runners.janitor_test import JanitorTest

PROGRAM_NAME = "MastoFeed"
CLI_NAME = "mastofeed"
PROGRAM_DESC = "CLI command to execute runners and tasks"
PROGRAM_EPILOG = f"Use [{CLI_NAME} commands] to get a list of available commands."
PROGRAM_VERSION = pkg_resources.get_distribution(PROGRAM_NAME).version
VERBOSE_LOGLEVEL = 10

SUBCOMMAND_TOKEN = "#SUBCOMMAND#"
HELP_TOKEN = "#HELP#"
IMPLEMENTED_IN_BASH_TOKEN = "#BASH#"
COMMAND_MAP = {
    "commands": (HELP_TOKEN, "Shows the list of available commands and subcommands"),
    "feed": (SUBCOMMAND_TOKEN, "Performs tasks related to the bot itself"),
    "mastodon": (SUBCOMMAND_TOKEN, "Performs tasks related to the Mastodon-like API"),
    "janitor": (SUBCOMMAND_TOKEN, "Performs tasks related to the Janitor API"),
    "validate_config": (IMPLEMENTED_IN_BASH_TOKEN, "Validates the current configs"),
}

SUBCOMMAND_MAP = {
    "feed": {
        "run": (Main, "Runs the application"),
        "listener": (Listener, "Runs the streaming listener"),
    },
    "mastodon": {
        "test": (
            PublishTest,
            "Publishes a test message to the Mastodon-like API to ensure that all is set up ok."
        ),
        "publish_queue": (
            QueuePublisher,
            "Publishes the current queue to the Mastodon-like API, attending the config file."
        ),
    },
    "janitor": {
        "test": (JanitorTest, "Tests the connection to the Janitor API")
    },
}


def print_command_list(with_colors: bool = True):
    main_template = "\n$title\n\nusage: $example_use\n\nCommand list:\n\n$command_list\n"
    title_template = "$name v$version"
    example_template = "$name command [subcommand]"
    command_template = "$command$description"
    subcommand_template = "  $subcommand$description"
    command_max_width = 20
    subcommand_max_width = 18

    if with_colors:
        title_template = f"{TerminalColor.ORANGE_BRIGHT}{title_template}{TerminalColor.END}"
        example_template = f"$name {TerminalColor.YELLOW_BRIGHT}command{TerminalColor.END} " +\
            f"[{TerminalColor.CYAN_BRIGHT}subcommand{TerminalColor.END}]"
        command_template = f"{TerminalColor.YELLOW_BRIGHT}{command_template}{TerminalColor.END}"
        subcommand_template = f"{TerminalColor.CYAN_BRIGHT}{subcommand_template}" +\
            f"{TerminalColor.END}"

    commands_list = []
    for command, pair in COMMAND_MAP.items():
        action, description = pair
        commands_list.append(
            Template(command_template).substitute(
                command=command.ljust(command_max_width), description=description
            )
        )
        if command in SUBCOMMAND_MAP:
            for subcommand, subpair in SUBCOMMAND_MAP[command].items():
                subaction, subdescription = subpair
                commands_list.append(
                    Template(subcommand_template).substitute(
                        subcommand=subcommand.ljust(subcommand_max_width),
                        description=subdescription
                    )
                )

    content = Template(main_template).substitute(
        title=Template(title_template
                       ).substitute(name=PROGRAM_NAME.capitalize(), version=PROGRAM_VERSION),
        example_use=Template(example_template).substitute(name=CLI_NAME),
        command_list="\n".join(commands_list)
    )
    print(content)


def _get_runner_by_command(args: Namespace) -> RunnerProtocol:
    command_candidate = args.command

    if command_candidate in COMMAND_MAP:
        # So we have this command registered.
        #   It can be a direct Runner or forwarding to a subcommand
        if COMMAND_MAP[command_candidate][0] == SUBCOMMAND_TOKEN:
            # Search it then inside the subcommands list
            if command_candidate in SUBCOMMAND_MAP:
                # Now get the subcommand
                subcommand_candidate = args.subcommand
                if subcommand_candidate in SUBCOMMAND_MAP[command_candidate]:
                    if SUBCOMMAND_MAP[command_candidate][subcommand_candidate][
                            0] == IMPLEMENTED_IN_BASH_TOKEN:
                        # It is not implemented in the Python side. We should never hit here!
                        raise RuntimeError(
                            f"The requested subcommand '{subcommand_candidate}' is meant to" +
                            " run in Bash but reached the Python side. " +
                            "Mostly a Runner setup error."
                        )
                    else:
                        # It is a direct Runner.
                        # DO NOT return the instance, let it be in the main.
                        return SUBCOMMAND_MAP[command_candidate][subcommand_candidate][0]
                elif subcommand_candidate is None:
                    # A subcommand is expected
                    raise RuntimeError(
                        f"The requested command '{command_candidate}' expects a" +
                        " subcommand, that is not present. Please type also a subcommand."
                    )
                else:
                    # Oops! It's not here, return an error
                    raise RuntimeError(
                        f"The requested subcommand '{subcommand_candidate}' relates to no" +
                        f" module for the command '{command_candidate}'"
                    )
            else:
                # Oops! Seems like the command does not have an entry into subcommands
                raise RuntimeError(
                    f"The requested command '{command_candidate}' is set up to have subcommands"
                    + " but these are not set up. Mostly a Runner setup error."
                )
        elif COMMAND_MAP[command_candidate][0] == IMPLEMENTED_IN_BASH_TOKEN:
            # It is not implemented in the Python side. We should never hit here!
            raise RuntimeError(
                f"The requested command '{command_candidate}' is meant to run in Bash" +
                " but reached the Python side. Mostly a Runner setup error."
            )
        else:
            # Rather than ignoring the subcommand, complain for the unexpected argument
            subcommand_candidate = args.subcommand
            if subcommand_candidate is not None:
                raise RuntimeError(
                    f"The requested command '{command_candidate}' is does not expect" +
                    "  subcommands but one is received. Stopping."
                )
            else:
                # It is a direct Runner.
                # DO NOT return the instance, let it be in the main.
                return COMMAND_MAP[command_candidate][0]
    else:
        # Oops! It's not here, return an error
        raise RuntimeError(f"The requested command '{command_candidate}' does not exist")


def setup_parser() -> ArgumentParser:

    parser = ArgumentParser(prog=CLI_NAME, description=PROGRAM_DESC, epilog=PROGRAM_EPILOG)

    # First argument is the command
    parser.add_argument("command", action="store")

    # Second argument is optional and should be the sub-command (test actions, for example)
    parser.add_argument("subcommand", nargs='?', default=None)

    # Ability to show the version
    parser.add_argument("--version", action="version", version=PROGRAM_VERSION)

    # Ability to override the Log level when using the CLI.
    parser.add_argument(
        "-l",
        "--loglevel",
        action="store",
    )

    # Shortcut to make the -l = 10, so it shows DEBUG (included) and higher.
    parser.add_argument("-d", "--debug", action="store_true")
    return parser


def load_config_files() -> Config:
    """
    Loads all configs existing in CONFIG_DIR.

    This is a merge-all-to-one approach, so may be the case that later objects
        overwrite older ones
    """
    config_files = glob.glob(os.path.join(CONFIG_DIR, "*.yaml"))

    # Yes, technically we're loading main.yaml twice
    config = Config(filename=os.path.join(CONFIG_DIR, "main.yaml"))
    for file in config_files:
        config.merge_from_file(filename=os.path.join(CONFIG_DIR, file))

    return config


def load_logger(config: Config, loglevel: int = None) -> logging:

    if loglevel is not None:
        # Lets first merge the config with the new value
        logger_config = config.get("logger")
        logger_config["loglevel"] = loglevel
        logger_config["stdout"]["active"] = True
        config.merge_from_dict(parameters={"logger": logger_config})

    return Logger(config=config, base_path=ROOT_DIR).get_logger()


def run():
    try:
        # Set up the parser
        parser = setup_parser()

        # Get the arguments
        args = parser.parse_args()

        # Adjust the log level
        loglevel = None
        if args.loglevel is not None:
            # for loglevel we expect an positive integer from 0 on.
            if args.loglevel is not None and isinstance(args.loglevel,
                                                        int) and args.loglevel >= 0:
                loglevel = args.loglevel
            else:
                raise RuntimeError(f"I don't understand the LogLevel [{args.loglevel}]")
        if args.debug is True:
            # verbose is just a shortcut to loglevel = 0 (or check the constant definition)
            if args.debug:
                loglevel = VERBOSE_LOGLEVEL

        # Instantiating the config and logger
        config = load_config_files()
        logger = load_logger(config=config, loglevel=loglevel)

        # This prints the list of available commands and leaves.
        if args.command == "commands":
            print_command_list()
            exit(0)

        # Find the command to execute. It is ready to be instantiated
        runner = _get_runner_by_command(args=args)(config=config, logger=logger)

        # Execute the runner
        runner.run()
    except RuntimeError as e:
        print(TerminalColor.RED_BRIGHT + str(e) + TerminalColor.END)
    except Exception:
        print(full_stack())
