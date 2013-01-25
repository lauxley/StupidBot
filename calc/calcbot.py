from __future__ import division
import math
import re
import string
import threading

from basebot import BaseBotModule, BaseCommand
import settings

CALC_TIMEOUT = getattr(settings, 'CALC_TIMEOUT', 2) # seconds


class TimeoutException(Exception):
    pass


class UnsafeExpressionException(Exception):
    pass


def timeout(func, args=(), kwargs={}, timeout=10, default=None):
    class ResultThread(threading.Thread):
        def run(self):
            self.result = func(*args, **kwargs)
    t = ResultThread()
    t.daemon = True
    t.start()
    t.join(timeout)
    if t.isAlive():
        # note that the thread is still running :(
        raise TimeoutException
    else:
        return t.result


def safe_calc(expr):
    def _is_safe(expr):
        whitelist = '^('+'|'.join(
        # oprators, digits
        ['-', r'\+', '/', r'\\', r'\*', r'\^', r'\*\*', r'\(', r'\)', '\d+']
        # functions of math module (ex. __xxx__)
        + [f for f in dir(math) if f[:2] != '__']) + ')*$'
        return re.match(whitelist, expr)

    def _check_implicit_operations(expr):
        r = r'(\d+)(\(.*\))'
        expr = re.sub(r, lambda s: '%s*%s' % (s.group(1), s.group(2)), expr)
        r = r'(\(.*\))(\d+)'
        expr = re.sub(r, lambda s: '%s*%s' % (s.group(2), s.group(1)), expr)
        return expr

    def _do_calc(expr):
        return str(eval(expr, dict(__builtins__=None), vars(math)))

    expr = string.replace(expr,",",".") # european style
    expr = _check_implicit_operations(expr) # replace things like 4(3+2) by 4*(3+2)

    if _is_safe(expr):
        result = timeout(_do_calc, args=[expr,], timeout=CALC_TIMEOUT)
        return result
    else:
        raise UnsafeExpressionException


class CalcCommand(BaseCommand):
    NAME = "calc"
    ALIASES = ['c']
    HELP = u"!calc EXPRESSION: a simple calculator."
    
    def get_response(self):
        if not self.options:
            return self.HELP
        try:
            result = safe_calc(self.options[0])
        except TypeError, e:
            self.module.bot.error_logger.warning(u"Invalid calc %s : %s" % (self.options[0], e))
            return u"Sorry, this calculator is stupid, try something more explicit."
        except TimeoutException, e:
            self.module.bot.error_logger.error(u'timeout trying to calculate : %s.' % self.options[0])
            return 'Sorry, it was taking me too long, i quit.'
        except UnsafeExpressionException,e:
            self.module.bot.error_logger.warning(u'Unsafe expression %s.' % self.options[0])
            return u'What are you trying to do exactly ?'

        return result


class CalcModule(BaseBotModule):
    COMMANDS = [CalcCommand,]
