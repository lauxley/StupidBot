#! -*- coding: utf-8 -*-
from cleverbot import Cleverbot
import settings

from basebot import BaseBotPlugin, BaseTrigger


class CleverBotTrigger(BaseTrigger):
    REGEXP = r'(?P<me>%s):?(?P<msg>.*)' % settings.NICK

    def process(self):
        # TODO : should be asynchronous
        self.bot.send(self.ev.target, '%s: %s' % (self.ev.source.nick, self.bot.brain.ask(self.match.group('msg').encode('ascii', 'replace'))))


class CleverBotPlugin(BaseBotPlugin):
    COMMANDS = []
    TRIGGERS = [CleverBotTrigger]

    def __init__(self, bot):
        super(CleverBotPlugin, self).__init__(bot)
        self.bot.brain = Cleverbot()
