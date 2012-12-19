import settings
from multiprocessing import Pool

class Auth():
    def __init__(self, serv, nick):
        self.nick = nick
        self.callbacks = []
        self.auth = None
        self._checked = False
        self.server = serv
        self.check_authed()


    def get_auth(self, cb=None, args=None):
        if self.auth:
            return self.auth
        elif not self._checked:
            self._add_callback(cb, args)
            self.check_authed()
        return None

            
    def check_authed(self):
        """
        returns the auth of the user, None if not authed

        /msg Q WHOIS user
        (11:57:55) Q: (notice) User luc2 is not authed.
        OR
        (11:56:00) Q: (notice) -Information for user NotABot (using account NotABot):
        """
        self.server.privmsg(settings.AUTH_BOT, "WHOIS %s" % self.nick)


    def _add_callback(self, cb, args):
        if cb:
            self.callbacks.append({'fn':cb,'args':args})


    def set_auth(self, auth):
        self.auth = auth


class QuakeNetBot():
    """
    channel.userdict doesn't quite have what we need, 
    so we will add another dict to the instance, not channel specific
    self.auths = {
          'name_from_users': Auth(),
          'name_from_users2': Auth()
    }
    """
    is_bot_module = True
    auths = {}

    COMMANDS = {
        'auth': 'auth_handler'
        }

    REGEXPS = {
        r"User (?P<username>[^ ]+) is not authed\." : "not_authed_handler",
        r"\-Information for user (?P<username>[^ ]+) \(using account (?P<authname>[^ ]+)\)" : "authed_handler"
        }

    # override to change self.auths
    def _on_join(self, serv, ev):
        super(QuakeNetBot, self)._on_join(serv, ev)
        if settings.AUTH_ENABLE:
            nick = e.source.nick
            self.auths[nick] = Auth(serv, nick)
            self.auths[nick].check_authed()

    #def _on_part(self, c, e):
    #def _on_kick(self, c, e):

    def _on_nick(self, c, e):
        super(QuakeNetBot, self)._on_nick(c, e)
        if settings.AUTH_ENABLE:
            before = e.source.nick
            after = e.target
            auth = self.auths[before]
            del self.auths[before]
            self.auths[after] = auth


    def _on_quit(self, c, e):
        super(QuakeNetBot, self)._on_quit(c, e)
        if settings.AUTH_ENABLE:
            nick = e.source.nick
            del self.auths[nick]


    def authentify(self):
        """
        this is highly server specific !
        """
        self.server.privmsg(settings.AUTH_BOT, "AUTH %s %s" % (settings.AUTH_LOGIN, settings.AUTH_PASSWORD))


    def get_authname(self, user):
        return self.get_auth(user).auth


    def get_auth(self, user, recheck=False):
        """
        recheck force the check of the auth
        """
        if not self.auths.has_key(user):
            self.auths[user] = Auth(self.server, user)
        else:
            if recheck:
                self.auths[user]._checked = False
        return self.auths[user]


    # COMMANDS HANDLERS
    def auth_handler(self, ev, *args):
        def _tell_auth(auth, user, target):
            if self.auths[user].auth:
                self.server.privmsg(target, '%s is authed as %s' % (user, self.auths[user].auth))
            else:
                self.server.privmsg(target, '%s is not authed.' % user)

        if settings.AUTH_ENABLE:
            if not len(args):
                user = ev.source.nick
            else:
                user = args[0]

            self.get_auth(user, recheck=True).get_auth(_tell_auth, [user, ev.target])
            return ev.target, None
        else:
            return ev.target, u'auth module desactivated !'


    # REGEXPS HANDLERS
    def not_authed_handler(self, match, ev):
        self._checked = True
        if settings.AUTH_ENABLE:
            username = match.group('username')
            a = self.get_auth(username)
            a.set_auth(None)
            
            for cb in a.callbacks:
                if not cb.get('_lock', False):
                    cb['_lock'] = True
                    cb['fn'](a.nick, *cb['args'])
                    del cb
                
        return ev.target, None

    def authed_handler(self, match, ev):
        self._checked = True
        if settings.AUTH_ENABLE:
            username = match.group('username')
            authname = match.group('authname')
            a = self.auths[username]
            a.set_auth(authname)

            for cb in a.callbacks:
                if not cb.get('_lock', False):
                    cb['_lock'] = True
                    cb['fn'](a.auth, *cb['args'])
                    del cb

        return ev.target, None
