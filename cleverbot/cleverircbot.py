import cleverbot
import settings

class CleverBotMixin():
    is_bot_module = True
    REGEXPS = {
        r'(?P<me>%s):?(?P<msg>.*)' % settings.NICK : 'highligh_handler',
        }

    def _init(self):
        self.brain = cleverbot.Session()

    # REGEXPS HANDLERS
    def highligh_handler(self, match, serv, ev):
        return ev.target, self.brain.Ask(match.group('msg').encode('ascii', 'replace'))

