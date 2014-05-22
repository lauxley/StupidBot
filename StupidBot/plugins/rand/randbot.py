import urllib
import os.path
import json
import random
import datetime
import re

from basebot import BaseCommand, BaseBotPlugin, BadCommandLineException
from auth import BaseAuthCommand

from db import RandDb

import settings


class RandCommand(BaseAuthCommand):
    NAME = "rand"
    HELP = u"""rand [[MIN] MAX|El1 El2 El3 ...]: Roll a number between MIN (default 1) and MAX (default 100), only one rand between 1 and 100 per day is taken into account in stats. Or randomize an element in the given list."""
    ALIASES = ['r',]

    DEFAULT_MIN = 1
    DEFAULT_MAX = 100

    def get_user_from_line(self):
        return self.ev.source.nick

    def parse_options(self):
        self.list = False
        self.min = self.DEFAULT_MIN
        self.max = self.DEFAULT_MAX
        if len(self.options):
            if len(self.options) == 1:
                try:
                    self.max = int(self.options[0])
                except ValueError:
                    raise BadCommandLineException
            elif len(self.options) == 2:
                try:
                    self.min = int(self.options[0])
                    self.max = int(self.options[1])
                except ValueError:
                    self.list = True
            else:
                self.list = True

    def get_response(self):
        if self.list:
            result = self.options[random.randint(0, len(self.options) - 1)]
            msg = 'The result is : %s.' % result
        else:
            roll = random.randint(self.min, self.max)
            user = self.bot.auth_plugin.get_username(self.user)
            if self.min == self.DEFAULT_MIN and self.max == self.DEFAULT_MAX:
                self.bot.rand_db.add_entry(datetime.datetime.now(), user, roll, self.ev.target)
            msg = '%s rolled a %s (%s-%s).' % (user, str(roll), self.min, self.max)
        return msg


class StatsArgsMixin(object):
    def _get_stats_args(self):

        r_date_fr = r'(?P<day>[0-3][0-9])(?P<month>[0-1][0-9])(?P<year>[0-9]{4})'
        self.opt_users = []

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
                    rolls = (datetime.datetime.today() - dt).days
                elif self.options[i].isdigit():
                    rolls = int(self.options[i])
                else:
                    u = self.options[i]
                    self.opt_users.append(u)
        self.opt_since = dt
        self.opt_rolls = rolls


class StatsCommand(BaseAuthCommand, StatsArgsMixin):
    NAME = "stats"
    HELP = u"""stats [player1] [today|week|month|year|DDMMYYYY]: display the rand stats of a given user, or you if no username is given."""

    def parse_options(self):
        self._get_stats_args()

    def get_user_from_line(self):
        try:
            return self.opt_users[0]
        except IndexError:
            return self.ev.source.nick

    def get_stats(self):
        return self.bot.rand_db.get_stats(self.bot.auth_plugin.get_username(self.user), self.opt_since, self.ev.target, allrolls=False)

    def get_response(self):
        r = self.get_stats()
        user = self.bot.auth_plugin.get_username(self.user)
        if r and r['count']:
            return  u'%s rolled %s times, and got %s on average. min: %s, max: %s. pos: %s' % (user, r['count'], round(r['avg'], 3), r['min'], r['max'], r['pos'])
        else:
            return  u'No stats for this user (%s)' % user


class AllStatsCommand(StatsCommand):
    NAME = "allstats"
    HELP = u"""allstats [player1] [today|week|month|year|DDMMYYYY]: display the whole rand stats of a given user including invalid rands."""

    def get_stats(self):
        return self.bot.rand_db.get_stats(self.bot.auth_plugin.get_username(self.user), self.opt_since, self.ev.target, allrolls=True)


class LadderCommand(BaseCommand, StatsArgsMixin):
    NAME = "ladder"
    HELP = u"""ladder [min] [today|week|month|year|DDMMYYYY]: display the ordered list of the best randers of the given period. 'min' is the minimal number of rolls."""

    def parse_options(self):
        self._get_stats_args()

    def get_response(self):
        ranks = self.bot.rand_db.get_ladder(self.opt_rolls, self.opt_since, self.ev.target)
        return u' - '.join(['#%d %s %d (%sx)' % (r[0] + 1, r[1][2], round(r[1][0], 3), r[1][1]) for r in enumerate(ranks)])


class MergeCommand(BaseCommand):
    NAME = "merge"
    HELP = u"""merge player player1,player2,player3: Allocate the stats of playerX to player."""
    REQUIRE_ADMIN = True

    def parse_options(self):
        try:
            cmd, user1, users = self.ev.arguments[0].split(" ", 2)
            self.dst_user = user1
            self.src_users = users
        except ValueError:
            raise BadCommandLineException

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
        users = self.bot.rand_db.get_users(self.ev.target, like)
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


class GraphCommand(BaseCommand, StatsArgsMixin):
    NAME = "randgraph"
    HELP = u"""randgraph name1 [name2 [name3 [...]]] : """
    DIRECTORY = settings.RAND_GRAPH_RENDER_DIRECTORY
    BASE_URL = settings.RAND_GRAPH_BASE_URL
    TEMPLATE = "./templates/graph.html"
    COLORS = ["#058DC7", "#AA4643", "#B54804"]  # TODO:

    def parse_options(self):
        self._get_stats_args()

    def _to_js_timestamp(self, date):
        return int(datetime.datetime.strptime(date[:len('XXXX-XX-XX XX:XX')],'%Y-%m-%d %H:%M').strftime("%s")) * 1000

    def process(self):
        """
        var data1 = [
        {label: "name1",  data: d1, points: { fillColor: "#058DC7" }, color: '#058DC7'},
        {label: "name2",  data: d2, points: { fillColor: "#AA4643" }, color: '#AA4643'},
        ];
        """
        data = []

        if not self.opt_users:
            self.opt_users.append(self.ev.source.nick)

        for i, user in enumerate(self.opt_users):
            d = {}
            d["label"] = user
            points = self.bot.rand_db.get_points(user, self.opt_since, self.ev.target)
            if not points:
                continue
            for r in points:
                d["data"] = [[self._to_js_timestamp(r[0]), r[1]] for r in points]
            color = self.COLORS[i % len(self.COLORS)]
            d.update({"points": {"fillcolor": color}, "color": color})
            data.append(d)

        if not data:
            self.bot.send(self.get_target(), u"No data.")
        else:
            with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), self.TEMPLATE), 'r') as template:
                r = template.read()
                render = r.replace("{data}", json.dumps(data))
            filename = "graph_%s.html" % datetime.datetime.now().strftime('%Y%m%d%H%M')
            with open(os.path.join(self.DIRECTORY, filename), 'w+') as html:
                html.write(render)
            self.bot.send(self.get_target(), urllib.basejoin(self.BASE_URL, filename))


class RandPlugin(BaseBotPlugin):
    COMMANDS = [RandCommand, StatsCommand, AllStatsCommand, LadderCommand, MergeCommand, UsersListCommand, BackupCommand, GraphCommand]

    def __init__(self, bot):
        super(RandPlugin, self).__init__(bot)
        self.bot.rand_db = RandDb()
