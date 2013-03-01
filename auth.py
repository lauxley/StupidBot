import threading
from basebot import BaseCommand, BaseBotPlugin, BaseTrigger

class BaseAuth(object):
    def __init__(self, bot, nick):
        self.nick = nick
        self.auth = None
        
        self.callbacks = []
        self._checked = False
        self.bot = bot
        self.timeout_flag = False
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
            

    def set_timeout(self):
        def _timedout():
            if self.timeout_flag:
                # the bot timed out, netsplit or whatever, he is not responding
                self.bot.error_logger.error("%s is not responding." % self.AUTH_BOT)
                self.timeout_flag = False
                self.set_auth(None)

        self.timeout_flag = True
        threading.Timer(self.bot.auth_plugin.AUTH_BOT_TIMEOUT, _timedout).start()

    def check_authed(self):
        self._checked = True
        self.is_checking = True
        self.bot.send(self.bot.auth_plugin.AUTH_BOT, self.USER_INFO_CMD % self.nick)
        self.set_timeout()

    def add_callback(self, cb, args):
        if cb:
            self.callbacks.append({'fn':cb,'args':args})

    def set_auth(self, auth):
        self.timeout_flag = False
        self.is_checking = False
        self.auth = auth
        self.process_callbacks()


class BaseAuthCommand(BaseCommand):
    """
    This is like a regular command but,
    it checks the auth_plugin to get the auth of the user issuing the command,
    as this can take some time, the result is asynchronous
    """
        
    def get_user_from_line(self):
        """
        override this if the default behavior is not what you want
        by default if there is at least an option,
        we check the auth from the first option, if not
        from the user who issued the command
        """
        if self.options:
            return self.options[0]
        return self.ev.source.nick

    def check_admin(self, user):
        if self._is_admin():
            self.bot.auth_plugin.get_user(self.get_user_from_line(), self.process)
        else:
            self.bot.send(self.ev.target, self.get_needs_to_be_admin())

    def handle(self):
        if self.REQUIRE_ADMIN:
            self.bot.auth_plugin.get_user(self.ev.source.nick, self.check_admin)
        else:
            self.bot.auth_plugin.get_user(self.get_user_from_line(), self.process)

    def process(self, user, *args, **kwargs):
        if user:
            self.user = user
        super(BaseAuthCommand, self).process()


class AuthCommand(BaseAuthCommand):
    """
    Ask the auth bot if the given user is authed/identified
    """
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


class BaseAuthTrigger(BaseTrigger):
    """
    Same as a regular trigger, but check the auth of the message's source
    """

    def get_user_from_line(self):
        """
        override this if the default behavior is not what you want
        """
        return self.match.group('username')

    def handle(self):
        # this method is just here to be homogenous with BaseCommand
        self.bot.auth_plugin.get_user(self.get_user_from_line(), self.process)
    
    def process(self, *args):
        pass


class BaseAuthPlugin(BaseBotPlugin):
    """
    This class is used to get the real user name of a user
    it can be overrided with settings.AUTH_PLUGIN, to use any irc auth method

    an auth plugin is a bit of a specific plugin,
    it shouldn't lie in settings.PLUGINS but in settings.AUTH_PLUGIN
    the get_user method could be asynchronous in some case, and so will always return None
    """
    def get_user(self, user, cb, *args, **kwargs):
        """
        This method will be called anytime we need to get a real user from a user name
        it is asynchronous, and will call command.process() passing user as an argument
        once it knows his real name
        """
        cb(user=user, *args, **kwargs)
        return None

    def get_username(self, user):
        return user


class BaseIdentPlugin(BaseAuthPlugin):
    """
    class used to authentify the bot, and identify other users
    """

    AUTH_BOT = ""  # the name of the bot used to identify
    AUTH_CLASS = BaseAuth
    AUTH_BOT_TIMEOUT = 5 # in seconds

    def __init__(self, bot):
        super(BaseIdentPlugin, self).__init__(bot)
        self.auths = {}

    def get_auth(self, user):
        if user in self.auths:
            auth = self.auths[user]
        else:
            auth = self.AUTH_CLASS(self.bot, user)
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

    def on_welcome(self, serv, ev):
        self.authentify()

    def _on_join(self, serv, ev):
        nick = ev.source.nick
        self.auths[nick] = self.AUTH_CLASS(self.bot, nick)

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
        user_list = e.arguments[2]
        for nick in [n for n in user_list if n not in self.auths]:
            self.auths[nick] = self.AUTH_CLASS(self.bot, nick)

    def authentify(self):
        """
        this is highly server specific !
        """
        pass
