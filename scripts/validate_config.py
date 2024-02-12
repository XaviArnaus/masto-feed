import yaml
import glob
import os
from definitions import CONFIG_DIR
from pyxavi.terminal_color import TerminalColor


def run():
    config_files = glob.glob(os.path.join(CONFIG_DIR, "*.yaml"))
    for file in config_files:
        try:
            yaml.safe_load(open(os.path.join(CONFIG_DIR, file)))
            print(f"{TerminalColor.GREEN_BRIGHT}File {file} is correct{TerminalColor.END}")
        except Exception as e:
            print(f"{TerminalColor.RED_BRIGHT}File {file} is incorrect{TerminalColor.END}")
            print(e)
