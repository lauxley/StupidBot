#! -*- coding: utf-8 -*-
import sys

import settings

from basebot import BaseIrcBot, BaseCommand
from rand.randbot import RandBotMixin
from cleverbot.cleverircbot import CleverBotMixin
from quakenet.quakebot import QuakeNetBot
#from calc.calcbot import CalcBot
from currency.currencybot import CurrencyBot
from meteo.meteobot import MeteoBot
from feed.rssbot import RssBot


class HelpCommand(BaseCommand):
    NAME = u'help'
    HELP = u"""Display this help."""

    def get_response(self):
        if self.options:
            cmd = self.options[0]
            try:
                msg = self.bot.commands[cmd].HELP
            except KeyError,e:
                msg = u"No such command."
        else:
            msg = u"Here are the currently implemented commands : %s" % ', '.join(['!%s' % k for k in self.bot.commands.keys() if not getattr(self.bot.commands[k], 'is_hidden', False)])

        return msg


class VersionCommand(BaseCommand):
    NAME = u'version'
    HELP = u"Display the bot version."

    def get_response(self):
        return u"version: %s" % self.bot.VERSION


class PingCommand(BaseCommand):
    NAME = u'ping'
    HELP = u'peng'

    def get_response(self):
        # TODO do a real pinglol ?
        return u'pong'


class StupidIrcBot(BaseIrcBot): #CalcBot (desactivated, so many potential problems)
    VERSION = u'0.9'

    COMMANDS = [HelpCommand, VersionCommand, PingCommand]
    TRIGGERS = []

    def on_welcome(self, serv, ev):
        super(StupidIrcBot, self).on_welcome(serv, ev)

        if getattr(settings, 'AUTH_ENABLE', False):
            self.authentify()
        
        if 'RssBot' in settings.MODULES:
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
    except Exception, e:
        bot.error_logger.error('FATAL : %s', e)
        raise
