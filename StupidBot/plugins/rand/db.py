
"""
$ sudo apt-get install sqlite3
$ sqlite3 rand.db
sqlite> CREATE TABLE rolls (pk INT AUTO_INCREMENT PRIMARY KEY,
                            user VARCHAR(50) NOT NULL,
                            roll_on DATETIME NOT NULL,
                            value SMALLINT NOT NULL,
                            valid TINYINT);
"""

import sqlite3
import datetime
import shutil
import os

import settings


class RandDb(object):
    db_file = "rand.db"

    def _connect(self):
        self.conn = sqlite3.connect(self.db_file)

    def __init__(self):
        if not os.path.isfile(self.db_file):
            self._connect()
            self.make()
        else:
            self._connect()

    def close(self):
        self.conn.close()

    def backup(self):
        bck_dir = os.path.join(getattr(settings, 'BACKUP_DIR', 'backups'), 'rand')
        if not os.path.isdir(bck_dir):
            os.makedirs(bck_dir)
        d = datetime.datetime.strftime(datetime.datetime.now(), '%Y%m%d_%H%M')
        shutil.copy(self.db_file, os.path.join(bck_dir, '%s.%s' % (self.db_file, d)))

    def insert(self, table, values):
        cur = self.conn.cursor()
        if table == 'rolls':
            cols = '`user`, `roll_on`, `value`, `chan`, `valid`'
        else:
            return
        sql = "INSERT INTO `%s` (%s) VALUES (%s);" % (table, cols, ','.join(['?' for v in values]))
        cur.execute(sql, values)
        self.conn.commit()

    def make(self):
        sql = """CREATE TABLE rolls (pk INT AUTO_INCREMENT PRIMARY KEY,
                            user VARCHAR(50) NOT NULL,
                            roll_on DATETIME NOT NULL,
                            value SMALLINT NOT NULL,
                            chan VARCHAR(64),
                            valid TINYINT);"""
        cur = self.conn.cursor()
        cur.execute(sql)
        self.conn.commit()

    # def get_or_create_user(self, user):
    #     cur = self.conn.cursor()
    #     cur.execute("SELECT pk FROM users WHERE name = ?;", [user,])
    #     u = cur.fetchone()
    #     if not u:
    #         cur.execute("INSERT INTO `users` VALUES (?);", [user,])
    #         self.conn.commit()
    #         cur.execute("SELECT pk FROM users WHERE name = `?`;", [user,])
    #         u = cur.fetchone()

    #     return u["pk"]

    def sql_dt(self, dt):
        return datetime.datetime.strftime(dt, '%Y-%m-%d %H:%M')

    def already_rolled(self, dt, user, chan):
        cur = self.conn.cursor()
        sql = "SELECT * FROM rolls WHERE date(roll_on)=date(?) AND user=? AND chan=? LIMIT 1;"
        cur.execute(sql, [self.sql_dt(dt), user, chan])
        if cur.fetchone():
            return True
        return False

    def add_entry(self, dt, user, roll, chan, valid=None):
        if valid is None:
            # test the existence of a roll
            valid = not self.already_rolled(dt, user, chan)
        # userpk = self.get_or_create_user(user)
        self.insert('rolls', [user, dt, roll, chan, valid])
        return valid

    def flush(self):
        self.backup()
        cur = self.conn.cursor()
        # cur.execute("DELETE FROM users;")
        cur.execute("DELETE FROM rolls;")
        self.conn.commit()

    def get_stats(self, user, dt, chan, allrolls=False):
        cur = self.conn.cursor()
        if not dt:
            dt = datetime.datetime(2000, 1, 1)  # ugly
        sql = "SELECT AVG(value) as a, COUNT(*) as c, MIN(value) as min, MAX(value) as max FROM rolls WHERE valid>=? AND roll_on >= ? AND chan=? GROUP BY user HAVING user = ?;"
        cur.execute(sql, [int(not allrolls), self.sql_dt(dt), chan, user])
        r = cur.fetchone()

        # we need another query to get the pos because sqlite sux
        if r:
            sql = "SELECT COUNT(*) FROM (SELECT AVG(value) as a FROM rolls WHERE valid>=? AND roll_on>=? AND chan=? GROUP BY user HAVING a >= ?);"
            cur.execute(sql, [int(not allrolls), self.sql_dt(dt), chan, int(r[0])])
            p = cur.fetchone()

            return {'avg':r[0], 'count':r[1], 'min':r[2], 'max':r[3], 'pos':p[0]}

    def get_ladder(self, min_rolls, dt, chan):
        cur = self.conn.cursor()
        if not dt:
            dt = datetime.date(2000, 1, 1)  # ugly
        if not min_rolls:
            min_rolls = 1
        sql = u"SELECT AVG(value) as a, COUNT(value) as c, user from rolls WHERE valid=1 AND roll_on >= ? AND chan=? GROUP BY user HAVING c >= ? ORDER BY a DESC LIMIT 10;"
        cur.execute(sql, (self.sql_dt(dt), chan, min_rolls))
        return cur.fetchall()

    def get_users(self, chan, like=None):
        cur = self.conn.cursor()
        if like:
            cur.execute("SELECT DISTINCT(user) FROM rolls WHERE chan=? AND user LIKE ?;", [chan, '%' + like + '%'])
        else:
            cur.execute("SELECT DISTINCT(user) FROM rolls WHERE chan=?;", [chan,])
        return [u[0] for u in cur.fetchall()]

    def merge(self, user1, *users):
        self.backup()
        cur = self.conn.cursor()
        for user in users:
            cur.execute("UPDATE rolls SET user=? WHERE user=?", [user1, user])
        self.conn.commit()
        # we should try to invalidate some rolls there if an user changed his nick and rerolled
        # or not, im lazy
