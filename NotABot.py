#! -*- coding: utf-8 -*-
import settings

from basebot import BaseIrcBot
from rand.randbot import RandBotMixin
from cleverbot.cleverircbot import CleverBotMixin
from quakenet.quakebot import QuakeNetBot
#from calc.calcbot import CalcBot
from currency.currencybot import CurrencyBot
from meteo.meteobot import MeteoBot
from feed.rssbot import RssBot

class StupidIrcBot(BaseIrcBot, RandBotMixin, CleverBotMixin, QuakeNetBot, CurrencyBot, MeteoBot, RssBot): #CalcBot (desactivated, so many potential problems)
    # TODO : HgBot, GitBot
    VERSION = '0.8'

    #TBI:
    # 'search'
    # 'google'
    # 'log' ? display a line from an old log
    # poll bot

    def on_welcome(self, serv, ev):
        super(StupidIrcBot, self).on_welcome(serv, ev)

        if getattr(settings, 'AUTH_ENABLE', False):
            self.authentify()
        
        try:
            self.fetch_feeds()
        except KeyboardInterupt:
            pass


    def get_user(self, user, cb=None, args=[]):
        if user:
            if getattr(settings, 'AUTH_ENABLE', False):
                auth = self.get_auth(user).get_auth(cb, args)
                if auth:
                    if cb:
                        cb(auth, *args)
                    return auth
                else:
                    # waiting for the response
                    return None
            else:
                if cb:
                    cb(user, *args)
                return user
        

if __name__ == '__main__':
    bot = StupidIrcBot()
    bot.start()
