#! -*- coding: utf-8 -*-
import logging
import os
import re
import sys
import signal
import time
from threading import Thread
from Queue import Queue
import datetime
from logging import handlers

from irc.client import DecodingLineBuffer
from irc.bot import SingleServerIRCBot

import settings


class CompliantDecodingLineBuffer(DecodingLineBuffer):
    def lines(self):
        lines = [l for l in super(DecodingLineBuffer, self).lines()]

        try:
            # Note: skipping parent in super to go up one class in the branch (to avoid trying to decode with 'replace')
            return iter([line.decode('utf-8') for line in lines])
        except UnicodeDecodeError:
            return iter([line.decode('latin-1') for line in lines])
        # fallback
        return iter([line.decode('utf-8', 'replace') for line in lines])


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

    # Only authed users can use this command
    REQUIRE_AUTH = False

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

        self.split_options(ev.arguments)
        self.parse_options()  # the exception will be catched by the main loop

        self.bot.error_logger.info('Command issued by %s : %s' % (ev.source, self.NAME))

    def split_options(self, arguments):
        # handling named arguments (foo=bar)
        reg = r'(?P<opt>\w+)=(?P<val>\w+)'
        self.args = dict(re.findall(reg, arguments[0]))
        cmd = re.sub(reg, u'', arguments[0])  # stripping out named arguments

        # context arguments (called options)
        try:
            self.options = cmd.strip().split(" ")[1:]
        except IndexError:
            self.options = []

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


class BaseBotPlugin(object):
    """
    Abstract class for any irc bot plugin
    """
    COMMANDS = {}
    TRIGGERS = []

    def __init__(self, bot):
        self.bot = bot


class HelpCommand(BaseCommand):
    NAME = u'help'
    HELP = u"""Display this help."""

    def get_response(self):
        if self.options:
            cmd = self.options[0]
            try:
                msg = self.bot.commands[cmd].HELP
            except KeyError:
                msg = u"No such command."
        else:
            msg = u"Here are the currently implemented commands : %s" % ', '.join(['!%s' % k for k in self.bot.commands.keys() if not getattr(self.bot.commands[k], 'HIDDEN', False)])

        return msg


class VersionCommand(BaseCommand):
    NAME = u'version'
    HELP = u"Display the bot version."

    def get_response(self):
        return u"version: %s" % self.bot.VERSION


class PingCommand(BaseCommand):
    NAME = u'ping'
    HELP = u'peng'

    def get_response(self):
        return u'pong'


class RestartCommand(BaseCommand):
    NAME = u"restart"
    HELP = u"restart the bot."
    REQUIRE_ADMIN = True
    IS_HIDDEN = True

    def process(self):
        # TODO: use boot.sh
        self.bot.error_logger.info("Restarting the bot...")
        executable = sys.executable
        args = sys.argv[:]
        args.insert(0, sys.executable)
        os.execvp(executable, args)


class ReconnectCommand(BaseCommand):
    NAME = u"reconnect"
    HELP = u"reconnect"
    REQUIRE_ADMIN = True
    IS_HIDDEN = True

    def process(self):
        self.bot.error_logger.info("Disconnecting because you asked so ...")
        self.bot.disconnect()
        self.bot._connect()


class IssueCommand(BaseCommand):
    NAME = u"command"
    ALIASES = [u"cmd",]
    IS_HIDDEN = True
    REQUIRE_ADMIN = True

    def parse_options(self):
        self.cmd_line = ' '.join(self.options)
        if not len(self.cmd_line):
            raise BadCommandLineException

    def process(self):
        self.bot.connection.send_raw(self.cmd_line)


class MsgCommand(BaseCommand):
    NAME = u"msg"
    REQUIRE_ADMIN = True

    def parse_options(self):
        try:
            self._target = self.options[0]
            self.msg = ' '.join(self.options[1:])
        except IndexError, e:
            raise BadCommandLineException

    def get_response(self):
        self.bot.send(self._target, self.msg)
        return u''

class QuitCommand(BaseCommand):
    NAME = u"quit"
    REQUIRE_ADMIN = True
    IS_HIDDEN = True

    def get_response(self):
        self.bot.disconnect()
        sys.exit(0)


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

    # because there is no way to know how the server implement the flood protection
    # and thus we can't make a more reliable rule to avoid it
    # the number of commands before we stop answering (if set to 2, the 3rd command will remain unanswered)
    FLOOD_PROTECTION_MAX_COMMANDS = getattr(settings, 'FLOOD_PROTECTION_MAX_COMMANDS', 2)
    # the number of seconds before we reset the command timer
    FLOOD_PROTECTION_TIMER = getattr(settings, 'FLOOD_PROTECTION_TIMER', 4)
    # the period of time in which the bot is allowed to send MAX_MSG_LEN bytes
    FLOOD_TIMER = getattr(settings, 'FLOOD_TIMER', 4)

    LEAVE_MESSAGE = getattr(settings, 'LEAVE_MESSAGE', 'Bye.')
    RECONNECTION_INTERVAL = getattr(settings, 'RECONNECTION_INTERVAL', 30)

    def __init__(self):
        self._init_loggers()
        super(BaseIrcBot, self).__init__([(settings.SERVER,),], settings.NICK, settings.REALNAME, reconnection_interval=self.RECONNECTION_INTERVAL)

        # used by simple implementation
        # self.last_sent = datetime.datetime.now()
        self.last_sent = []

        self.msg_queue = Queue()  # message queue
        self._start_msg_consumer()

        # the map to remember the last user's command time
        self.command_timer_map = {}

        self.plugins = []
        self.commands = {}
        self.triggers = {}

        self._init_plugins()
        self.ircobj.add_global_handler("all_events", self.global_handler)

        # catch to disconnect gracefully..
        signal.signal(signal.SIGINT, self.quit)
        #signal.signal(signal.SIGKILL, self.quit)
        #signal.signal(signal.SIGTERM, self.quit)
        signal.signal(signal.SIGQUIT, self.quit)

    def quit(self, signal=None, frame=None):
        self.error_logger.warning("Received a SIGINT|SIGKILL|SIGTERM (%s) signal, trying to quit gracefully" % str(signal))
        self.disconnect()
        sys.exit(0)

    def _load_plugin(self, plugin, append_plugin_dir=True):
        self.error_logger.info('Loading %s.', plugin)

        try:
            if append_plugin_dir:
                mod = __import__(getattr(settings, 'PLUGINS_DIR', 'plugins') + '.' + '.'.join(plugin.split('.')[:-1]), globals(), locals(), [plugin.split('.')[-1]])
            else:
                mod = __import__('.'.join(plugin.split('.')[:-1]), globals(), locals(), [plugin.split('.')[-1]])
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

        self.plugins.append(plugin_instance)
        return plugin_instance

    def disconnect(self, message=None):
        super(BaseIrcBot, self).disconnect(message or self.LEAVE_MESSAGE)

    def unload_plugin(self, plugin):
        self.error_logger.info('Unloading %s.', plugin)

        if plugin in self.plugins:  # or it could be the auth_plugin
            self.plugins.remove(plugin)
        for command_class in plugin.COMMANDS:
            for name, command in self.commands.iteritems():
                if command == command_class:
                    del self.commands[name]
        for trigger_class in plugin.TRIGGERS:
            for name, trigger in self.triggers.iteritems():
                if trigger == trigger_class:
                    del self.triggers[name]

    def _init_plugins(self):
        for command_class in self.COMMANDS:
            self.commands.update({command_class.NAME : command_class})
            for alias in command_class.ALIASES:
                self.commands.update({alias : command_class})
            command_class.plugin = self
        for trigger_class in self.TRIGGERS:
            self.triggers.update({trigger_class.REGEXP : trigger_class})
            trigger_class.plugin = self

        if hasattr(settings, 'AUTH_PLUGIN'):
            self.auth_plugin = self._load_plugin(getattr(settings, 'AUTH_PLUGIN', 'auth.BaseAuthPlugin'))
        else:
            self.auth_plugin = self._load_plugin('auth.BaseAuthPlugin', append_plugin_dir=False)

        for plugin in getattr(settings, 'PLUGINS', []):
            self._load_plugin(plugin)

        self.error_logger.info("Done loading plugins.")

    def _start_msg_consumer(self):
        t = Thread(target=self._msg_consumer)
        t.daemon = True
        t.start()

    ########## PARALLEL IMPLEMENTATION - TESTING ANTI FLOOD METHODS ##########
    # the issue here is double:
    # firstly, the rfc only gives advices about how to deal with flood, so servers are free to have their own
    # implementations of flood protections
    # secondly, there is no way to tell at what speed the server really process data, or the state of the server's socket buffer
    # and thus if the command will overflow
    # (overflow = the read buffer is already full and we try to send more data)

    def _check_flood_danger2(self):
        """
        very basic implementation
        """
        return (datetime.datetime.now() - self.last_sent).seconds < self.TIME_BETWEEN_MSGS

    def _check_flood_danger(self, msg):
        """
        We try to make a wild guess on the server process time
        so we can chain a lot of small commands, but larger responses trigger the timer
        """
        now = datetime.datetime.now()

        def _sum_bytes():
            return sum([s['bytes'] for s in self.last_sent if (now - s['time']).seconds <= self.FLOOD_TIMER])

        def _clean():
            for s in self.last_sent:
                if (now - s['time']).seconds > self.FLOOD_TIMER:
                    self.last_sent.remove(s)

        sb = _sum_bytes() + len(msg.text)
        _clean()
        return (sb > self.MAX_MSG_LEN)

    #########################################################################

    def _send(self, msg):
        while self._check_flood_danger(msg):
            time.sleep(self.TIME_BETWEEN_MSGS)
        self.last_sent.append({'time':datetime.datetime.now(), 'bytes': len(msg.text)})
        self.msg_logger.info(u'>>> %s - %s', msg.target, msg.text)
        self.server.privmsg(msg.target, msg.text)

    def _msg_consumer(self):
        """
        Called from a specific Thread because it is blocking
        """
        while True:
            msg = self.msg_queue.get()
            while len(msg.text) > self.MAX_MSG_LEN:
                ind = msg.text.rfind(" ", 0, self.MAX_MSG_LEN)
                if ind == -1:
                    ind = self.MAX_MSG_LEN
                buff = msg.text[ind:]
                msg.text = msg.text[:ind]
                self._send(msg)
                msg.text = buff
            self._send(msg)

    def send(self, target, msg):
        if not type(msg) in (tuple, list, set):  # we don't use collections.Iterable because a string is an iterable
            msg = msg.split("\n")
        else:
            # ok.
            msg = [i for sub in [s.split("\n") for s in msg] for i in sub]

        for m in msg:
            self.msg_queue.put(Message(target, m))

    def get_needs_to_be_admin(self):
        return "Sorry, you can't do that by yourself, ask %s" % (" or ".join(settings.ADMINS))

    def _init_loggers(self):
        msg_formatter = logging.Formatter('%(asctime)s - %(message)s')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        logdir = os.path.join(os.path.dirname(__file__), getattr(settings, 'LOG_DIR', 'logs'), str(datetime.datetime.today().year), str(datetime.datetime.today().month))
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
        handler = handlers.RotatingFileHandler(os.path.join(settings.LOG_DIR, 'error.log'), maxBytes=1024 * 100, backupCount=5)  # 100 kB
        handler.setFormatter(formatter)
        error_logger.addHandler(handler)
        self.error_logger = error_logger

    def on_welcome(self, serv, ev):
        self.server = serv
        # changing the default Buffer to ensure no encoding error
        self.connection.buffer = CompliantDecodingLineBuffer()

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
        if ev.type not in ['all_raw_messages', 'motd', 'ping']:
            try:
                source = ev.source.nick
            except AttributeError:
                source = ev.source
            self.msg_logger.info('%s - %s - %s: %s' % (ev.type, ev.target, source, ' | '.join(ev.arguments)))

    # we dispatch all the handlers to the plugins in case they have something to do
    def _dispatcher(self, serv, ev):
        super(BaseIrcBot, self)._dispatcher(serv, ev)

        for plugin in self.plugins:
            m = "on_" + ev.type
            if hasattr(plugin, m):
                getattr(plugin, m)(serv, ev)

    def check_command_timer(self, user):
        """
        ensure that an user is not tring to excess flood the bot.
        we don't use the auth_plugin here, no need

        for now, we consider that the user tries to flood the bot if he issue more than 2 commands
        in less than 2 seconds

        note that it doesn't protect against the flood, it only make sure that one user only can not
        make the bot be kicked for excess flood.
        """
        now = datetime.datetime.now()
        if user not in self.command_timer_map:
            self.command_timer_map[user] = {'counter':0, 'time':now}
        ctm = self.command_timer_map[user]

        if (now - ctm['time']).seconds <= self.FLOOD_PROTECTION_TIMER:
            ctm['counter'] = ctm['counter'] + 1
            if ctm['counter'] > self.FLOOD_PROTECTION_MAX_COMMANDS:
                return False
        else:
            # the last command was a long time ago : reset
            ctm = {'counter':1, 'time':now}

        return True

    def global_handler(self, serv, ev):
        self.log_msg(ev)
        if ev.type in ["pubmsg", "privnotice", "privmsg"]:

            msg = ev.arguments[0]
            if msg[0] == self.COMMAND_PREFIX:
                try:
                    cmdcls = self.commands[msg[1:].split(' ')[0]]
                    try:
                        cmd = cmdcls(self, ev)
                    except BadCommandLineException, e:
                        self.send(ev.target, u"Bad command line - %s" % e.message or cmdcls.HELP)
                    else:
                        if self.check_command_timer(ev.source.nick):
                            cmd.handle()
                        else:
                            self.error_logger.warning(u'Flood attempt by %s.' % ev.source)
                            #self.send(ev.target, u'Nop.')
                            self.server.privmsg(ev.target, u'Nop.')
                except KeyError, e:
                    self.error_logger.warning('Invalid command : %s by %s' % (e, ev.source))
                except NotImplementedError, e:
                    self.send(ev.target, u"Not implemented. Sorry !")
            else:
                for regexp, trigger_class in self.triggers.items():
                    m = re.match(regexp, msg)
                    if m:
                        trigger_class(self, m, ev).handle()
