import os.path
import sqlite3
import urlparse
import datetime, time
from threading import Thread

import feedparser

import settings


def dt_to_sql(dt):
    if type(dt) == datetime.datetime:
        return datetime.datetime.strftime(dt, '%Y-%m-%d %H:%M:%S')
    elif type(dt) == time.struct_time:
        return datetime.datetime.fromtimestamp(time.mktime(dt))
    return None

def from_sql_dt(dt):
    return datetime.datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')


class RssFeed():
    def __init__(self, row):
        self.id = row[0]
        self.url = row[1]
        self.updated = from_sql_dt(row[2])
        self.last_entry = row[3]
        self.channels = row[4].split(',')
        self.title = row[5]

        self.entries = []

    def update(self, conn):
        cur = conn.cursor()
        sql = "UPDATE feeds SET last_entry=?, last_updated=? WHERE ROWID=?;"
        cur.execute(sql, [self.last_entry, dt_to_sql(self.updated), self.id])
        conn.commit()


    def fetch(self, conn):
        # TODO : catch if feed changed and became invalid all of a sudden
        data = feedparser.parse(self.url)

        del self.entries
        self.entries = data['entries']

        new_data = []
        updated = datetime.datetime.strptime(data['updated'], '%a, %d %b %Y %H:%M:%S %Z')

        if updated != self.updated:
            for entry in data['entries']:
                if self.last_entry == entry['id']:
                    return []
                else:
                    new_data.append(entry)
                    self.last_entry = entry.id
                    self.updated = updated
                    self.update(conn)
        return new_data


class RssBot():
    is_bot_module = True
    db_file = 'feeds.db'

    feeds = []

    FETCH_TIME = getattr(settings, 'FEED_FETCH_TIME', 2) # in minutes
    MAX_ENTRIES = getattr(settings, 'FEED_MAX_ENTRIES', 5) # maximum entries to display when fetching a feed

    COMMANDS = {
        'addfeed':'addfeed_handler',
        'removefeed':'removefeed_handler',
        'feedlist':'feedlist_handler',
        'feed':'feed_handler', # priv msg the selected feed entry
        }


    def _init(self):
        # initialize the loop to fetch the feeds
        if not os.path.isfile(self.db_file):
            self.feed_conn = sqlite3.connect(self.db_file, check_same_thread = False)
            self._make_db()
            return
        self.feed_conn = sqlite3.connect(self.db_file, check_same_thread = False)

        sql = "SELECT ROWID, url, last_updated, last_entry, channels, title FROM feeds"
        cur = self.feed_conn.cursor()
        cur.execute(sql)
        row = cur.fetchone()
        while row:
            self.feeds.append(RssFeed(row))
            row = cur.fetchone()
        cur.close()
                
    def close(self):
        self.feed_conn.close()

    
    def _make_db(self):
        sql = """CREATE TABLE feeds (
                            url VARCHAR(255) NOT NULL,
                            last_entry VARCHAR(64),
                            last_updated DATETIME,
                            channels VARCHAR(255),
                            title VARCHAR(64)
                );"""

        cur = self.feed_conn.cursor()
        cur.execute(sql)
        self.feed_conn.commit()
        cur.close()

    def _get_feed(self, feed_url, feed_title, chan):
        created = False
        for feed in self.feeds:
            if feed.url == feed_url:
                return feed, created
        try:
            # check that it is a valid feed
            data = feedparser.parse(feed_url)

            last_entry = data['entries'][0]['id']
            last_updated = datetime.datetime.strptime(data['updated'], '%a, %d %b %Y %H:%M:%S %Z')

            feed = RssFeed(self._create_feed(feed_url, feed_title, last_entry, dt_to_sql(last_updated), chan))
            feed.entries = data['entries']
            created = True
        except (IndexError, KeyError), e:
            self.error_logger.warning('Invalid feed : %s' % e)
            return None, False
        
        self.feeds.append(feed)
        return feed, created


    def _create_feed(self, feed_url, feed_title, last_entry, last_updated, chan):
        sql = "INSERT INTO feeds (url, last_entry, last_updated, channels, title) VALUES (?,?,?,?,?)"
        cur = self.feed_conn.cursor()
        cur.execute(sql, [feed_url, last_entry, last_updated, chan, feed_title])
        self.feed_conn.commit()

        sql = "SELECT ROWID, url, last_updated, last_entry, channels, title FROM feeds WHERE url=?"
        cur.execute(sql, [feed_url,])
        return cur.fetchone()

    def _fetch(self):
        while(True):
            for feed in self.feeds:
                new_data = feed.fetch(self.feed_conn)
                for entry in new_data[:self.MAX_ENTRIES]:
                    for chan in feed.channels:
                        self.send(chan, self._tell(feed, entry))
                        time.sleep(self.TIME_BETWEEN_MSGS) # avoid to get kicked, TODO: should be managed in self.send

            time.sleep(self.FETCH_TIME*60)

    def fetch_feeds(self):
        thr = Thread(target=self._fetch)
        thr.daemon = True
        thr.start()

    def _tell(self, feed, entry):
        return '%s : %s - %s' % (feed.title, entry['title'], entry['link'])

    def _tell_more(self, feed, entry):
        return '%s : %s - %s' % (feed.title, entry['title'], entry['link'])

    # HANDLERS
    def addfeed_handler(self, ev, *args):
        # check parameters
        if len(args) != 2:
            return ev.target, u"Please give me one title and a valid url."
        feed_title = args[0]
        feed_url = args[1]
        
        # check if the feed already exists, create it if not
        feed, created = self._get_feed(feed_url, feed_title, ev.target)
        # check the channel is not already in the list
        if feed:
            if created:
                return ev.target, u'Feed added to this channel.'
            elif ev.target in feed.channels:
                return ev.target, u"Already added in this channel."
            else:
                # add it
                feed.channels.append(ev.target)
                sql = "UPDATE feeds SET channels=? WHERE ROWID=?;"
                cur = self.feed_conn.cursor()
                cur.execute(sql, [','.join(feed.channels), feed.id])
                self.feed_conn.commit()
                return ev.target, u'Feed added to this channel.'
        else:
            return ev.target, u"Invalid RSS feed."

    addfeed_handler.help = u"!addfeed FEED_TITLE FEED_URL - add the given rss feed to the list."
    addfeed_handler.require_admin = True
    

    def feedlist_handler(self, ev, *args):
        if self.feeds:
            return ev.target, ' - '.join(['%s:%s' % (f.title,f.url) for f in self.feeds])
        else:
            return ev.target, u'No rss feed added yet.'
    feedlist_handler.help = u"!feedlist - print the list of fetched rss feeds for this channel."
    
    
    def removefeed_handler(self, ev, *args):
        raise NotImplementedError
    removefeed_handler.help = u"!removefeed FEED_URL|#FEED_ID - remove the given feed from the current channel."
    removefeed_handler.require_admin = True
    

    def get_last_entry(self):
        most_recent = self.feeds[0]
        for feed in self.feeds:
            if feed.updated > most_recent.updated:
                most_recent = feed
        return most_recent, most_recent.entries[0]

    def feed_handler(self, ev, *args):
        if not self.feeds:
            return ev.target, u'No rss feed added yet.'

        if len(args) == 0:
            feed, last_entry = self.get_last_entry()
            return ev.source.nick, self._tell_more(feed, last_entry)
        else:
            feedn = None
            entryn = None
            try:
                for arg in args:
                    if arg[0] != "#":
                        for n,feed in enumerate(self.feeds):
                            if feed.title == arg:
                                feedn = n
                    else:
                        entryn = int(arg[1:])

                if feedn is not None and entryn is not None:
                    return ev.source.nick, self._tell_more(self.feeds[feedn], self.feeds[feedn].entries[entryn])
                elif feedn is not None:
                    return ev.source.nick, self._tell_more(self.feeds[feedn], self.feeds[feedn].entries[0])
                else:
                    raise IndexError # kinda ugly :p

            except (TypeError, ValueError, IndexError):
                return ev.target, u"Bad parameters."
    feed_handler.help = u"!feed [FEED_TITLE [#ENTRY_NUMBER]] - sends you a private message with the content of the given entry, or the last fetched entry if none."
