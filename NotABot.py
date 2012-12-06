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
    NICK = u'NotABot'
    REALNAME = u'Not a Bot'
    SERVER = u'euroserv.fr.quakenet.org'
    START_CHANNELS = ['#throkferoth', ]
    ADMINS = ['lox|samta', 'Traj']
    MAX_MSG_LEN = 450 #its 512 but we need some space for the command arguments

    COMMANDS = {
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
                        try:
                            cmd, arguments = msg[1:].split(' ', 1)
                        except ValueError, e:
                            #there is no arguments
                            cmd = msg[1:]
                        target, response = getattr(self, self.COMMANDS[cmd])(serv, ev)

                    except KeyError:
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

    # CMD HANDLERS
    def help_handler(self, serv, ev):
        return ev.target, u"Here are the currently implemented commands : %s" % ', '.join(['!%s' %k for k in self.COMMANDS.keys() if k not in self.HIDDEN_COMMANDS])

    def rand_handler(self, serv, ev):
        roll = random.randint(1, 100)
        self.db.add_entry(datetime.datetime.now(), self.get_username_from_source(ev.source), roll)
        return ev.target, '%s rolled a %s' % (self.get_username_from_source(ev.source), str(roll))

    def ping_handler(self, serv, ev):
        return ev.target, u'pong'

    def merge_handler(self, serv, ev):
        if self.get_username_from_source(ev.source) in self.ADMINS:
            try:
                s, user1, user2 = ev.arguments[0].split(" ")
            except ValueError, e:
                return ev.target, "Bad arguments: the command should be like !merge Joe Bill, Bill will disapear in favor of Joe"
            else:
                self.db.merge(user1, user2)
                return ev.target, "%s was merged in favor of %s" % (user2, user1)
        else:
            return ev.target, self.get_need_to_be_admins()

    def stats_handler(self, serv, ev):
        try:
            user = ev.arguments[0].split(" ")[1]
        except (IndexError,ValueError), e:
            user = self.get_username_from_source(ev.source)

        r = self.db.get_stats(user)
        if r[0]:
            return ev.target, u'%s rolled %s times, and got %s on average.' % (user, r[1], round(r[0], 3))
        else:
            return ev.target, u'No stats for this user'

    def min_handler(self, serv, ev):
        pass

    def max_handler(self, serv, ev):
        pass

    def get_username_from_source(self, source):
        try:
            return source.split("!")[0]
        except IndexError:
            return ev.source

    def users_handler(self, serv, ev):
        try:
            like = ev.arguments[0].split(" ")[1]
        except IndexError:
            like = None
        if not self.get_username_from_source(ev.source) in self.ADMINS:
            return ev.target, self.get_need_to_be_admins()
        else:
            return ev.target, u', '.join(self.db.get_users(like))

    def ladder_handler(self, serv, ev):
        """
        !ladder
        !ladder 50 #minimum number of rolls

        db.get_ladder returns :
        [('user1', '48.392'), ('user2', '47.045')]
        """
        try:
            # TODO: make a method to split commands and arguments
            min_rolls = int(ev.arguments[0].split(" ")[1])
        except (IndexError, ValueError),e:
            min_rolls = 10 # default value
        ranks = self.db.get_ladder(min_rolls)
        return ev.target, ' - '.join(['#%d %s %d (%sx)' % (r[0]+1, r[1][2], round(r[1][0], 3), r[1][1]) for r in enumerate(ranks)])

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
