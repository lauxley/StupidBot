#! -*- coding: utf-8 -*-
import settings

from basebot import BaseIrcBot
from rand.randbot import RandBotMixin
from cleverbot.cleverircbot import CleverBotMixin

class StupidIrcBot(BaseIrcBot, RandBotMixin, CleverBotMixin):
    # TODO : HgBot, GitBot
    VERSION = '0.5'
    r_date_fr = r'(?P<day>[0-3][0-9])(?P<month>[0-1][0-9])(?P<year>[0-9]{4})'

    #TBI:
    # 'search'
    # 'google'
    # 'log' ? display a line from an old log
    # answer to direct highligh cleverbot ?
    # 'meteo' [town] [now|today|tomorrow]
    # poll bot
    # currency

    def authentify(self, serv):
        """
        this is highly server specific !
        """
        serv.privmsg(settings.AUTH_BOT, "AUTH %s %s" % (settings.AUTH_LOGIN, settings.AUTH_PASSWORD))

bot = StupidIrcBot()
bot.start()
