#! -*- coding: utf-8 -*-
import cleverbot
import settings

from basebot import BaseBotModule, BaseTrigger

class CleverBotTrigger(BaseTrigger):
    REGEXP = r'(?P<me>%s):?(?P<msg>.*)' % settings.NICK

    def process(self):
        # TODO : should be asynchronous
        self.bot.send(self.ev.target, self.bot.brain.Ask(self.match.group('msg').encode('ascii', 'replace')))

class CleverBotModule(BaseBotModule):
    COMMANDS = []
    TRIGGERS = [CleverBotTrigger]

    def __init__(self, bot):
        super(CleverBotModule, self).__init__(bot)
        self.bot.brain = cleverbot.Session()
