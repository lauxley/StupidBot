from __future__ import division
import math
import re


def safe_calc(expr):
    def _is_safe(expr):
        whitelist = '^('+'|'.join(
        # oprators, digits
        ['-', r'\+', '/', r'\\', r'\*', r'\^', r'\*\*', r'\(', r'\)', '\d+']
        # functions of math module (ex. __xxx__)
        + [f for f in dir(math) if f[:2] != '__']) + ')*$'
        return re.match(whitelist, expr)

    expr = string.replace(expr,",",".") # european style
    if _is_safe(expr):
        try:
            return str(eval(expr, dict(__builtins__=None), vars(math)))
        except TypeError:
            return u"Sorry, this calculator is stupid, try something more explicit."
    else:
        # TODO : log
        return u'What are you trying to do exactly ?'

class CalcBot():
    is_bot_module=True

    COMMANDS = {
        "c": "calc_handler",
        "calc": "calc_handler"
        }

    def calc_handler(self, ev, *args):
        if not len(args):
            return ev.target, self.calc_handler.help

        
        return ev.target, safe_calc(args[0])
    calc_handler.help = u"!calc EXPRESSION: a simple calculator."
