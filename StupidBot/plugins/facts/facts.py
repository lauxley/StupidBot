import re

from sqlalchemy import or_, and_
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
            if len(self.options) == 1 and re.match(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}$', self.options[0]):
                self.date = self.options.pop()
            self.context = self.options
        else:
            if self.ev.target in self.plugin.context_store:
                self.context = self.plugin.context_store[self.ev.target].split(" ")
            else:
                self.context = []

        self.context = sorted(self.context, lambda w1, w2: len(w2) - len(w1))

    def get_response(self):
        # this should query the base using the biggest word as a search term
        q = self.session.query(self.plugin.SCHEMA)

        if self.date:
            fact = q.filter(self.plugin.SCHEMA.date == self.date).order_by(func.rand()).first()
        else:
            # testing with the whole 'sentence'
            fact = q.filter(or_
                            (and_(*[self.plugin.SCHEMA.text.like('%%%s%%' % e) for e in self.context]),
                            and_(*[self.plugin.SCHEMA.author.like('%%%s%%' % e) for e in self.context]))
                            ).order_by(func.rand()).first()
            if not fact:
                # we only keep 'big' words (>1) and see how it goes
                c = [w for w in self.context if len(w) > 1]
                fact = q.filter(or_(*[self.plugin.SCHEMA.text.like('%%%s%%' % e) for e in c]),
                                or_(*[self.plugin.SCHEMA.author.like('%%%s%%' % e) for e in c])
                                ).order_by(func.rand()).first()

        return fact or u"no match"


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
