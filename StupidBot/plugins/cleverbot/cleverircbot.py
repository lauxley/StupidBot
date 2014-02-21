#! -*- coding: utf-8 -*-
#from cleverbot import Cleverbot
from chatterbotapi import ChatterBotFactory, ChatterBotType
import settings

from basebot import BaseBotPlugin, BaseTrigger


class CleverBotTrigger(BaseTrigger):
    REGEXP = r'(?P<me>%s):?(?P<msg>.*)' % settings.NICK

    def process(self):
        # TODO : should be asynchronous
        msg = self.bot.brain.think(self.match.group('msg').encode('ascii', 'replace'))
        self.bot.send(self.ev.target, '%s: %s' % (self.ev.source.nick, msg))


class CleverBotPlugin(BaseBotPlugin):
    COMMANDS = []
    TRIGGERS = [CleverBotTrigger]

    def __init__(self, bot):
        super(CleverBotPlugin, self).__init__(bot)
        factory = ChatterBotFactory()
        cleverbot = factory.create(ChatterBotType.CLEVERBOT)
        self.bot.brain = cleverbot.create_session()
