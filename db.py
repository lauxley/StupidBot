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

class RandDb(object):
    db_file = "rand.db"
    
    def _connect(self):
        self.conn = sqlite3.connect(self.db_file)

    def __init__(self):
        self._connect()

    def close(self):
        self.conn.close()

    def insert(self, table, values):
        # assert table exists
        # assert values is a list
        cur = self.conn.cursor()
        # todo: except sql injection attempt
        if table == 'rolls':
            cols = '`user`, `roll_on`, `value`, `valid`'
        else:
            return
        sql = "INSERT INTO `%s` (%s) VALUES (%s);" % (table, cols, ','.join(['?' for v in values]))
        cur.execute(sql, values)
        self.conn.commit()

    def make(self):
        # TODO
        pass

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

    def already_rolled(self, dt, user):
        cur = self.conn.cursor()
        sql = "SELECT * FROM rolls WHERE date(roll_on)=date(?) AND user=? LIMIT 1;"
        cur.execute(sql, [self.sql_dt(dt), user])
        if cur.fetchone():
            return True
        return False

    def add_entry(self, dt, user, roll, valid=None):
        if valid == None:
            # test the existence of a roll
            valid = not self.already_rolled(dt, user)
        # userpk = self.get_or_create_user(user)
        self.insert('rolls', [user, dt, roll, valid])

    def flush(self):
        cur = self.conn.cursor()
        # cur.execute("DELETE FROM users;")
        cur.execute("DELETE FROM rolls;")
        self.conn.commit()


    def get_stats(self, user):
        cur = self.conn.cursor()
        cur.execute("SELECT AVG(value) as a, COUNT(*) as c FROM rolls WHERE valid=1 AND user=?;", [user,])
        r = cur.fetchone()
        if r:
            return r
        else:
            return None
    
    def get_users(self, like=None):
        cur = self.conn.cursor()
        if like:
            cur.execute("SELECT DISTINCT(user) FROM rolls;")
        else:
            cur.execute("SELECT DISTINCT(user) FROM rolls WHERE user LIKE ?;", ('%'+like+'%',))
        return [u[0] for u in cur.fetchall()]

    def merge(self, user1, user2):
        cur = self.conn.cursor()
        cur.execute("UPDATE rolls SET user=? WHERE user=?", [user1, user2])
        self.conn.commit()
        # we should try to invalidate some rolls there if an user changed his nick and rerolled
        # or not, im lazy

    def get_ladder(self, min_rolls):
        cur = self.conn.cursor()
        cur.execute("SELECT AVG(value) as a, COUNT(value) as c, user from rolls WHERE valid=1 GROUP BY user HAVING c > ? ORDER BY a DESC LIMIT 10;", (min_rolls, ))
        return cur.fetchall()
