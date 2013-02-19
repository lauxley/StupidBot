import time
import urllib
from threading import Thread
from xml.dom.minidom import parseString

from basebot import BaseCommand, BaseBotPlugin

class RegisterOnline(BaseCommand):
    NAME = "everegister"

    def get_response(self):
        if self.ev.target.startswith('#'):
            self.plugin.registered_chans.add(self.ev.target)
        return u"Done."


class IsOnline(BaseCommand):
    NAME = "evestatus"

    def get_response(self):
        return self.plugin.tell_status()


class EvePlugin(BaseBotPlugin):
    FETCH_TIME = 2
    API_ONLINE_URL = u"https://api.eveonline.com/server/ServerStatus.xml.aspx/"

    COMMANDS = [RegisterOnline, IsOnline]

    def __init__(self, bot):
        super(EvePlugin, self).__init__(bot)
        self.online = None
        self.registered_chans = set()

    def on_welcome(self, serv, ev):
        self.fetch()

    def tell_status(self):
        if self.online is None:
            return u"I don't know !"
        elif self.online:
            status = u"Online"
        else:
            status = u"Offline"
        msg = u"Eve online Server status : %s." % status
        if self.nb:
            msg = msg + " (%d players)" % self.nb
        return  msg

    def _poll(self):
        # polling
        while(True):
            try:
                data = urllib.urlopen(self.API_ONLINE_URL).read()
                dom = parseString(data)
                online = dom.getElementsByTagName("serverOpen")[0].firstChild.wholeText
                nbnode = dom.getElementsByTagName("onlinePlayers")
                if nbnode:
                    self.nb = int(nbnode[0].firstChild.wholeText)
                else:
                    self.nb = 0
                o = (online == u"True")
                if o != self.online:
                    self.online = o
                    for chan in self.registered_chans:
                        self.bot.send(chan, self.tell_status)
            except (TypeError, IndexError, ValueError), e:
                self.bot.error_logger.error("Error fetching eve status : %s" % e)
            time.sleep(self.FETCH_TIME*60)

    def fetch(self):
        thr = Thread(target=self._poll)
        thr.daemon = True
        thr.start()
