import settings

class QuakeNetBot():
    """
    channel.userdict doesn't quite have what we need, 
    so we will add another dict to the instance, not channel specific
    self.auths = {
          'name_from_users': 'auth_name',
          'name_from_users2': None, # not authed
    }
    """
    is_bot_module = True
    auths = {}

    CALLBACKS = {}

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
            self.auths[nick] = None
            self.check_authed(serv, nick)

    # def _on_part(self, c, e):
        
    #def _on_kick(self, c, e):
        
    def _on_nick(self, c, e):
        super(QuakeNetBot, self)._on_nick(c, e)
        if settings.AUTH_ENABLE:
            before = e.source.nick
            after = e.target
            auth = self.auths[nick]
            del self.auths[before]
            self.auths[after] = after


    def _on_quit(self, c, e):
        super(QuakeNetBot, self)._on_quit(c, e)
        if settings.AUTH_ENABLE:
            nick = e.source.nick
            del self.auth[nick]


    def _add_callback(self, user, target, cb):
        if not self.CALLBACKS.has_key(user):
            self.CALLBACKS[user] = []
        self.CALLBACKS[user].append({'fn':cb,'target':target})

    def authentify(self, serv):
        """
        this is highly server specific !
        """
        serv.privmsg(settings.AUTH_BOT, "AUTH %s %s" % (settings.AUTH_LOGIN, settings.AUTH_PASSWORD))


    def check_authed(self, serv, user):
        """
        returns the auth of the user, None if not authed

        /msg Q WHOIS user
        (11:57:55) Q: (notice) User luc2 is not authed.
        OR
        (11:56:00) Q: (notice) -Information for user NotABot (using account NotABot):
        """
        serv.privmsg(settings.AUTH_BOT, "WHOIS %s" % user)


    def is_authed(self, serv, target, user, callback=None):
        if not self.auths.get(user, False):
            if callback:
                self._add_callback(user, target, callback)
            self.check_authed(serv, user)
        else:
            self.tell_auth(serv, target, user)


    def tell_auth(self, serv, target, user):
        if self.auths.get(user, False):
            serv.privmsg(target, 'Authed as %s' % self.auths[user])
        else:
            serv.privmsg(target, '%s is not authed.' % user)


    # COMMANDS HANDLERS
    def auth_handler(self, serv, ev, *args):
        """
        return the auth for given user
        """
        if settings.AUTH_ENABLE:
            if not len(args):
                user = ev.source.nick
            else:
                user = args[0]
            
            self.is_authed(serv, ev.target, user, callback=self.tell_auth)
            return ev.target, None
        else:
            return ev.target, u'auth module desactivated !'


    # REGEXPS HANDLERS
    def not_authed_handler(self, match, serv, ev):
        if settings.AUTH_ENABLE:
            username = match.group('username')
            self.auths[username] = None

            if self.CALLBACKS.has_key(username):
                for cb in self.CALLBACKS[username]:
                    cb['fn'](serv, cb['target'], username)
                del self.CALLBACKS[username]
                
        return ev.target, None

    def authed_handler(self, match, serv, ev):

        if settings.AUTH_ENABLE:
            username = match.group('username')
            authname = match.group('authname')
            self.auths[username] = authname

            if self.CALLBACKS.has_key(username):
                for cb in self.CALLBACKS[username]:
                    cb['fn'](serv, cb['target'], username)
                del self.CALLBACKS[username]                

        return ev.target, None        
