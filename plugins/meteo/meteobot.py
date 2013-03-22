#! -*- coding: utf-8 -*-
import os
import sqlite3

from datetime import datetime
from unidecode import unidecode

from basebot import BaseBotPlugin
from auth import BaseAuthCommand
import settings

from worldweatheronline import get_weather


class MeteoCommand(BaseAuthCommand):
    NAME = "meteo"
    ALIASES = ["weather",]

    # custom
    DATE_REQUEST_CHOICES = ['current', 'today', 'tomorrow', 'weekend']
    oops = u"Wrong parameters, or service unreachable."

    HELP = u"meteo CITY[,COUNTRY] [%s] - Note that weekend is only available from Tuesday to Friday." % '|'.join(DATE_REQUEST_CHOICES)

    def get_user_from_line(self):
        return self.ev.source.nick

    def get_response(self):
        user = self.bot.auth_plugin.get_username(self.user)
        location = self.plugin.meteo_db[user] or getattr(settings, 'DEFAULT_LOCATION', 'Paris,france')
        day = 'tomorrow'

        for arg in self.options:
            if arg in ['current', 'today', 'tomorrow', 'weekend']:
                day = arg
            else:
                location = unidecode(arg)

        self.plugin.meteo_db[user] = location

        # TODO : this is blocking, is it a good idea ?
        weather, error = get_weather(location, day)
        if not weather:
            if error:
                self.plugin.bot.error_logger.error("Cannot fetch the weather : %s" % error)
            return self.oops

        if type(weather[2]) == tuple:
            temp = u'%s° to %s°' % (weather[2][0], weather[2][1])
        else:
            temp = u'%s°' % weather[2]
        return u'%s (%s): %s, %s, precipitations: %smm' % (weather[0], datetime.strftime(weather[4], '%d %b'), weather[1], temp, weather[3])


class MeteoDB(object):
    db_file = "meteo.db"

    def __init__(self):
        if not os.path.isfile(self.db_file):
            self._connect()
            self._make_db()
        else:
            self._connect()

    def __getitem__(self, key):
        cur = self.conn.cursor()
        cur.execute("SELECT location FROM meteo WHERE user=?;", [key,])
        r = cur.fetchone()
        cur.close()
        if r:
            return r[0]
        else:
            return None

    def __setitem__(self, key, value):
        cur = self.conn.cursor()
        cur.execute("SELECT ROWID FROM meteo WHERE user=?;", [key,])
        r = cur.fetchone()
        if r:
            cur.execute("UPDATE meteo SET location=? WHERE user=?;", [value, key])
        else:
            cur.execute("INSERT INTO meteo (user, location) VALUES (?, ?);", [key, value])
        self.conn.commit()
        cur.close()

    def _make_db(self):
        sql = """CREATE TABLE meteo (
                            user VARCHAR(50) NOT NULL,
                            location VARCHAR(200));"""
        cur = self.conn.cursor()
        cur.execute(sql)
        self.conn.commit()

    def close(self):
        self.conn.close()

    def _connect(self):
        self.conn = sqlite3.connect(self.db_file)


class MeteoPlugin(BaseBotPlugin):
    COMMANDS = [MeteoCommand,]

    def __init__(self, bot):
        super(MeteoPlugin, self).__init__(bot)
        # used to remember each user choice
        self.meteo_db = MeteoDB()
