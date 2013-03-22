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

    WIKI_SEARCH_URL = u"http://%s.wikipedia.org/w/api.php"

    def split_options(self, arguments):
        self.lang = getattr(settings, 'DEFAULT_LANG', 'en')
        # TODO : be able to change language with something like lang=de
        self.query = u" ".join(arguments[0].strip().split(" ")[1:])

    def get_response(self):
        params = {'action':'opensearch', 'search': self.query, 'format':'xml', 'limit': 1}
        # TODO : there is probably a cleaner way to add the query string
        request = urllib2.Request(self.WIKI_SEARCH_URL % self.lang + '?' + urllib.urlencode(params))
        try:
            response = urllib2.urlopen(request)
            dom = parseString(response.read())
            name = dom.getElementsByTagName('Text')[0].firstChild.wholeText
            description = dom.getElementsByTagName('Description')[0].firstChild.wholeText
        except (urllib2.URLError, ExpatError, IndexError, ValueError), e:
            self.plugin.bot.error_logger.error('Problem trying to fetch a wikipedia description : %s' % e)
            return u"Nop."

        return u"%s: %s" % (name, description)


class WikipediaPlugin(BaseBotPlugin):
    COMMANDS = [DefineCommand,]
