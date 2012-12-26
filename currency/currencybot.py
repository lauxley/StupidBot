import settings
from openexchange.simpleapi import convert, get_currencies

class CurrencyBot():
    COMMANDS = {
        'cur': 'currency_handler',
        'curency': 'currency_handler',
        'currencies': 'currencies_handler',
        }

    default_currency = getattr(settings,'DEFAULT_CURRENCY', 'eur')
    oops = u'wrong parameters, or service unreachable.'

    def currency_handler(self, ev, *args):
        if len(args) == 3 and args[2].isdigit():
            from_curr = args[0]
            to_curr = args[1]
            amount = float(args[2])
        elif len(args) == 2 and args[1].isdigit():
            from_curr = args[0]
            to_curr = self.default_currency
            amount = float(args[1])
        elif len(args) == 2:
            from_curr = args[0]
            to_curr = args[1]
            amount = 1
        elif len(args) == 1:
            from_curr = args[0]
            to_curr = self.default_currency
            amount = 1
        else:
            return ev.target, self.oops
        
        c = convert(from_curr=from_curr, to_curr=to_curr, amount=amount)
        if c is None:
            return ev.target, self.oops
        
        return ev.target, '%s %s = %s %s' % (amount, from_curr, c, to_curr)
    currency_handler.help = u"!currency FROMCUR [TOCUR] [AMOUNT] - for a list of all currencies, check !currencies."


    def currencies_handler(self, ev, *args):
        curs = get_currencies()
        if not curs:
            return ev.target, self.oops
        return ev.target, ', '.join(curs)
    currencies_handler.help = u"!currencies - a list of all available currencies"
