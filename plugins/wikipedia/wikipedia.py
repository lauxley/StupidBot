#! -*- coding: utf-8 -*-
import urllib
import urllib2
from xml.dom.minidom import parseString
from xml.parsers.expat import ExpatError

from basebot import BaseBotPlugin, BaseCommand
import settings


class DefineCommand(BaseCommand):
    NAME = "define"
    ALIASES = ["d"]
    HELP = u"define [lang=CODE] [index=INDEX] WORD|EXPRESSION - fetch the wikipedia api to give you the definition of the given word/expression."

    WIKI_SEARCH_URL = u"http://%s.wikipedia.org/w/api.php"

    def split_options(self, arguments):
        super(DefineCommand, self).split_options(arguments)
        self.index = int(self.args.get(u'index', 0))
        self.lang = self.args.get(u'lang', getattr(settings, 'DEFAULT_LANG', 'en'))
        self.query = urllib.quote_plus(u" ".join(self.options))

    def get_response(self):
        params = {'action':'opensearch', 'search': self.query, 'format':'xml'}
        request = urllib2.Request(self.WIKI_SEARCH_URL % self.lang + '?' + urllib.urlencode(params))
        try:
            response = urllib2.urlopen(request)
            dom = parseString(response.read())
            name = dom.getElementsByTagName('Text')[self.index].firstChild.wholeText
            description = dom.getElementsByTagName('Description')[self.index].firstChild.wholeText
            items_count = dom.getElementsByTagName('Item').length
        except (urllib2.URLError, ExpatError, IndexError, ValueError), e:
            self.plugin.bot.error_logger.error('Problem trying to fetch a wikipedia description (%s): %s' % (request.get_full_url(), e))
            return u"Nop."
        
        resp_count = u"%s(index %s of %d):" % (name, self.index, items_count)
        resp_desc = u"%s" % description
        return [resp_count, resp_desc]


class WikipediaPlugin(BaseBotPlugin):
    COMMANDS = [DefineCommand,]
