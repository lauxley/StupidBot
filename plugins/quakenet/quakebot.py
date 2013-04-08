import settings
from basebot import BaseTrigger
from auth import BaseIdentPlugin, AuthCommand, BaseAuth


class QuakenetAuth(BaseAuth):
    USER_INFO_CMD = u"WHOIS %s"


class QAuthTrigger(BaseTrigger):
    def handle(self):
        username = self.match.group('username')
        self.auth = self.bot.auth_plugin.get_auth(username)


class NotAuthedTrigger(QAuthTrigger):
    REGEXP = r"User (?P<username>[^ ]+) is not authed\."

    def handle(self):
        super(NotAuthedTrigger, self).handle()
        self.auth.set_auth(None)


class AuthedTrigger(QAuthTrigger):
    REGEXP = r"\-Information for user (?P<username>[^ ]+) \(using account (?P<authname>[^ ]+)\)"

    def handle(self):
        super(AuthedTrigger, self).handle()
        authname = self.match.group('authname')
        self.auth.set_auth(authname)


class UserUnknownTrigger(QAuthTrigger):
    REGEXP = r"Can\'t find user (?P<username>[^ ]+)."

    def handle(self):
        super(UserUnknownTrigger, self).handle()
        self.auth.set_auth(None)  # to call the callbacks
        # self.auth is a ghost Auth instance, created only to reply
        # to the command
        if self.auth.nick in self.bot.auth_plugin.auths:
            del self.bot.auth_plugin.auths[self.auth.nick]


class BotNotAuthedTrigger(BaseTrigger):
    REGEXP = r"WHOIS is only available to authed users."

    def handle(self):
        self.bot.error_logger.error(u'The bot was not authentified for some reason ...')
        self.bot.auth_plugin.authentify()


class BotAuthedTrigger(BaseTrigger):
    REGEXP = "You are now logged in as (?P<username>[^ ]+)."

    def handle(self):
        self.bot.error_logger.info('Authentified.')


class QuakeNetPlugin(BaseIdentPlugin):
    AUTH_CLASS = QuakenetAuth
    AUTH_BOT = "Q@CServe.quakenet.org"

    COMMANDS = [AuthCommand, ]
    TRIGGERS = [NotAuthedTrigger, AuthedTrigger, UserUnknownTrigger, BotNotAuthedTrigger, BotAuthedTrigger]

    def authentify(self):
        self.bot.error_logger.info("Authentifying with Q ...")
        self.bot.send(self.AUTH_BOT, "AUTH %s %s" % (settings.AUTH_LOGIN, settings.AUTH_PASSWORD))
