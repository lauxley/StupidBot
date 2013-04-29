from basebot import BaseTrigger
from auth import BaseIdentPlugin, AuthCommand, BaseAuth

import settings


class FreenodeAuth(BaseAuth):
    USER_INFO_CMD = u"ACC %s"


# class BotNotAuthedTrigger(BaseTrigger):
#     REGEXP = r"WHOIS is only available to authed users."

#     def handle(self):
#         self.bot.error_logger.error(u'The bot was not authentified for some reason ...')
#         self.bot.auth_plugin.authentify()


class BotAuthedTrigger(BaseTrigger):
    REGEXP = "You are now identified for (?P<username>[^ ]+)."

    def handle(self):
        self.bot.error_logger.info('Authentified.')


class ACCTrigger(BaseTrigger):
    REGEXP = r'(?P<username>[^ ]+) ACC (?P<status>[0-3])'

    def handle(self):
        username = self.match.group('username')
        self.auth = self.bot.auth_plugin.get_auth(username)
        status = int(self.match.group('status'))
        if status == 0 or status == 1:
            self.auth.set_auth(None)
        else:
            self.auth.set_auth(username)


class FreenodePlugin(BaseIdentPlugin):
    AUTH_CLASS = FreenodeAuth
    AUTH_BOT = "NickServ"

    COMMANDS = [AuthCommand,]
    TRIGGERS = [ACCTrigger, BotAuthedTrigger]  # , BotNotAuthedTrigger

    def authentify(self):
        self.bot.error_logger.info("Authentifying with NickServ ...")
        self.bot.send(self.AUTH_BOT, "identify %s %s" % (settings.AUTH_LOGIN, settings.AUTH_PASSWORD))
