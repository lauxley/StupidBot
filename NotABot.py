#! -*- coding: utf-8 -*-
import settings

from basebot import BaseIrcBot
from rand.randbot import RandBotMixin
from cleverbot.cleverircbot import CleverBotMixin
from quakenet.quakebot import QuakeNetBot

class StupidIrcBot(BaseIrcBot, RandBotMixin, CleverBotMixin, QuakeNetBot):
    # TODO : HgBot, GitBot
    VERSION = '0.6'

    #TBI:
    # 'search'
    # 'google'
    # 'log' ? display a line from an old log
    # answer to direct highligh cleverbot ?
    # 'meteo' [town] [now|today|tomorrow]
    # poll bot
    # currency

if __name__ == '__main__':
    bot = StupidIrcBot()
    bot.start()
