import random
import datetime
import re

from basebot import BaseCommand, BaseAuthCommand, BaseAuthTrigger, BaseBotModule, BaseAuthModule

from db import RandDb

class RandCommand(BaseAuthCommand):
    NAME = "rand"
    HELP = u"""rand: Roll a number between 1 and 100, only one rand per day is taken into account in stats."""
    ALIASES = ['r',]

    def get_response(self):
        roll = random.randint(1, 100)
        user = self.bot.auth_module.get_username(self.user)
        valid = self.bot.rand_db.add_entry(datetime.datetime.now(), user, roll)
        msg = '%s rolled a %s.' % (user, str(roll))
        return msg


class TrajRandTrigger(BaseAuthTrigger):
    REGEXP = r'(?P<username>[^ ]+)? ?obtient un (?P<roll>\d{1,3}) \(1-100\)'


    def handle(self):
        if self.ev.source.nick == 'Traj':
            user = self.get_user_from_line()
            if not user: #damn Traj, need a special rule just for him
                user = 'Traj'
            self.bot.auth_module.get_user(user, self.process)


    def process(self, user, *args):
        # TODO : check that the self.ev.source is really Traj (authed as such)
        valid = self.bot.rand_db.add_entry(datetime.datetime.now(), auth, roll)
        roll = self.match.group('roll')
        user = self.bot.auth_module.get_username(user)
        msg = '%s rolled a %s.' % (user, str(roll))
        self.bot.send(self.ev.target, msg)


class StatsArgsMixin(object):
    def _get_stats_args(self):

        r_date_fr = r'(?P<day>[0-3][0-9])(?P<month>[0-1][0-9])(?P<year>[0-9]{4})'

        u = dt = rolls = None
        if len(self.options):
            for i in range(0, len(self.options)):
                if self.options[i] == "today":
                    dt = datetime.date.today()
                    rolls = 1
                elif self.options[i] == "week":
                    dt = datetime.date.today() - datetime.timedelta(days=7)
                    rolls = 3
                elif self.options[i] == "month":
                    dt = datetime.date.today() - datetime.timedelta(days=31)
                    rolls = 10
                elif self.options[i] == "year":
                    dt = datetime.date.today() - datetime.timedelta(days=365)
                    rolls = 100
                elif re.match(r_date_fr, self.options[i]):
                    dt = datetime.datetime.strptime(self.options[i], '%d%m%Y')
                    rolls = (datetime.date.today() - dt).days
                elif self.options[i].isdigit():
                    rolls = int(self.options[i])
                else:
                    u = self.options[i]

        self.opt_user = u
        self.opt_since = dt
        self.opt_rolls = rolls


class StatsCommand(BaseAuthCommand, StatsArgsMixin):
    NAME = "stats"
    HELP = u"""stats [player1] [today|week|month|year|DDMMYYYY]: display the rand stats of a given user, or you if no username is given."""

    def _parse_options(self):
        super(StatsCommand, self)._parse_options() # hack
        self._get_stats_args()

    def get_user_from_line(self):
        return self.opt_user or self.ev.source.nick

    def get_stats(self):
        return self.bot.rand_db.get_stats(self.bot.auth_module.get_username(self.user), self.opt_since, allrolls=False)

    def get_response(self):
        r = self.get_stats()
        user = self.bot.auth_module.get_username(self.user)
        if r and r['count']:
            return  u'%s rolled %s times, and got %s on average. min: %s, max: %s. pos: %s' % (user, r['count'], round(r['avg'], 3), r['min'], r['max'], r['pos'])
        else:
            return  u'No stats for this user (%s)' % user


class AllStatsCommand(StatsCommand):
    NAME = "allstats"
    HELP = u"""allstats [player1] [today|week|month|year|DDMMYYYY]: display the whole rand stats of a given user including invalid rands."""

    def get_stats(self):
        return self.bot.rand_db.get_stats(self.bot.auth_module.get_username(self.user), self.opt_since, allrolls=True)


class LadderCommand(BaseCommand, StatsArgsMixin):
    NAME = "ladder"
    HELP = u"""ladder [today|week|month|year|DDMMYYYY]: display the ordered list of the best randers of the given period."""

    def _parse_options(self):
        super(LadderCommand, self)._parse_options()
        self._get_stats_args()

    def get_response(self):
        ranks = self.bot.rand_db.get_ladder(self.opt_rolls, self.opt_since)
        return u' - '.join(['#%d %s %d (%sx)' % (r[0]+1, r[1][2], round(r[1][0], 3), r[1][1]) for r in enumerate(ranks)])


class MergeCommand(BaseCommand):
    NAME = "merge"
    HELP = u"""merge player player1,player2,player3: Allocate the stats of playerX to 'player', only a trusted user can do this."""
    REQUIRE_ADMIN = True

    def _parse_options(self):
        try:
            cmd, user1, users = self.ev.arguments[0].split(" ", 2)
            self.dst_user = user1
            self.src_users = users
        except ValueError, e:
            self.bot.send(ev.target, "Bad arguments: the command should be like !merge Joe Bill, John. Bill and John will disapear in favor of Joe")
            return None
        
        return []

    def process(self):
        self.bot.rand_db.merge(self.dst_user, *self.src_users.split(', '))
        self.bot.send(self.get_target(), u"Merge done in favor of %s." % self.dst_user)


class UsersListCommand(BaseCommand):
    NAME = "users"
    HELP = u"""users [filter]: display the list of the saved users, if 'filter' is set will display the list of users with 'filter' in their nick"""
    REQUIRE_ADMIN = True

    def get_response(self):
        try:
            like = self.options[0]
        except IndexError:
            like = None
        users = self.bot.rand_db.get_users(like)
        if users:
            return u', '.join(users)
        else:
            return u'No users found with this filter.'


class BackupCommand(BaseCommand):
    NAME = "backup"
    HELP = u"""backup: does exactly what it says."""
    REQUIRE_ADMIN = True
    
    def process(self):
        self.bot.rand_db.backup()
        self.bot.send(self.get_target(), u"Done.")


class RandModule(BaseBotModule):
    COMMANDS = [ RandCommand, StatsCommand, AllStatsCommand, LadderCommand, MergeCommand, UsersListCommand, BackupCommand ]
    TRIGGERS = [TrajRandTrigger,]

    def __init__(self, bot):
        super(RandModule, self).__init__(bot)
        self.bot.rand_db = RandDb()
