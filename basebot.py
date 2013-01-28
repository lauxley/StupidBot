import logging
import os
import re
from threading import Thread
from Queue import Queue
import datetime, time
from logging import handlers

from irc.client import DecodingLineBuffer
from irc.bot import SingleServerIRCBot

import settings

class CompliantDecodingLineBuffer(DecodingLineBuffer):
    errors = 'replace'


class ImproperlyConfigured(Exception):
    pass


class BadCommandLineException(Exception):
    pass


class BaseCommand(object):
    """
    Abstract class for any command
    commands are specific messages send specifically for the bot to do something
    on contrary, triggers are messages not specifically aimed at the bot, that it catches.

    An instance of command is created every time a user issue it.
    """
    # this is the word used to issue the command
    NAME = u""

    # a list of additional words that can be used to issue the command
    ALIASES = []

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
        try:
            self.options = self.ev.arguments[0].split(" ")[1:]
        except IndexError, e:
            self.options = []
        # try:
        self.parse_options() # the exception will be catched by the main loop
        # except BadCommandLineException, e:


        self.bot.error_logger.info('Command issued by %s : %s' % (ev.source, self.NAME))

    def parse_options(self):
        """
        Override this if you have to check for mandatory arguments and stuff
        """
        pass

    def get_response(self):
        """
        Most of the time this will be the only method to implement
        It should return a string containing the response of the bot to the issued command
        """
        return u""
    
    def process(self, *args, **kwargs):
        msg = self.get_response()
        self.bot.send(self.get_target(), msg)

    def get_target(self):
        if self.TARGET == "target":    
            if self.ev.type == "privmsg":
                target = self.ev.source.nick
            else:
                target = self.ev.target
        elif self.TARGET == "source":
            target = self.ev.source.nick
        else:
            self.bot.error_logger.error("Invalid command target %s for command %s !" % (self.TARGET, self.__name__))
            target = None
        return target        

    def get_needs_to_be_admin(self):
        return u"Sorry you need to be admin to issue this command."

    def _is_admin(self, user):
        return user in settings.ADMINS

    def check_admin(self, user, *args):        
        if self._is_admin(self.bot.auth_plugin.get_username(user)):
            self.process(*args)
        else:
            self.bot.send(self.ev.target, self.get_needs_to_be_admin())
        
    def handle(self):
        if self.REQUIRE_ADMIN:
            self.bot.auth_plugin.get_user(self.ev.source.nick, self.check_admin)
        else:
            self.process()


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


class BaseTrigger(object):
    """
    Triggers are any messages not aimed at the bot,
    that could make him do something
    """

    # every message catched by the bot is checked against every triggers regexp,
    # if one match, the corresponding handle method is called.
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
    

class BaseBotPlugin(object):
    """
    Abstract class for any irc bot plugin
    """
    COMMANDS = {}
    TRIGGERS = []

    def __init__(self, bot):
        self.bot = bot


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


class Message():
    """
    only a small helper to help with the msg queue
    """
    def __init__(self, target, text):
        self.target = target
        self.text = text


class BaseIrcBot(SingleServerIRCBot):
    COMMAND_PREFIX = '!'
    
    # its 512 but we need some space for the command arguments, might depend on irc server
    MAX_MSG_LEN = getattr(settings, 'MAX_MSG_LEN', 450) 

    # The time in seconds that the bot will wait before sending 2 consecutive messages
    TIME_BETWEEN_MSGS = getattr(settings, 'TIME_BETWEEN_MSGS', 1) 

    def __init__(self):
        super(BaseIrcBot, self).__init__([(settings.SERVER,),], settings.NICK, settings.REALNAME)

        self.last_sent = None
        self.msg_queue = Queue() # message queue
        self._start_msg_consumer()

        self._init_loggers()

        self.plugins = []
        self.commands = {}
        self.triggers = {}

        self.ircobj.add_global_handler("all_events", self.global_handler)

    def _load_plugin(self, plugin):
        self.error_logger.info('Loading %s.', plugin)

        try:
            mod = __import__(getattr(settings, 'PLUGINS_DIR', '')+'.'+'.'.join(plugin.split('.')[:-1]), globals(), locals(), [plugin.split('.')[-1]])
        except ImportError, e:
            self.error_logger.error("Can not import Plugin %s : %s" % (plugin, e))
            return 

        plugin_instance = getattr(mod, plugin.split('.')[-1])(self)

        if not isinstance(plugin_instance, BaseBotPlugin):
            raise ImproperlyConfigured("%s is not a BaseBotPlugin subclass ! it should be." % plugin)

        for command_class in plugin_instance.COMMANDS:
            self.commands.update({command_class.NAME : command_class})
            for alias in command_class.ALIASES:
                self.commands.update({alias : command_class})
            command_class.plugin = plugin_instance
        for trigger_class in plugin_instance.TRIGGERS:
            self.triggers.update({trigger_class.REGEXP : trigger_class})
            trigger_class.plugin = plugin_instance
            
        return plugin_instance

    def _unload_plugin(self, plugin):
        self.error_logger.info('Unloading %s.', plugin)
        
        self.plugins.remove(plugins)
        for command_class in plugin.COMMANDS:
            for name, command in self.commands.iteritems():
                if command == command_class:
                    del self.commands[name]

    def _init_plugins(self):
        for command_class in self.COMMANDS:
            self.commands.update({command_class.NAME : command_class})
            for alias in command_class.ALIASES:
                self.commands.update({alias : command_class})
            command_class.plugin = self
        for trigger_class in self.TRIGGERS:
            self.triggers.update({trigger_class.REGEXP : trigger_class})
            trigger_class.plugin = self

        auth_plugin = getattr(settings, 'AUTH_PLUGIN', 'basebot.BaseAuthPlugin')
        self.auth_plugin = self._load_plugin(auth_plugin)
        
        for plugin in getattr(settings, 'PLUGINS', []):
            self.plugins.append(self._load_plugin(plugin))
        self.error_logger.info("Done loading plugins.")


    def _start_msg_consumer(self):
        t = Thread(target=self._msg_consumer)
        t.daemon = True
        t.start()

    def _msg_consumer(self):
        # TODO : if we spam a lot of commands, we still get an excess flood :(
        # we should add a trigger so at least we recover nicely for it.

        while True:
            msg = self.msg_queue.get()

            if not self.last_sent:
                self.last_sent = datetime.datetime.now()
            
            if (datetime.datetime.now()- self.last_sent).seconds < self.TIME_BETWEEN_MSGS:
                time.sleep(self.TIME_BETWEEN_MSGS)

            while len(msg.text) > self.MAX_MSG_LEN:
                # TODO : break if there is no space in the msg
                ind = msg.text.rfind(" ", 0, self.MAX_MSG_LEN)
                buff = msg.text[ind:]
                self.last_sent = datetime.datetime.now()
                self.msg_logger.info('%s - %s: %s' % (msg.target, settings.NICK, msg.text))
                self.server.privmsg(msg.target, msg.text[:ind])
                msg.text = buff
                time.sleep(self.TIME_BETWEEN_MSGS) # so we don't get disco for excess flood
            
            self.last_sent = datetime.datetime.now()
            self.msg_logger.info('%s - %s: %s' % (msg.target, settings.NICK, msg.text))
            self.server.privmsg(msg.target, msg.text)

    def send(self, target, msg):
        if type(msg) in [list, set]:
            for m in msg:
                self.msg_queue.put(Message(target, m))
        else:
            self.msg_queue.put(Message(target, msg))

    def get_needs_to_be_admin(self):
        return "Sorry, you can't do that by yourself, ask %s" % (" or ".join(settings.ADMINS))

    def _init_loggers(self):
        msg_formatter = logging.Formatter('%(asctime)s - %(message)s')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        logdir = os.path.join(os.path.dirname(__file__), settings.LOG_DIR, str(datetime.datetime.today().year), str(datetime.datetime.today().month))
        if not os.path.isdir(logdir):
            os.makedirs(logdir)

        msg_logger = logging.getLogger('msgslog')
        msg_logger.setLevel(logging.DEBUG)
        handler = handlers.TimedRotatingFileHandler(os.path.join(settings.LOG_DIR, str(datetime.datetime.today().year), str(datetime.datetime.today().month), 'daily.log'), when='midnight')
        handler.setFormatter(msg_formatter)
        msg_logger.addHandler(handler)
        self.msg_logger = msg_logger

        error_logger = logging.getLogger('errorlog')
        error_logger.setLevel(logging.INFO)
        handler = handlers.RotatingFileHandler(os.path.join(settings.LOG_DIR, 'error.log'), maxBytes=1024*100) # 100 kB
        handler.setFormatter(formatter)
        error_logger.addHandler(handler)
        self.error_logger = error_logger

    def on_welcome(self, serv, ev):
        self.server = serv
        # changing the default Buffer to ensure no encoding error
        self.connection.buffer = CompliantDecodingLineBuffer()

        self._init_plugins()

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

    # we dispatch all the handlers to the plugins in case they have something to do
    def _dispatcher(self, serv, ev):
        super(BaseIrcBot, self)._dispatcher(serv, ev)
        for plugin in self.plugins:
            m = "on_" + ev.type
            if hasattr(plugin, m):
                getattr(plugin, m)(serv, ev)

    def global_handler(self, serv, ev):
        if ev.type in ["pubmsg", "privnotice", "privmsg"]:
            self.log_msg(ev)
            
            msg = ev.arguments[0]
            if msg[0] == self.COMMAND_PREFIX:
                try:
                    cmdcls = self.commands[msg[1:].split(' ')[0]]
                    try:
                        cmd = cmdcls(self, ev)
                    except BadCommandLineException, e:
                        self.send(ev.target, u"Bad command line - %s" % cmdcls.HELP)
                    else:
                        cmd.handle()
                except KeyError, e:
                    self.error_logger.warning('Invalid command : %s by %s' % (e, ev.source))
                except NotImplementedError, e:
                    self.send(ev.target, u"Not implemented. Sorry !")
            else:
                for regexp, trigger_class in self.triggers.items():
                    m = re.match(regexp, msg)
                    if m:
                        trigger_class(self, m, ev).handle()
