import imp

import settings
from basebot import BaseCommand, BaseAuthCommand, BaseTrigger, BaseAuthPlugin

class Auth():
    def __init__(self, bot, nick):
        self.nick = nick
        self.auth = None
        
        self.callbacks = []
        self._checked = False
        self.bot = bot
        self.check_authed()

    def get_auth(self):
        if self.auth:
            u = self.auth
        elif not self._checked:
            self.check_authed()
            u = None
            # waiting for response
        else:
            u = self.nick

        return u

    def process_callbacks(self):
        for cb in self.callbacks:
            if not cb.get('_lock', False):
                cb['_lock'] = True
                cb['fn'](self, *cb['args'])
                del cb
            
    def check_authed(self):
        """
        returns the auth of the user, None if not authed

        /msg Q WHOIS user
        (11:57:55) Q: (notice) User luc2 is not authed.
        OR
        (11:56:00) Q: (notice) -Information for user NotABot (using account NotABot):
        """
        self._checked = True
        self.is_checking = True
        self.bot.send(settings.AUTH_BOT, "WHOIS %s" % self.nick)

    def add_callback(self, cb, args):
        if cb:
            self.callbacks.append({'fn':cb,'args':args})

    def set_auth(self, auth):
        self.is_checking = False
        self.auth = auth
        self.process_callbacks()


class AuthCommand(BaseAuthCommand):
    NAME = "auth"
    HELP = u"auth [user] : tell the auth status of user with Q, also force the check."

    def handle(self):
        if self.REQUIRE_ADMIN:
            self.bot.auth_plugin.get_user(self.ev.source.nick, self.check_admin, force_check=True)
        else:
            self.bot.auth_plugin.get_user(self.get_user_from_line(), self.process, force_check=True)

    def get_response(self):
        if self.user.nick:
            if self.user.auth:
                return u"%s is authed as %s." % (self.user.nick, self.user.auth)
            else:
                return u"%s is not authed." % self.user.nick
        else:
            return u"%s is unknown."


class AuthTrigger(BaseTrigger):
    def handle(self):
        username = self.match.group('username')
        self.auth = self.bot.auth_plugin.get_auth(username)
        

class NotAuthedTrigger(AuthTrigger):
    REGEXP = r"User (?P<username>[^ ]+) is not authed\."

    def handle(self):
        super(NotAuthedTrigger, self).handle()
        self.auth.set_auth(None)
        

class AuthedTrigger(AuthTrigger):
    REGEXP = r"\-Information for user (?P<username>[^ ]+) \(using account (?P<authname>[^ ]+)\)"

    def handle(self):
        super(AuthedTrigger, self).handle()
        authname = self.match.group('authname')
        self.auth.set_auth(authname)
        

class UserUnknownTrigger(AuthTrigger):
    REGEXP = r"Can\'t find user (?P<username>[^ ]+)."

    def handle(self):
        super(UserUnknownTrigger, self).handle()
        # self.auth is a ghost Auth instance, created only to reply
        # to the command
        if self.auth.nick in self.bot.auth_plugin.auths:
            del self.bot.auth_plugin.auths[self.auth.nick]


class BotNotAuthedTrigger(BaseTrigger):
    REGEXP = r"WHOIS is only available to authed users."

    def handle(self):
        self.bot.auth_plugin = BaseAuthPlugin
        self.bot.error_logger.error(u'The bot is not Authed for some reason ! the Quakenet Auth Plugin has been desactivated.')


class QuakeNetPlugin(BaseAuthPlugin):
    """
    channel.userdict doesn't quite have what we need, 
    so we will add another dict to the instance, not channel specific
    self.auths = {
          'name_from_users': Auth(),
          'name_from_users2': Auth()
    }
    """

    # TODO : a trigger to catch a successfull authentification of the bot, or unload the plugin

    auths = {}

    COMMANDS = [ AuthCommand, ]
    TRIGGERS = [ NotAuthedTrigger, AuthedTrigger, UserUnknownTrigger, BotNotAuthedTrigger ]
    
    def __init__(self, bot):
        super(QuakeNetPlugin, self).__init__(bot)
        self.authentify()

    def get_auth(self, user):
        if user in self.auths:
            auth = self.auths[user]
        else:
            auth = Auth(self.bot, user)
            self.auths[user] = auth
        return auth

    def get_user(self, user, cb, *args, **kwargs):
        auth = self.get_auth(user)
        if 'force_check' in kwargs and kwargs['force_check'] == True and not auth.is_checking:
            auth.check_authed()

        auth.add_callback(cb, args)
        if auth._checked and not auth.is_checking:
            auth.process_callbacks()

    def get_username(self, user):
        return user.get_auth()

    def _on_join(self, serv, ev):
        nick = ev.source.nick
        self.auths[nick] = Auth(self.bot, nick)

    #def _on_part(self, c, e):
    #def _on_kick(self, c, e):

    def _on_nick(self, c, e):
        before = e.source.nick
        after = e.target
        auth = self.auths[before]
        del self.auths[before]
        self.auths[after] = auth

    def _on_quit(self, c, e):
        nick = e.source.nick
        del self.auths[nick]

    def _on_namreply(self, c, e):
        # e.arguments[0] == "@" for secret channels,
        #                     "*" for private channels,
        #                     "=" for others (public channels)
        # e.arguments[1] == channel
        # e.arguments[2] == nick list
        # TODO
        pass

    def authentify(self):
        """
        this is highly server specific !
        """
        self.bot.error_logger.info("Authentifying with Q")
        self.bot.send(settings.AUTH_BOT, "AUTH %s %s" % (settings.AUTH_LOGIN, settings.AUTH_PASSWORD))
