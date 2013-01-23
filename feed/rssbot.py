import os.path
import sqlite3
import urlparse
import datetime, time
from threading import Thread

import feedparser

import settings

from basebot import BaseBotModule, BaseCommand

def dt_to_sql(dt):
    if type(dt) == datetime.datetime:
        return datetime.datetime.strftime(dt, '%Y-%m-%d %H:%M:%S')
    elif type(dt) == time.struct_time:
        return datetime.datetime.fromtimestamp(time.mktime(dt))
    return None

def from_sql_dt(dt):
    return datetime.datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')


class RssFeed(object):
    def __init__(self, module, row):
        self.module = module
        self.id = row[0]
        self.url = row[1]
        self.updated = from_sql_dt(row[2])
        self.last_entry = row[3]
        self.channels = row[4].split(',')
        self.title = row[5]

        self.entries = []

    def __unicode__(self):
        return unicode(self.title)

    def tell(self, entryn=0):
        try:
            return u'%s : %s - %s' % (self.title, self.entries[entryn].title, self.entries[entryn].link)
        except (IndexError, AttributeError), e:
            self.module.bot.error_logger.error("Bad parameter to RssFeed.tell : %s" % e)
            return u'Bad parameters.'

    def tell_more(self, entryn=0):
        try:
            entry = self.entries[entryn]
            return [entry.title, entry.summary, entry.link]
        except (IndexError, AttributeError), e:
            self.module.bot.error_logger.error("Bad parameter to RssFeed.tell : %s" % e)
            return u'Bad parameters.'

    def update(self, conn):
        cur = conn.cursor()
        sql = "UPDATE feeds SET last_entry=?, last_updated=? WHERE ROWID=?;"
        cur.execute(sql, [self.last_entry, dt_to_sql(self.updated), self.id])
        conn.commit()

    def fetch(self, conn):
        # TODO : catch if feed changed and became invalid all of a sudden
        # or if an entry has been deleted !
        #self.module.bot.error_logger.info("Fetching %s." % self.title)
        data = feedparser.parse(self.url)

        del self.entries
        self.entries = data['entries']

        new_data = []
        try:
            upd = getattr(data,'updated',None) or getattr(data, 'published', None) or data['entries'][0]['published']
        except (IndexError, KeyError), e:
            self.module.bot.error_logger.error("Something went wrong trying to update the Rss Feed %s : %s" % (self.title, e))
        else:
            # because of http://bugs.python.org/issue6641
            # im not using the utc information
            updated = datetime.datetime.strptime(upd[:24], '%a, %d %b %Y %H:%M:%S')

            if updated > self.updated:
                for entry in data['entries']:
                    if self.last_entry == entry['id']:
                        break
                    else:
                        new_data.append(entry)

                if data['entries']:
                    self.last_entry = data['entries'][0].id
                    self.updated = updated
                    self.update(conn)

        return new_data

    def _update_sql_chans(self):
        sql = "UPDATE feeds SET channels=? WHERE ROWID=?;"
        cur = self.module.feed_conn.cursor()
        cur.execute(sql, [','.join(self.channels), self.id])
        self.module.feed_conn.commit()

    def add_chan(self, chan):
        self.channels.append(chan)
        self._update_sql_chans()

    def del_chan(self, chan):
        self.channels.remove(chan)
        if len(self.channels):
            self._update_sql_chans()
        else:
            sql = "DELETE FROM feeds WHERE ROWID=?;"
            cur = self.module.feed_conn.cursor()
            cur.execute(sql, [self.id,])
            self.module.feed_conn.commit()
        

class AddFeedCommand(BaseCommand):
    NAME = "feedadd"
    HELP = u"addfeed FEED_TITLE FEED_URL - add the given rss feed to the list."
    REQUIRE_ADMIN = True

    def get_response(self):
        # check parameters
        if len(self.options) != 2:
            return u"Please give me one title and a valid url."
        feed_title = self.options[0]
        feed_url = self.options[1]
        
        # check if the feed already exists, create it if not
        feed, created = self.module._get_feed(feed_url, feed_title, self.ev.target)
        # check the channel is not already in the list
        if feed:
            if created:
                return u'Feed added to this channel.'
            elif self.ev.target in feed.channels:
                return u"Already added in this channel."
            else:
                feed.add_chan(self.ev.target)
                return u'Feed added to this channel.'
        else:
            return u"Invalid RSS feed."


class FeedListCommand(BaseCommand):
    NAME = "feedlist"
    HELP = u"feedlist - print the list of fetched rss feeds for this channel."

    def get_response(self):
        if self.module.feeds:
            return ' - '.join(['%s:%s' % (f.title, f.url) for f in self.module.feeds if (self.ev.target in f.channels)])
        else:
            return u'No rss feed added yet.'


class FeedRemoveCommand(BaseCommand):
    NAME = "feedremove"
    HELP = u"removefeed FEED_URL|FEED_ID - remove the given feed from the current channel."
    ALIASES = ["feeddel",]
    REQUIRE_ADMIN = True

    def get_response(self):
        chan = self.ev.target
        for feed in self.module.feeds:
            if feed.title == self.options[0] or feed.url == self.options[0]:
                feed.del_chan(chan)
                title = feed.title
                if len(feed.channels) == 0:
                    self.module.feeds.remove(feed)
                return "Done. %s won't bother you anymore." % title
        return "Couldn't delete feed %s." % self.options[0]

class FeedCommand(BaseCommand):
    """
    TODO: 
    * log old entries
    * & pass a date to !feed 
    * search interface (for example title=foobar)
    * strip the html code or even better find the attribute without html code
    """

    NAME = "feed"
    HELP = u"!feed [FEED_TITLE [#ENTRY_NUMBER]] - sends you a private message with the content of the given entry, or the last fetched entry if none."
    TARGET = "source"
    
    def get_last_feed(self):
        most_recent = self.module.feeds[0]
        for feed in self.module.feeds:
            if feed.updated > most_recent.updated:
                most_recent = feed
        return most_recent


    def get_response(self):
        if not self.module.feeds:
            return u'No rss feed added yet.'

        entryn = 0
        feed = self.get_last_feed()
        for arg in self.options:
            if arg.isdigit():
                entryn = int(arg)
            for f in self.module.feeds:
                if f.title == arg:
                    feed = f
                    break

        return feed.tell_more(entryn=entryn)


class RssModule(BaseBotModule):
    """
    TODO: cleanup (especially the db part)
    """

    db_file = 'feeds.db'

    feeds = []

    FETCH_TIME = getattr(settings, 'FEED_FETCH_TIME', 2) # in minutes
    MAX_ENTRIES = getattr(settings, 'FEED_MAX_ENTRIES', 5) # maximum entries to display when fetching a feed

    COMMANDS = [ AddFeedCommand, FeedListCommand, FeedRemoveCommand, FeedCommand ]
 
    def __init__(self, bot):
        super(RssModule, self).__init__(bot)
        # initialize the loop to fetch the feeds
        if not os.path.isfile(self.db_file):
            self.feed_conn = sqlite3.connect(self.db_file, check_same_thread = False)
            self._make_db()
            return
        self.feed_conn = sqlite3.connect(self.db_file, check_same_thread = False)

        sql = "SELECT ROWID, url, last_updated, last_entry, channels, title FROM feeds"
        cur = self.feed_conn.cursor()
        for row in cur.execute(sql):
            self.feeds.append(RssFeed(self, row))
        cur.close()
                
    def close(self):
        self.feed_conn.close()

    def on_welcome(self, serv, ev):
        self.fetch_feeds()

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
            data = feedparser.parse(feed_url)
            
            last_entry = data['entries'][0]['id']

            upd = getattr(data,'updated',None) or getattr(data, 'published', None) or data['entries'][0]['published']
            last_updated = datetime.datetime.strptime(upd[:24], '%a, %d %b %Y %H:%M:%S')
            
            feed = RssFeed(self, self._create_feed(feed_url, feed_title, last_entry, dt_to_sql(last_updated), chan))
            feed.entries = data['entries']
            created = True
        except (IndexError, KeyError), e:
            self.bot.error_logger.warning('Invalid feed : %s' % e)
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
        # polling
        while(True):
            for feed in self.feeds:
                new_data = feed.fetch(self.feed_conn)
                for n, entry in enumerate(new_data[:self.MAX_ENTRIES]):
                    for chan in feed.channels:
                        self.bot.send(chan, feed.tell(entryn=n))

            time.sleep(self.FETCH_TIME*60)

    def fetch_feeds(self):
        thr = Thread(target=self._fetch)
        thr.daemon = True
        thr.start()



