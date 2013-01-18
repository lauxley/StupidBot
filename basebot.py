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
    #ALIASES = [] # TODO

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


    def __init__(self, bot, ev):
        self.bot = bot
        self.ev = ev
        self.options = self._parse_options()
        self.bot.error_logger.info('Command issued by %s : %s' % (ev.source, self.NAME))


    def _parse_options(self):
        return self.ev.arguments[0].split(" ")[1:]


    def get_response(self):
        """
        most of the time this will be the only method to implement
        """
        return u""

    
    def process(self, *args, **kwargs):
        msg = self.get_response()
        self.bot.send(self.get_target(), msg)


    def get_target(self):
        if self.TARGET == "target":
            # if ev.type == "privmsgs" # TODO : handle private messages
            target = self.ev.target
        elif self.TARGET == "source":
            target = self.ev.source.nick
        else:
            self.bot.error_logger.error("Invalid command target %s for command %s !" % (self.TARGET, self.__name__))
            target = None
        return target        


    def get_needs_to_be_admin(self):
        return u"Sorry you need to be admin to issue this command."


    def check_admin(self, user):        
        if user in settings.ADMINS:
            self.process()
        else:
            self.bot.send(self.ev.target, self.get_needs_to_be_admin())
        

    def handle(self):
        if self.REQUIRE_ADMIN:
            self.bot.auth_module.get_user(self.ev.source.nick, self.check_admin)
        else:
            self.process()

class BaseAuthCommand(BaseCommand):
    """
    This is like a regular command but,
    it checks the auth_module to get the auth of the user issuing the command,
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
        if user in settings.ADMINS:
            self.bot.auth_module.get_user(self.get_user_from_line(), self.process)
        else:
            self.bot.send(self.ev.target, self.get_needs_to_be_admin())


    def handle(self):
        if self.REQUIRE_ADMIN:
            self.bot.auth_module.get_user(self.ev.source.nick, self.check_admin)
        else:
            self.bot.auth_module.get_user(self.get_user_from_line(), self.process)


    def process(self, user, *args, **kwargs):
        self.user = user
        super(BaseAuthCommand, self).process(*args, **kwargs)


class BaseTrigger(object):
    """
    Triggers are any messages not aimed at the bot,
    that could make him do something
    """

    REGEXP = r''

    def __init__(self, bot, match, ev):
        self.bot = bot
        self.match = match
        self.ev = ev
        self.bot.error_logger.info("Trigger matched %s for -%s" % (self.REGEXP, ev.arguments[0]))

    def handle(self):
        # this method is just here to be homogenous with BaseCommand
        self.process()

    def process(self):
        pass

class BaseBotModule(object):
    """
    Abstract class for any irc bot module
    """
    COMMANDS = {}
    TRIGGERS = []

    def __init__(self, bot):
        self.bot = bot

class BaseAuthModule(BaseBotModule):
    """
    This class is used to get the real user name of a user
    it can be overrided with settings.AUTH_MODULE, to use any irc auth method

    an auth module is a bit of a specific module,
    it shouldn't lie in settings.MODULES but in settings.AUTH_MODULE
    the get_user method could be asynchronous in some case, and so will always return None
    """
    def get_user(self, user, cb, *args, **kwargs):
        """
        This method will be called anytime we need to get a real user from a user name
        it is asynchronous, and will call command.process() passing user as an argument
        once it knows his real name
        """
        cb(user=user, isauth=False, *args, **kwargs)
        return None


class BaseIrcBot(SingleServerIRCBot):
    COMMAND_PREFIX = '!'
    MAX_MSG_LEN = getattr(settings, 'MAX_MSG_LEN', 450) #its 512 but we need some space for the command arguments, might depend on irc server
    TIME_BETWEEN_MSGS = getattr(settings, 'TIME_BETWEEN_MSGS', 1) #in seconds


    def __init__(self):
        super(BaseIrcBot, self).__init__([(settings.SERVER,),], settings.NICK, settings.REALNAME)
        self.last_sent = None

        self._init_loggers()

        self.modules = []
        self.commands = {}
        self.triggers = {}

        self.ircobj.add_global_handler("all_events", self.global_handler)

    def _load_module(self, module):
        self.error_logger.info('Loading %s', module)

        try:
            mod = __import__('.'.join(module.split('.')[:-1]), globals(), locals(), [module.split('.')[-1]])
        except ImportError, e:
            self.error_logger.error("Can not import Module %s : %s" % (module, e))
            return 

        module_instance = getattr(mod, module.split('.')[-1])(self)

        if not isinstance(module_instance, BaseBotModule):
            raise ImproperlyConfigured("%s is not a BaseBotModule subclass ! it should be." % module)

        for command_class in module_instance.COMMANDS:
            self.commands.update({command_class.NAME : command_class})
        for trigger_class in module_instance.TRIGGERS:
            self.triggers.update({trigger_class.REGEXP : trigger_class})
            
        return module_instance

    def _init_modules(self):
        for command_class in self.COMMANDS:
            self.commands.update({command_class.NAME : command_class})
        for trigger_class in self.TRIGGERS:
            self.triggers.update({trigger_class.REGEXP : trigger_class})

        auth_module = getattr(settings, 'AUTH_MODULE', 'basebot.BaseAuthModule')
        self.auth_module = self._load_module(auth_module)
        
        for module in getattr(settings, 'MODULES', []):
            self.modules.append(self._load_module(module))


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
        error_logger.setLevel(logging.INFO)
        handler = logging.FileHandler(os.path.join(settings.LOG_DIR, 'error.log'))
        handler.setFormatter(formatter)
        error_logger.addHandler(handler)
        self.error_logger = error_logger


    def on_welcome(self, serv, ev):
        self.server = serv
        # changing the default Buffer to ensure no encoding error
        self.connection.buffer = CompliantDecodingLineBuffer()

        self._init_modules()

        for chan in settings.START_CHANNELS:
            self.connection.join(chan)

    
    def _on_join(self, serv, ev):
        super(BaseIrcBot, self)._on_join(serv, ev)
        self.msg_logger.info(u"%s joined the channel %s." % (ev.source.nick, ev.target))

    def _on_nick(self, serv, ev):
        super(BaseIrcBot, self)._on_nick(serv, ev)
        self.msg_logger.info(u"%s is now known as %s." % (ev.source.nick, ev.target))

    def _on_part(self, serv, ev):
        super(BaseIrcBot, self)._on_part(serv, ev)
        self.msg_logger.info(u"%s left the channel %s." % (ev.source.nick, ev.target))

    def _on_kick(self, serv, ev):
        super(BaseIrcBot, self)._on_kick(serv, ev)
        self.msg_logger.info(u"%s was kicked from %s." % (ev.source.nick, ev.target))

    def _on_quit(self, serv, ev):
        super(BaseIrcBot, self)._on_quit(serv, ev)
        self.msg_logger.info(u"%s left." % (ev.source.nick))

    def log_msg(self, ev):
        if ev.target and ev.source:
            self.msg_logger.info('%s - %s: %s' % (ev.target, ev.source.nick, ev.arguments[0]))        


    # we dispatch all the handlers to the modules in case they have something to do
    def _dispatcher(self, serv, ev):
        super(BaseIrcBot, self)._dispatcher(serv, ev)
        for module in self.modules:
            m = "on_" + ev.type
            if hasattr(module, m):
                getattr(module, m)(serv, ev)

    def global_handler(self, serv, ev):
        # TODO: handle privmsgs
        if ev.type in ["pubmsg", "privnotice", "privmsgs"]:
            self.log_msg(ev)
            
            msg = ev.arguments[0]
            if msg[0] == self.COMMAND_PREFIX:
                try:
                    cmd = msg[1:].split(' ')[0]
                    self.commands[cmd](self, ev).handle()
                except KeyError, e:
                    self.error_logger.warning('Invalid command : %s by %s' % (e, ev.source))
                except NotImplementedError, e:
                    self.send(ev.target, u"Not implemented. Sorry !")
            else:
                
                for regexp, trigger_class in self.triggers.items():
                    m = re.match(regexp, msg)
                    if m:
                        trigger_class(self, m, ev).handle()



