from basebot import BaseTrigger 
from auth import BaseIdentPlugin, AuthCommand

class FreenodeAuth(BaseAuth):
    USER_INFO_CMD = u"ACC %s"

class BotAuthedTrigger(BaseTrigger):
    # TODO
    pass
  
class ACCTrigger(BaseTrigger):
    REGEXP = r'(?P<username>[^ ]+) ACC (?P<status>\d[0-3])'

    def handle(self):
        username = self.match.group('username')
        self.auth = self.bot.auth_plugin.get_auth(username)
        status = int(self.match.group('status'))
        if status == 0 or status == 1:
            self.auth.set_auth(None)
        else:
            self.auth.set_auth(username)


class Freenode(BaseIdentPlugin):
    AUTH_BOT = "NickServ"
    AUTH_CLASS = FreenodeAuth

    COMMANDS = [ AuthCommand, ]
    TRIGGERS = [ ACCTrigger ]
    
    def authentify(self):
        self.bot.error_logger.info("Authentifying with NickServ ...")
        self.bot.send(settings.AUTH_BOT, "identify %s %s" % (settings.AUTH_LOGIN, settings.AUTH_PASSWORD))
