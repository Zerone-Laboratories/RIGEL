# This file is part of RIGEL Engine.
#
# RIGEL Engine is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# RIGEL Engine is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

import colorama
from colorama import Fore, Style
colorama.init(autoreset=True)
import logging
from logging import StreamHandler, Formatter, DEBUG, INFO, WARNING, ERROR, CRITICAL
from typing import Optional

class ColoredFormatter(Formatter):
    LEVEL_COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.MAGENTA
    }
    
    def format(self, record):
        level_color = self.LEVEL_COLORS.get(record.levelname, '')
        colored_record = logging.makeLogRecord(record.__dict__)
        colored_record.levelname = f"{level_color}{record.levelname}{Style.RESET_ALL}"
        
        return super().format(colored_record)

class SysLog:
    def __init__(self, name: str = "SysLog", level: int = INFO, log_file: Optional[str] = None):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        console_handler = StreamHandler()
        console_handler.setLevel(level)
        formatter = ColoredFormatter(f'%(asctime)s - {Fore.GREEN}%(name)s{Style.RESET_ALL} - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(level)
            # Use regular formatter for file (no colors in file)
            file_formatter = Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
    
    def debug(self, message: str):
        self.logger.debug(message)
    def info(self, message: str):
        self.logger.info(message)
    def warning(self, message: str):
        self.logger.warning(message)
    def error(self, message: str):
        self.logger.error(message)
    def critical(self, message: str):
        self.logger.critical(message)

# Example usage
if __name__ == "__main__":
    syslog = SysLog(name="RigelEngine", level=DEBUG, log_file="syslog.log")
    syslog.debug("This is a debug message.")
    syslog.info("This is an info message.")
    syslog.warning("This is a warning message.")
    syslog.error("This is an error message.")
    syslog.critical("This is a critical message.")