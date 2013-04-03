#! -*- coding: utf-8 -*-
import datetime

from basebot import BaseIrcBot, HelpCommand, VersionCommand, PingCommand, ReconnectCommand, IssueCommand  # RestartCommand,
from auth import BaseAuthTrigger


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


if __name__ == '__main__':
    bot = StupidIrcBot()
    try:
        bot.start()
    except Exception, e:
        import traceback
        tb = traceback.format_exc()
        bot.error_logger.error('FATAL : %s\n%s', e, tb)
        raise
