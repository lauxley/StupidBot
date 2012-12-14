import random
import datetime
import re

from db import RandDb

class RandBotMixin():
    """
    ideas :
    allstats, taking non valid rolls into accounts

    """

    is_bot_module = True
    COMMANDS = {
        'rand': 'rand_handler',
        'stats': 'stats_handler',
        'merge': 'merge_handler',
        'ladder': 'ladder_handler',
        'users': 'users_handler'
        }

    REGEXPS = {
        r'(?P<user>[^ ]+)? ?obtient un (?P<roll>\d{1,3}) \(1-100\)' : 'trajrand_handler',
        }

    r_date_fr = r'(?P<day>[0-3][0-9])(?P<month>[0-1][0-9])(?P<year>[0-9]{4})'

    def _init(self):
        self.db = RandDb()

    def get_stats_args(self, ev, *args):
        
        u = dt = rolls = None
        if len(args):
            for i in range(0, len(args)):
                if args[i] == "today":
                    dt = datetime.date.today()
                    rolls = 1
                elif args[i] == "week":
                    dt = datetime.date.today() - datetime.timedelta(days=7)
                    rolls = 3
                elif args[i] == "month":
                    dt = datetime.date.today() - datetime.timedelta(days=31)
                    rolls = 10
                elif args[i] == "year":
                    dt = datetime.date.today() - datetime.timedelta(days=365)
                    rolls = 100
                elif re.match(self.r_date_fr, args[i]):
                    dt = datetime.datetime.strptime(args[i], '%d%m%Y')
                    rolls = (datetime.date.today() - dt).days
                elif args[i].isdigit():
                    rolls = int(args[i])
                else:
                    u = args[i]

        return {'user':u, 'since':dt, 'rolls':rolls}


    def rand_handler(self, serv, ev, *args):
        roll = random.randint(1, 100)
        self.db.add_entry(datetime.datetime.now(), self.get_username_from_source(ev.source), roll)
        return ev.target, '%s rolled a %s' % (self.get_username_from_source(ev.source), str(roll))
    rand_handler.help = u"""!rand: Roll a number between 1 and 100, only one rand per day is taken into account in stats."""


    def merge_handler(self, serv, ev, *args):
        try:
            cmd, user1, users = ev.arguments[0].split(" ", 2)
        except ValueError, e:
            return ev.target, "Bad arguments: the command should be like !merge Joe Bill, John. Bill and John will disapear in favor of Joe"
        else:
            self.db.merge(user1, *users.split(', '))
            return ev.target, "merge in favor of %s" % user1
    merge_handler.help = u"""!merge player player1,player2,player3: Allocate the stats of playerX to 'player', only a trusted user can do this."""
    merge_handler.require_admin = True

    def stats_handler(self, serv, ev, *args):
        # TODO: add min, max, nombre de 100, de 1 ...
        ar = self.get_stats_args(ev, *args)
        if not ar['user']:
            ar['user'] = self.get_username_from_source(ev.source)
        r = self.db.get_stats(ar['user'], ar['since'])
        if r and r[0]:
            return ev.target, u'%s rolled %s times, and got %s on average. min: %s, max: %s.' % (ar['user'], r[1], round(r[0], 3), r[2], r[3])
        else:
            return ev.target, u'No stats for this user'
    stats_handler.help = u"""!stats [player1] [today|week|month|year|DDMMYYYY]: display the rand stats of a given user, or you if no username is given."""

    def ladder_handler(self, serv, ev, *args):
        """
        db.get_ladder returns :
        [('user1', '48.392'), ('user2', '47.045')]
        """
        ar = self.get_stats_args(ev, *args)

        ranks = self.db.get_ladder(ar['rolls'], ar['since'])
        return ev.target, ' - '.join(['#%d %s %d (%sx)' % (r[0]+1, r[1][2], round(r[1][0], 3), r[1][1]) for r in enumerate(ranks)])
    ladder_handler.help = u"""!ladder [today|week|month|year|DDMMYYYY]: display the ordered list of the best randers of the given period."""

    def users_handler(self, serv, ev, *args):
        try:
            like = args[0]
        except IndexError:
            like = None
        users = self.db.get_users(like)
        if users:
            return ev.target, u', '.join(users)
        else:
            return ev.target, u'No users found with this filter.'
    users_handler.help = u"""!users [filter]: display the list of the saved users, if 'filter' is set will display the list of users with 'filter' in their nick"""
    users_handler.require_admin = True

    # REGEXPS HANDLERS
    def trajrand_handler(self, match, serv, ev):
        user = match.group('user')
        if not user: #damn Traj, need a special rule just for him
            user = 'Traj'
        roll = match.group('roll')
        self.db.add_entry(datetime.datetime.now(), user, roll)
        return ev.target, None
