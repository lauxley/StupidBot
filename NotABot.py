#! -*- coding: utf-8 -*-
import logging
import random
import datetime
import re
import time

from irc.client import DecodingLineBuffer
from irc.bot import SingleServerIRCBot

from db import RandDb

class CompliantDecodingLineBuffer(DecodingLineBuffer):
    errors = 'replace'

class StupidIrcBot(SingleServerIRCBot):
    # TODO: move this to a setting file
    VERSION = '0.2'
    NICK = u'NotABot'
    REALNAME = u'Not a Bot'
    SERVER = u'euroserv.fr.quakenet.org'
    START_CHANNELS = ['#throkferoth', ]
    ADMINS = ['lox|samta', 'Traj']
    MAX_MSG_LEN = 450 #its 512 but we need some space for the command arguments
    r_date_fr = r'(?P<day>[0-3][0-9])(?P<month>[0-1][0-9])(?P<year>[0-9]{4})'

    COMMANDS = {
        'version': 'version_handler',
        'help': 'help_handler',
        'rand': 'rand_handler',
        'ping': 'ping_handler',
        'merge': 'merge_handler',
        'stats': 'stats_handler',
        'users': 'users_handler',
        'ladder': 'ladder_handler',
        #TBI:
        # 'search'
        # 'max', 'min'
        }

    REGEXPS = {
        r'(?P<user>[^ ]+)? ?obtient un (?P<roll>\d{1,3}) \(1-100\)' : 'trajrand_handler',
        # add a taunt handler
        }

    #won't appear in help
    HIDDEN_COMMANDS = []

    def __init__(self, *args, **kwargs):
        super(StupidIrcBot, self).__init__([(self.SERVER,),], self.NICK, self.REALNAME, *args, **kwargs)

        self.ircobj.add_global_handler("all_events", self.global_handler)

        self.db = RandDb()
        
    def on_welcome(self, serv, ev):
        # changing the default Buffer to ensure no encoding error
        self.connection.buffer = CompliantDecodingLineBuffer()

        for chan in self.START_CHANNELS:
            self.connection.join(chan)

    def global_handler(self, serv, ev):
        """
        ev.arguments:
        - rev
        - node
        - tags (space delimited)
        - branch
        - author
        - desc
        """
        try:
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
                        target, response = getattr(self, self.COMMANDS[cmd])(serv, ev, *arguments)

                    except KeyError:
                        # no a valid command
                        pass
                else:
                    for regexp in self.REGEXPS.keys():
                        m = re.match(regexp, msg)
                        if m:
                            target, response = getattr(self, self.REGEXPS[regexp])(m, serv, ev)
                            # break # should we ?
                if response:
                    self.send(serv, target, response)
        except IndexError:
            pass

    def send(self, serv, target, msg):
        while len(msg) > self.MAX_MSG_LEN:
            time.sleep(1) # so we don't get disco for excess flood
            ind = msg.rfind(" ", 0, self.MAX_MSG_LEN)
            buff = msg[ind:]
            serv.privmsg(target, msg[:ind])
            msg = buff
        serv.privmsg(target, msg)

    def get_need_to_be_admins(self):
        return "Sorry, you can't do that by yourself, ask %s" % (" or ".join(self.ADMINS))

    def get_username_from_source(self, source):
        try:
            return source.split("!")[0]
        except IndexError:
            return source

    def get_stats_args(self, ev, *args):
        fa = dt = None
        if len(args):
            for i in range(0, len(args)):
                if args[i] == "today":
                    dt = datetime.date.today()
                elif args[i] == "week":
                    dt = datetime.date.today() - datetime.timedelta(days=7)
                elif args[i] == "month":
                    dt = datetime.date.today() - datetime.timedelta(days=31)
                elif args[i] == "year":
                    dt = datetime.date.today() - datetime.timedelta(days=365)
                elif re.match(self.r_date_fr, args[i]):
                    dt = datetime.datetime.strptime(args[i], '%d%m%Y')
                elif i == 0:
                    fa = args[0]

        return fa, dt

    # CMD HANDLERS
    def help_handler(self, serv, ev, *args):
        try:
            cmd = args[0]
        except IndexError,e:
            msg = u"Here are the currently implemented commands : %s" % ', '.join(['!%s' %k for k in self.COMMANDS.keys() if k not in self.HIDDEN_COMMANDS])
        else:
            msg = getattr(self, '%s_handler' % cmd).help
        return ev.target, msg
    help_handler.help = u"""Display this help."""

    def rand_handler(self, serv, ev, *args):
        roll = random.randint(1, 100)
        self.db.add_entry(datetime.datetime.now(), self.get_username_from_source(ev.source), roll)
        return ev.target, '%s rolled a %s' % (self.get_username_from_source(ev.source), str(roll))
    rand_handler.help = u"""!rand: Roll a number between 1 and 100, only one rand per day is taken into account in stats."""

    def ping_handler(self, serv, ev, *args):
        return ev.target, u'pong'
    ping_handler.help = u"""!ping: pong?"""

    def merge_handler(self, serv, ev, *args):
        if self.get_username_from_source(ev.source) in self.ADMINS:
            try:
                cmd, user1, users = ev.arguments[0].split(" ", 2)
            except ValueError, e:
                return ev.target, "Bad arguments: the command should be like !merge Joe Bill, Bill will disapear in favor of Joe"
            else:
                self.db.merge(user1, *users.split(', '))
                return ev.target, "merge in favor of %s" % user1
        else:
            return ev.target, self.get_need_to_be_admins()
    merge_handler.help = u"""!merge player player1,player2,player3: Allocate the stats of playerX to 'player', only a trusted user can do this."""

    def stats_handler(self, serv, ev, *args):
        # TODO: add min, max, nombre de 100, de 1 ...
        user, dt = self.get_stats_args(ev, *args)
        if not user:
            user = self.get_username_from_source(ev.source)
        r = self.db.get_stats(user, dt)
        if r[0]:
            return ev.target, u'%s rolled %s times, and got %s on average.' % (user, r[1], round(r[0], 3))
        else:
            return ev.target, u'No stats for this user'
    stats_handler.help = u"""!stats [player1] [today|week|month|year|DDMMYYYY]: display the rand stats of a given user, or you if no username is given."""

    def ladder_handler(self, serv, ev, *args):
        """
        db.get_ladder returns :
        [('user1', '48.392'), ('user2', '47.045')]
        """
        minrolls, dt = self.get_stats_args(ev, *args)

        ranks = self.db.get_ladder(minrolls, dt)
        return ev.target, ' - '.join(['#%d %s %d (%sx)' % (r[0]+1, r[1][2], round(r[1][0], 3), r[1][1]) for r in enumerate(ranks)])
    ladder_handler.help = u"""!ladder [today|week|month|year|DDMMYYYY]: display the ordered list of the best randers of the given period."""

    def users_handler(self, serv, ev, *args):
        try:
            like = args[0]
        except IndexError:
            like = None
        if not self.get_username_from_source(ev.source) in self.ADMINS:
            return ev.target, self.get_need_to_be_admins()
        else:
            users = self.db.get_users(like)
            if users:
                return ev.target, u', '.join(users)
            else:
                return ev.target, u'No users found with this filter.'
    users_handler.help = u"""!users [filter]: display the list of the saved users, if 'filter' is set will display the list of users with 'filter' in their nick"""


    def version_handler(self, serv, ev, *args):
        return ev.target, u"version: %s" % self.VERSION
    version_handler.help = u"""Display the bot version."""

    # REGEXPS HANDLERS
    def trajrand_handler(self, match, serv, ev):
        user = match.group('user')
        if not user: #damn Traj, need a special rule just for him
            user = 'Traj'
        roll = match.group('roll')
        self.db.add_entry(datetime.datetime.now(), user, roll)
        return ev.target, None


bot = StupidIrcBot()
bot.start()
