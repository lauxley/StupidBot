#! -*- coding: utf-8 -*-
import sys

import settings

from basebot import BaseIrcBot, BaseCommand, HelpCommand, VersionCommand, PingCommand

class StupidIrcBot(BaseIrcBot):
    VERSION = u'0.9.1'

    COMMANDS = [HelpCommand, VersionCommand, PingCommand]
    TRIGGERS = []
        

if __name__ == '__main__':
    bot = StupidIrcBot()
    try:
        bot.start()
    except Exception, e:
        bot.error_logger.error('FATAL : %s', e)
        raise
