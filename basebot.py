import logging
import os
import re
import datetime, time
from logging import handlers

from irc.client import DecodingLineBuffer
from irc.bot import SingleServerIRCBot

import settings

class CompliantDecodingLineBuffer(DecodingLineBuffer):
    errors = 'replace'

class ImproperlyConfigured(Exception):
    pass

class BaseCommand(object):
    """
    Abstract class for any command
    commands are specific messages send specifically for the bot to do something
    on contrary, triggers are messages not aimed at the bot, that it catches.
    """
    NAME = u""

    # if True, only the user(s) defined in settings.ADMIN can issue this command
    REQUIRE_ADMIN = False 

    # if True, will not appear in the list of commands and stuff..
    IS_HIDDEN = False

    # will be printed when someone issue a !help <COMMAND>
    HELP = u"Sorry, no help for this command yet !"

    # possible values of TARGET: 
    # * source : the response will be send directly to the user issuing the command in a private message
    # * target : will respond to the same channel were the command was issued
    TARGET = "target"


    def __init__(self, bot):
        self.bot = bot


    def _parse_options(self, ev):
        return ev.arguments[0].split(" ")[1:]


    def get_response(self, ev):
        """
        most of the time this will be the only method to implement
        """
        return u""

    
    def process(self, ev):
        if not self.REQUIRE_ADMIN or ev.source.nick in settings.ADMINS:
            return self.get_response(ev)
        else:
            return u"Sorry you need to be admin to issue this command."


    def get_target(self, ev):
        if self.TARGET == "target":
            # if ev.type == "privmsgs" # TODO : handle private messages
            target = ev.target
        elif self.TARGET == "source":
            target = ev.source.nick
        else:
            self.bot.error_logger("Invalid command target %s for command %s !" % (self.TARGET, self.__name__))
            target = None
        return target


    def handle(self, ev):
        options = self._parse_options(ev)
        # self.bot.base_logger('command issued by %s : %s' % (ev.source, self.line))
        
        self.source = ev.source
     
        if target:
            self.bot.send(target, self.process(ev))


class BaseAuthCommand(BaseCommand):
    """
    This is like a regular command but,
    it checks the auth_module to get the auth of the user issuing the command,
    as this can take some time, the result is asynchronous
    """

    def callback(self, *args):
        self.bot.send(args[0], self.get_response(*args))

        
    def get_user_from_line(self, ev):
        """
        override this if you don't want to check the auth
        from the user who issued the command, 
        but from one of the command options
        """
        return ev.source.nick


    def handle(self, ev):
        options = self._parse_options(ev)
        self.auth_module.get_user(self.get_user_from_line(ev), self.callback, options)


class BaseTrigger(object):
    """
    Triggers are any messages not aimed at the bot,
    that could make him do something
    """

    REGEXP = r''

    def handle(self, ev):
        pass


class BaseBotModule(object):
    """
    Abstract class for any irc bot module
    """
    COMMANDS = {}
    TRIGGERS = []


class BaseAuthModule(object):
    """
    This class is used to get the real user name of a user
    it can be overrided with settings.AUTH_MODULE, to use any irc auth method

    an auth module is a bit of a specific module, it shouldn't lie in settings.MODULES
    but in settings.AUTH_MODULE, and shouldn't implement the regular modules hooks
    the get_user method could be asynchronous in some case, and so will always return None
    """
    def get_user(self, user, cb, args=[]):
        cb(*args)
        return None


class BaseIrcBot(SingleServerIRCBot):
    COMMAND_PREFIX = '!'
    MAX_MSG_LEN = getattr(settings, 'MAX_MSG_LEN', 450) #its 512 but we need some space for the command arguments, might depend on irc server
    TIME_BETWEEN_MSGS = getattr(settings, 'TIME_BETWEEN_MSGS', 1) #in seconds


    def __init__(self):
        super(BaseIrcBot, self).__init__([(settings.SERVER,),], settings.NICK, settings.REALNAME)
        self.last_sent = None

        self._init_loggers()

        self.auth_module = getattr(settings, 'AUTH_MODULE', BaseAuthModule)
        self.modules = {}
        self._init_modules()

        self.ircobj.add_global_handler("all_events", self.global_handler)


    def _init_modules(self):
        self.commands = {}
        for module in settings.MODULES:
            mod = module(self)
            if not isinstance(mod, BaseBotModule):
                raise ImproperlyConfigured("%s is not a BaseBotModule subclass ! it should be." % module)
            for command in module.COMMANDS:
                self.commands.update({command.NAME : command(self)})


    def send(self, target, msg):
        # TODO : we should probably have a thread with a queue to send these messages
        if not self.last_sent:
            self.last_sent = datetime.datetime.now()
            
        if (datetime.datetime.now()- self.last_sent).seconds < self.TIME_BETWEEN_MSGS:
            time.sleep(self.TIME_BETWEEN_MSGS)

        while len(msg) > self.MAX_MSG_LEN:
            ind = msg.rfind(" ", 0, self.MAX_MSG_LEN)
            buff = msg[ind:]
            self.last_sent = datetime.datetime.now()
            self.server.privmsg(target, msg[:ind])
            msg = buff
            time.sleep(self.TIME_BETWEEN_MSGS) # so we don't get disco for excess flood
        
        self.last_sent = datetime.datetime.now()
        self.server.privmsg(target, msg)   


    def get_needs_to_be_admin(self):
        return "Sorry, you can't do that by yourself, ask %s" % (" or ".join(settings.ADMINS))


    def _init_loggers(self):
        msg_formatter = logging.Formatter('%(asctime)s - %(message)s')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        if not os.path.isdir(settings.LOG_DIR):
            os.mkdir(os.path.join(os.path.dirname(__file__),settings.LOG_DIR))

        msg_logger = logging.getLogger('msgslog')
        msg_logger.setLevel(logging.DEBUG)
        handler = logging.handlers.TimedRotatingFileHandler(os.path.join(settings.LOG_DIR, 'daily.log'), when='midnight')
        handler.setFormatter(msg_formatter)
        msg_logger.addHandler(handler)
        self.msg_logger = msg_logger

        error_logger = logging.getLogger('errorlog')
        error_logger.setLevel(logging.WARNING)
        handler = logging.FileHandler(os.path.join(settings.LOG_DIR, 'error.log'))
        handler.setFormatter(formatter)
        error_logger.addHandler(handler)
        self.error_logger = error_logger


    def on_welcome(self, serv, ev):
        self.server = serv
        # changing the default Buffer to ensure no encoding error
        self.connection.buffer = CompliantDecodingLineBuffer()

        for chan in settings.START_CHANNELS:
            self.connection.join(chan)


    def log_msg(self, ev):
        if ev.target and ev.source:
            self.msg_logger.info('%s - %s: %s' % (ev.target, ev.source.nick, ev.arguments[0]))        


    # we dispatch all the handlers to the modules in case they have something to do
    def _dispatcher(self, serv, ev):
        for module in self.modules:
            m = "on_" + ev.type
            if hasattr(module, m):
                getattr(module, m)(serv, ev)

    def global_handler(self, serv, ev):
        try:
            response = None
            if ev.type in ["pubmsg", "privnotice", "privmsgs"]:
                self.log_msg(ev)
                
                msg = ev.arguments[0]
                if msg[0] == self.COMMAND_PREFIX:
                    try:
                        cmd = msg[1:].split(' ')[0]
                        self.commands[cmd].handle(ev)
                        
                        # hdl = getattr(self, self.COMMANDS[cmd])
                        # if self.check_admin(hdl, ev):
                        #     target, response = ev.target, self.get_needs_to_be_admin()
                        # else:
                        #     try:
                        #         target, response = hdl(ev, *arguments)
                        #     except NotImplementedError, e:
                        #         target, response = ev.target, u"Not Implemented yet."

                    except KeyError, e:
                        self.error_logger.warning('Invalid command : %s by %s' % (e, ev.source))
                else:
                    for regexp in self.REGEXPS.keys():
                        m = re.match(regexp, msg)
                        if m:
                            target, response = getattr(self, self.REGEXPS[regexp])(m, ev)
                            # break # should we ?
                if response:
                    self.send(target, response)
            else:
                # TODO: handle privmsgs
                pass
        except IndexError:
            pass


