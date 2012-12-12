import logging
import os
import re
from logging import handlers

from irc.client import DecodingLineBuffer
from irc.bot import SingleServerIRCBot

import settings

class CompliantDecodingLineBuffer(DecodingLineBuffer):
    errors = 'replace'

class BaseIrcBot(SingleServerIRCBot):
    # commands modes : ANY | PUBLIC | PRIVATE : tells if the bot will respond to commands on a private msg or a public channel
    
    MAX_MSG_LEN = 450 #its 512 but we need some space for the command arguments

    COMMANDS = {
        'version': 'version_handler',
        'help': 'help_handler',
        'ping': 'ping_handler',
        }

    def __init__(self):
        super(BaseIrcBot, self).__init__([(settings.SERVER,),], settings.NICK, settings.REALNAME)
        self._init_loggers()
        self._init_modules()
        self.ircobj.add_global_handler("all_events", self.global_handler)

    def _init_modules(self):
        for b in self.__class__.__bases__:
            print '-', self.COMMANDS
            self.COMMANDS.update(getattr(b, 'COMMANDS', {}))
            self.REGEXPS.update(getattr(b, 'REGEXPS', {}))
            if hasattr(b, '_init'): # TODO: we may want to rename it to something like _init_bot or smtg
                b._init(self)

    def send(self, serv, target, msg):
        while len(msg) > self.MAX_MSG_LEN:
            time.sleep(1) # so we don't get disco for excess flood
            ind = msg.rfind(" ", 0, self.MAX_MSG_LEN)
            buff = msg[ind:]
            serv.privmsg(target, msg[:ind])
            msg = buff
        serv.privmsg(target, msg)   


    def get_needs_to_be_admin(self):
        return "Sorry, you can't do that by yourself, ask %s" % (" or ".join(settings.ADMINS))


    def check_admin(self, hdl, ev):
        return (getattr(hdl, 'needs_admin', False) and self.get_username_from_source(ev.source) not in settings.ADMINS)


    def get_username_from_source(self, source):
        # change this using the real auth
        try:
            return source.split("!")[0]
        except IndexError:
            return source


    def _init_loggers(self):
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        if not os.path.isdir(settings.LOG_DIR):
            os.mkdir(os.path.join(os.path.dirname(__file__),settings.LOG_DIR))

        msg_logger = logging.getLogger('msgslog')
        msg_logger.setLevel(logging.DEBUG)
        handler = logging.handlers.TimedRotatingFileHandler(os.path.join(settings.LOG_DIR, 'daily.log'), when='midnight')
        handler.setFormatter(formatter)
        msg_logger.addHandler(handler)
        self.msg_logger = msg_logger

        error_logger = logging.getLogger('errorlog')
        error_logger.setLevel(logging.WARNING)
        handler = logging.FileHandler(os.path.join(settings.LOG_DIR, 'error.log'))
        handler.setFormatter(formatter)
        error_logger.addHandler(handler)
        self.error_logger = error_logger


    def on_welcome(self, serv, ev):
        # changing the default Buffer to ensure no encoding error
        self.connection.buffer = CompliantDecodingLineBuffer()

        for chan in settings.START_CHANNELS:
            self.connection.join(chan)

        if getattr(settings, 'AUTH_ENABLE', False):
            self.authentify(serv)


    def authentify(self, serv):
        """
        this is highly server specific !
        thus needs to be overrided
        """
        pass


    def global_handler(self, serv, ev):        
        try:
            self.msg_logger.info('%s %s>%s: %s' % (ev.type, ev.source, ev.target, ev.arguments))
            response = None
            if ev.type == "pubmsg":
                msg = ev.arguments[0]
                if msg[0] == '!':
                    try:
                        l = msg[1:].split(' ')
                        try:
                            cmd, arguments = l[0], l[1:]
                        except ValueError, e:
                            # there is no arguments
                            cmd = msg[1:]
                            arguments = []
                        hdl = getattr(self, self.COMMANDS[cmd])
                        if self.check_admin(hdl, ev):
                            target, response = ev.target, self.get_needs_to_be_admin()
                        else:
                            target, response = hdl(serv, ev, *arguments)

                    except KeyError, e:
                        self.error_logger.warning('Invalid command : %s' % e)
                else:
                    for regexp in self.REGEXPS.keys():
                        m = re.match(regexp, msg)
                        if m:
                            target, response = getattr(self, self.REGEXPS[regexp])(m, serv, ev)
                            # break # should we ?
                if response:
                    self.send(serv, target, response)
            else:
                # TODO: handle privmsgs
                pass
        except IndexError:
            pass


    # CMD HANDLERS
    def help_handler(self, serv, ev, *args):
        try:
            cmd = args[0]
        except IndexError,e:
            msg = u"Here are the currently implemented commands : %s" % ', '.join(['!%s' %k for k in self.COMMANDS.keys() if getattr(self.COMMANDS[k], 'is_hidden', False)])
        else:
            msg = getattr(self, '%s_handler' % cmd).help
        return ev.target, msg
    help_handler.help = u"""Display this help."""

    def version_handler(self, serv, ev, *args):
        return ev.target, u"version: %s" % self.VERSION
    version_handler.help = u"""Display the bot version."""

    def ping_handler(self, serv, ev, *args):
        return ev.target, u'pong'
    ping_handler.help = u"""!ping: pong?"""
    ping_handler.is_hidden = False # only an example


