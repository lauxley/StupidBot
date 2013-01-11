#! -*- coding: utf-8 -*-
import sys

import settings

from basebot import BaseIrcBot
from rand.randbot import RandBotMixin
from cleverbot.cleverircbot import CleverBotMixin
from quakenet.quakebot import QuakeNetBot
#from calc.calcbot import CalcBot
from currency.currencybot import CurrencyBot
from meteo.meteobot import MeteoBot
from feed.rssbot import RssBot


class HelpCommand(BaseCommand):
    HELP = u"""Display this help."""
    def tell(self)
        try:
            cmd = self.options[0]
        except IndexError,e:
            msg = u"Here are the currently implemented commands : %s" % ', '.join(['!%s' % k for k in self.bot.COMMANDS.keys() if not getattr(self.bot.COMMANDS[k], 'is_hidden', False)])
        else:
            try:
                msg = getattr(self, self.bot.COMMANDS[cmd]).HELP
            except KeyError,e:
                msg = u"No such command."
        return msg


class VersionCommand(BaseCommand):
    HELP = u"Display the bot version."
    def tell(self):
        return u"version: %s" % self.bot.VERSION


class PingCommand(BaseCommand):
    def tell(self):
        return u'pong'


class StupidIrcBot(BaseIrcBot): #CalcBot (desactivated, so many potential problems)
    VERSION = '0.8'

    COMMANDS = {'help': HelpCommand, 'version': VersionCommand, 'Ping': PingCommand}
    TRIGGERS = []

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
    try:
        bot.start()
    except e:
        bot.error_logger.error('FATAL : %s', e)
        sys.exit()
