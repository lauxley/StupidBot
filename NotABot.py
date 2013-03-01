#! -*- coding: utf-8 -*-
import sys

import settings

from basebot import BaseIrcBot, BaseCommand, HelpCommand, VersionCommand, PingCommand, ReconnectCommand, RestartCommand, IssueCommand

class StupidIrcBot(BaseIrcBot):
    VERSION = u'0.9.5'

    COMMANDS = [HelpCommand, VersionCommand, PingCommand, ReconnectCommand, IssueCommand] #RestartCommand
    TRIGGERS = []
        

if __name__ == '__main__':
    bot = StupidIrcBot()
    try:
        bot.start()
    except Exception, e:
        bot.error_logger.error('FATAL : %s', e)
        raise
