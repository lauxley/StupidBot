"""
install:
voir db.py
"""

import re
import datetime
import sqlite3

from db import RandDb

# settings
filename = "random.txt"
trusted_bots = ['@Traj', '+Traj', '@Traj-', '+Traj-', '@Jeeju-Traj', '@Jeeju', '@Jeejouh', '@Jeeju-Traj-Jouh', '+Jeeju', '+Jeeju-Trajj', '@Traj-join-TMS', '@Traj`Gforce5200', '@Traj`Geforce2', '@Jeeju|Traj', '@JeejuTraj', '+Jeeju-Traj', '@Traj`Increvable', '@Jeeju-Trajj', '+Jeeju|Traj']

# regexps
# --- Day changed Tue Dec 25 2007
r_date = r'--- Day changed (?P<date>.{3} .{3} \d{2} \d{4})'
# 09:03 <@Traj> Rayas obtient un 15 (1-100)
r_roll = r'(?P<hour>\d{2}:\d{2}) <(?P<bot>[^ ]+)> (?P<user>[^ ]+) obtient un (?P<roll>\d{1,3}) \(1-100\)'

def add_entry(day, hour, user, roll, valid):
    # add_entry(self, datetime, user, roll, valid)
    dt = "%s %s" % (datetime.datetime.strftime(day, '%Y-%b-%d'), datetime.datetime.strftime(hour, '%H:%M'))
    db.add_entry(dt, user, roll, valid)

db = RandDb()
db.flush()

day = None
count = 0 #debug var
today_users = set()
for line in open(filename, 'r'):
    count = count + 1
    is_first = True
    
    dm = re.match(r_date, line) #date match
    dr = re.match(r_roll, line) #roll match
    if dm:
        day = datetime.datetime.strptime(dm.group('date'), '%a %b %d %Y')
        today_users = set() #reset
    elif dr:
        hour = datetime.datetime.strptime(dr.group('hour'), '%H:%M') #int(dr.group('hour').split(':')[0]), int(dr.group('hour').split(':')[1])
        bot = dr.group('bot')
        user = dr.group('user')
        roll = dr.group('roll')
        if user in today_users:
            is_first = False
        today_users.add(user)

        if day:  
            if bot in trusted_bots:
                add_entry(day, hour, user, roll, is_first)
            else:
                print 'bot not trusted : %s for line : \n%s' % (bot, line)
    else:
        pass
        # line not matching anything


db.close()
