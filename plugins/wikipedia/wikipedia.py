import urllib
import urllib2
from xml.dom.minidom import parseString
from xml.parsers.expat import ExpatError

from basebot import BaseBotPlugin, BaseCommand


class DefineCommand(BaseCommand):
    NAME = "define"
    ALIASES = ["d"]

    WIKI_SEARCH_URL = u"http://%s.wikipedia.org/w/api.php"

    def split_response(self, arguments):
        self.lang = "fr"
        # TODO : be able to change language
        self.query = u" ".join(arguments[0].strip().split(" ")[1:])

    def get_response(self):
        params = {'action':'opensearch', 'search': self.query, 'format':'xml', 'limit': 1}
        request = urllib2.Request(self.WIKI_SEARCH_URL % self.lang + urllib.urlencode(params))
        try:
            response = urllib2.urlopen(request)
            dom = parseString(response)
            description = dom.getElementsByTagName('Description').text

        except (urllib2.URLError, ExpatError):
            return u"Nop."

        return description


class WikipediaPlugin(BaseBotPlugin):
    COMMANDS = [DefineCommand,]
