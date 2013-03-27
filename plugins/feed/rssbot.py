import re
import os.path
import sqlite3
import datetime, time
import bleach
from threading import Thread

import feedparser

import settings

from basebot import BaseBotPlugin, BaseCommand, BadCommandLineException


def dt_to_sql(dt):
    if type(dt) == datetime.datetime:
        return datetime.datetime.strftime(dt, '%Y-%m-%d %H:%M:%S')
    elif type(dt) == time.struct_time:
        return datetime.datetime.fromtimestamp(time.mktime(dt))
    return None


def from_sql_dt(dt):
    return datetime.datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')


class RssFeed(object):
    def __init__(self, plugin, row):
        self.plugin = plugin
        self.id = row[0]
        self.url = row[1]
        self.updated = from_sql_dt(row[2])
        self.last_entry = row[3]

        self.channel = row[4]
        self.title = row[5]
        self.filter = row[6]
        self.exclude = row[7]

        self.entries = []

    def __unicode__(self):
        return unicode(self.title)

    def tell(self, entry):
        try:
            return u'%s : %s - %s' % (self.title, entry.title, entry.link)
        except (IndexError, AttributeError), e:
            self.plugin.bot.error_logger.error("Bad parameter to RssFeed.tell : %s" % e)
            return u'Bad parameters.'

    def tell_more(self, entry):
        try:
            return [entry.title, bleach.clean(entry.summary, tags=[], strip=True), entry.link]
        except (IndexError, AttributeError), e:
            self.plugin.bot.error_logger.error("Bad parameter to RssFeed.tell : %s" % e)
            return u'Bad parameters.'

    def update(self):
        cur = self.plugin.feed_conn.cursor()
        sql = "UPDATE feeds SET last_entry=?, last_updated=?, filter=?, exclude=? WHERE ROWID=?;"
        cur.execute(sql, [self.last_entry, dt_to_sql(self.updated), self.filter, self.exclude, self.id])
        self.plugin.feed_conn.commit()

    def delete(self):
        cur = self.plugin.feed_conn.cursor()
        sql = "DELETE FROM feeds WHERE ROWID=?"
        cur.execute(sql, [self.id,])
        self.plugin.feed_conn.commit()

    def fetch(self):
        # TODO : catch if feed changed and became invalid all of a sudden
        # or if an entry has been deleted !
        data = feedparser.parse(self.url, request_headers={'Cache-control': 'max-age=%d' % self.plugin.FETCH_TIME * 60})

        del self.entries
        self.entries = data['entries']

        new_data = []
        try:
            try:
                if 'updated_parsed' in data['feed']:  # if possible we use the feed date, because the first entry date could change if the entry is removed
                    upd = data['feed']['updated_parsed']
                else:
                    upd = data['entries'][0]['updated_parsed']
                updated = datetime.datetime.fromtimestamp(time.mktime(upd))
            except TypeError:
                upd = getattr(data,'updated',None) or getattr(data, 'published', None) or data['entries'][0]['published']
                updated = datetime.datetime.strptime(upd[:24], '%a, %d %b %Y %H:%M:%S')
        except (IndexError, KeyError), e:
            self.plugin.bot.error_logger.error("Something went wrong trying to update the Rss Feed %s : %s" % (self.title, e))
        else:
            if updated > self.updated:
                for entry in data['entries']:
                    if self.last_entry == entry['id']:
                        break
                    else:
                        if not self.filter or (self.filter and re.findall(self.filter, entry.title, flags=re.IGNORECASE)):
                            if not self.exclude or (self.exclude and not re.findall(self.exclude, entry.title, flags=re.IGNORECASE)):
                                new_data.append(entry)

                if data['entries']:
                    self.last_entry = data['entries'][0].id
                    self.updated = updated
                    self.update()

        return new_data


class AddFeedCommand(BaseCommand):
    NAME = "feedadd"
    HELP = u"addfeed FEED_TITLE FEED_URL - add the given rss feed to the list."
    REQUIRE_ADMIN = True

    def parse_options(self):
        if len(self.options) != 2:
            raise BadCommandLineException
        self.feed_title = self.options[0]
        self.feed_url = self.options[1]

    def get_response(self):
        # check if the feed already exists, create it if not
        feed, created = self.plugin._get_or_create_feed(self.feed_url, self.feed_title, self.ev.target)
        if feed:
            if created:
                return u'Feed added to this channel.'
            else:
                return u"Already added in this channel."
        else:
            return u"Invalid RSS feed."


class FeedListCommand(BaseCommand):
    NAME = "feedlist"
    HELP = u"feedlist - print the list of fetched rss feeds for this channel."

    def get_response(self):
        if self.plugin.feeds:
            return ' - '.join(['%s:%s' % (f.title, f.url) for f in self.plugin.feeds if (self.ev.target == f.channel)])
        else:
            return u'No rss feed added yet.'


class FeedRemoveCommand(BaseCommand):
    NAME = "feedremove"
    HELP = u"removefeed FEED_URL|FEED_ID - remove the given feed from the current channel."
    ALIASES = ["feeddel",]
    REQUIRE_ADMIN = True

    def parse_options(self):
        if len(self.options) != 1:
            raise BadCommandLineException

    def get_response(self):
        chan = self.ev.target
        for feed in self.plugin.feeds:
            if feed.title == self.options[0] and feed.channel == chan:
                feed.delete()
                self.plugin.feeds.remove(feed)
                return "Done. %s won't bother you anymore." % feed.title
        return "Couldn't delete feed %s." % self.options[0]


class FeedAddFilter(BaseCommand):
    """
    Add a filter to a specific feed on a specific channel,
    only
    """
    NAME = u"feedfilter"
    REQUIRE_ADMIN = True
    HELP = u"feedfilter FEED_TITLE PATTERN - when fetching new entries from FEED_TITLE, the bot will only display the entries matching PATTERN."

    # custom
    RESPONSE = u"Filter applied for feed %s."

    def parse_options(self):
        if len(self.options) < 2:
            raise BadCommandLineException

    def apply_filter(self, feed):
        feed.filter = self.options[1]
        feed.update()

    def get_response(self):
        for feed in self.plugin.feeds:
            if feed.title == self.options[0] and feed.channel == self.ev.target:
                self.apply_filter(feed)
                return self.RESPONSE % feed.title


class FeedAddExclude(FeedAddFilter):
    NAME = u"feedexclude"
    REQUIRE_ADMIN = True
    HELP = u"feedexclude FEED_TITLE PATTERN - when fetching new entries from FEED_TITLE, the bot will NOT display the entries matching PATTERN."

    RESPONSE = "Exclusion applied for feed %s."

    def apply_filter(self, feed):
        feed.exclude = self.options[1]
        feed.update()


class FeedCommand(BaseCommand):
    """
    TODO:
    * log old entries
    * & pass a date to !feed
    * search interface (for example title=foobar) with grep ?!
    """

    NAME = "feed"
    HELP = u"feed [FEED_TITLE [ENTRY_NUMBER|list]] - sends you a private message with the content of the given entry."
    TARGET = "source"

    def get_last_feed(self):
        most_recent = self.plugin.feeds[0]
        for feed in self.plugin.feeds:
            if feed.updated > most_recent.updated:
                most_recent = feed
        return most_recent

    def parse_options(self):
        self.entryn = 0
        self.feed = None
        for arg in self.options:
            if arg.isdigit():
                self.entryn = int(arg)
            for f in self.plugin.feeds:
                if f.title == arg:
                    self.feed = f
                    break
        if not self.feed:
            self.feed = self.get_last_feed()
        if self.entryn >= len(self.feed.entries):
            raise BadCommandLineException("There is only %d entries available." % len(self.feed.entries))

    def get_response(self):
        if not self.plugin.feeds:
            return u'No rss feed added yet.'

        return self.feed.tell_more(self.feed.entries[self.entryn])


class RssPlugin(BaseBotPlugin):
    """
    TODO: cleanup (especially the db part)
    """

    db_file = 'feeds.db'

    FETCH_TIME = getattr(settings, 'FEED_FETCH_TIME', 2)  # in minutes
    MAX_ENTRIES = getattr(settings, 'FEED_MAX_ENTRIES', 5)  # maximum entries to display when fetching a feed

    COMMANDS = [AddFeedCommand, FeedListCommand, FeedRemoveCommand, FeedCommand, FeedAddFilter, FeedAddExclude]

    def __init__(self, bot):
        super(RssPlugin, self).__init__(bot)

        self.feeds = []

        # initialize the loop to fetch the feeds
        if not os.path.isfile(self.db_file):
            self.feed_conn = sqlite3.connect(self.db_file, check_same_thread=False)
            self._make_db()
            return
        self.feed_conn = sqlite3.connect(self.db_file, check_same_thread=False)

        sql = "SELECT ROWID, url, last_updated, last_entry, channel, title, filter, exclude FROM feeds"
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
                            channel VARCHAR(64) NOT NULL,
                            title VARCHAR(64),
                            filter VARCHAR(64),
                            exclude VARCHAR(64)
                );"""

        cur = self.feed_conn.cursor()
        cur.execute(sql)
        self.feed_conn.commit()
        cur.close()

    def _get_or_create_feed(self, feed_url, feed_title, chan):
        created = False
        for feed in self.feeds:
            if feed.url == feed_url and feed.channel == chan:
                return feed, created

        try:
            data = feedparser.parse(feed_url)

            last_entry = data['entries'][0]['id']

            if 'updated_parsed' in data['feed']:
                last_updated = datetime.datetime.fromtimestamp(time.mktime(data['feed']['updated_parsed']))
            else:
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
        sql = "INSERT INTO feeds (url, last_entry, last_updated, channel, title) VALUES (?,?,?,?,?)"
        cur = self.feed_conn.cursor()
        cur.execute(sql, [feed_url, last_entry, last_updated, chan, feed_title])
        self.feed_conn.commit()

        sql = "SELECT ROWID, url, last_updated, last_entry, channel, title, filter, exclude FROM feeds WHERE url=?"
        cur.execute(sql, [feed_url,])
        return cur.fetchone()

    def _fetch(self):
        # polling
        while(True):
            for feed in self.feeds:
                # TODO : this is sub-obtimal,
                # if we have the same feed in different channels, it will be fetched as many times
                new_data = feed.fetch()
                if len(new_data) > self.MAX_ENTRIES:
                    self.bot.send(feed.channel, u"%d new entries for %s ! access them with !feed %s X" % (len(new_data), feed.title, feed.title))
                else:
                    for n, entry in enumerate(new_data[:self.MAX_ENTRIES]):
                        self.bot.send(feed.channel, feed.tell(entry))
            time.sleep(self.FETCH_TIME * 60)

    def fetch_feeds(self):
        thr = Thread(target=self._fetch)
        thr.daemon = True
        thr.start()
