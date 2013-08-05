import re
from datetime import datetime

from sqlalchemy import or_
from  sqlalchemy.sql.expression import func

from basebot import BaseBotPlugin, BaseIrcBot, BaseTrigger
from basedb import DbMixin, DbCommand

from model import Fact


class FactCommand(DbCommand):
    NAME = u"fact"
    ALIASES = [u"f"]
    HELP = u"fact [about|date(YYYY-MM-DD)|author] - a random fact matching the argument, or the context."

    def parse_options(self):
        self.date = None
        if len(self.options):
            #handle date
            if len(self.options) == 1 and re.match(r'^[1-9]{4}-[1-9]{2}-[1-9]{2}$', self.options[0]):
                self.date = datetime.strptime(self.options.pop(), '%Y-%m-%d')
            self.context = self.options
        else:
            if self.ev.target in self.plugin.context_store:
                self.context = self.plugin.context_store[self.ev.target].split(" ")
            else:
                self.context = []

        # we only keep 'big' words (>1) and see how it goes
        self.context = sorted([w for w in self.context if len(w) > 1], lambda w1, w2: len(w2) - len(w1))

    def get_response(self):
        fact = None
        i = 0
        while fact is None:
            # this should query the base using the biggest word as a search term
            q = self.session.query(self.plugin.SCHEMA)
            if self.date:
                q.filter(self.plugin.SCHEMA == self.date)
                i = i + 1

            if len(self.context) > i:
                q = q.filter(or_(self.plugin.SCHEMA.text.like('%%%s%%' % self.context[i]),
                                 self.plugin.SCHEMA.author.like('%%%s%%' % self.context[i]),
                                 self.plugin.SCHEMA.category.like('%%%s%%' % self.context[i])
                                 ))

            fact = q.order_by(func.rand()).first()
            i = i + 1
        return u'%s' % fact or u"no match"


class ContextTrigger(BaseTrigger):
    """
    memorize the 'context' of the conversation
    """
    # doesnt start with a ! (COMMAND_PREFIX), and is at least 10 characters long
    REGEXP = r'^(?!\%c).{10,}' % BaseIrcBot.COMMAND_PREFIX

    def process(self):
        self.plugin.context_store[self.ev.target] = self.match.group(0)


class FactsPlugin(DbMixin, BaseBotPlugin):
    SCHEMA = Fact
    COMMANDS = [FactCommand]
    TRIGGERS = [ContextTrigger]

    def __init__(self, bot):
        super(FactsPlugin, self).__init__(bot)
        self.context_store = {}
