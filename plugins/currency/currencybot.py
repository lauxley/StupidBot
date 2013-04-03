from openexchange.simpleapi import convert, get_currencies

import settings

from basebot import BaseBotPlugin, BaseCommand, BadCommandLineException


class CurrencyCommand(BaseCommand):
    NAME = "currency"
    ALIASES = ["cur",]
    HELP = u"!currency FROMCUR [TOCUR] [AMOUNT] - for a list of all currencies, check !currencies."

    default_currency = getattr(settings,'DEFAULT_CURRENCY', 'eur')
    oops = u'Wrong parameters, or service unreachable.'

    def parse_options(self):
        if len(self.options) == 3 and self.options[2].isdigit():
            self.from_curr = self.options[0]
            self.to_curr = self.options[1]
            self.amount = float(self.options[2])
        elif len(self.options) == 2 and self.options[1].isdigit():
            self.from_curr = self.options[0]
            self.to_curr = self.default_currency
            self.amount = float(self.options[1])
        elif len(self.options) == 2:
            self.from_curr = self.options[0]
            self.to_curr = self.options[1]
            self.amount = 1
        elif len(self.options) == 1:
            self.from_curr = self.options[0]
            self.to_curr = self.default_currency
            self.amount = 1
        else:
            raise BadCommandLineException

    def get_response(self):
        c = convert(from_curr=self.from_curr, to_curr=self.to_curr, amount=self.amount)
        if c is None:
            return self.oops

        return u'%s %s = %s %s' % (self.amount, self.from_curr, c, self.to_curr)


class CurrenciesCommand(BaseCommand):
    NAME = "currencies"
    HELP = u"!currencies - a list of all available currencies"

    def get_response(self):
        curs = get_currencies()
        if not curs:
            return self.oops
        return ', '.join(curs)


class CurrencyPlugin(BaseBotPlugin):
    COMMANDS = [CurrencyCommand, CurrenciesCommand]
