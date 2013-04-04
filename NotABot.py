#! -*- coding: utf-8 -*-
import datetime
import argparse

from basebot import BaseIrcBot, HelpCommand, VersionCommand, PingCommand, ReconnectCommand, IssueCommand  # RestartCommand,
from auth import BaseAuthTrigger

import settings


class TrajRandTrigger(BaseAuthTrigger):
    REGEXP = r'(?P<username>[^ ]+)? ?obtient un (?P<roll>\d{1,3}) \(1-100\)'

    def handle(self):
        self.bot.auth_plugin.get_user(self.ev.source.nick, self.handle2)

    def handle2(self, source):
        if source.auth == '`Xrs`Jeeju`':
            user = self.get_user_from_line()
            if not user:  # damn Traj, need a special rule just for him
                user = 'Traj'
            self.bot.auth_plugin.get_user(user, self.process)

    def process(self, user, *args):
        roll = self.match.group('roll')
        user = self.bot.auth_plugin.get_username(user)
        self.bot.rand_db.add_entry(datetime.datetime.now(), user, roll, self.ev.target)


class StupidIrcBot(BaseIrcBot):
    VERSION = u'0.9.6'

    COMMANDS = [HelpCommand, VersionCommand, PingCommand, ReconnectCommand, IssueCommand]  # RestartCommand
    TRIGGERS = [TrajRandTrigger,]

    def __init__(self, custom_settings=None):
        # TODO: monkey-patching settings, is there a better way to do that ?
        # without breaking 'import settings'
        # keep the settings.py file
        if custom_settings:
            from importlib import import_module
            mod = import_module(custom_settings)
            for attr in dir(mod):
                if not attr.startswith('__'):
                    setattr(settings, attr, getattr(mod, attr))
        super(StupidIrcBot, self).__init__()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='A stupid bot.')
    parser.add_argument('--settings', nargs='?', dest='custom_settings', help="pass a custom settings files")
    args = parser.parse_args()
    bot = StupidIrcBot(custom_settings=args.custom_settings)
    try:
        bot.start()
    except Exception, e:
        # TODO : use argparse to override the settings with a given file
        import traceback
        tb = traceback.format_exc()
        bot.error_logger.error('FATAL : %s\n%s', e, tb)
        raise
