from __future__ import division
import math
import re
import string
#import threading
from multiprocessing import Process, Queue

from basebot import BaseBotPlugin, BaseCommand, BadCommandLineException
import settings

CALC_TIMEOUT = getattr(settings, 'CALC_TIMEOUT', 2) # seconds


class TimeoutException(Exception):
    pass


class UnsafeExpressionException(Exception):
    pass


def timeout(func, args=(), kwargs={}, timeout=10, default=None):
    result_queue = Queue()
    class ResultProcess(Process):
        def run(self):
            try:
                result_queue.put(func(*args, **kwargs))
            except Exception, e:
                result_queue.put(e)

    p = ResultProcess(target=func, args=args, kwargs=kwargs)
    p.daemon = True
    p.start()
    p.join(timeout)
    if p.is_alive():
        raise TimeoutException
    else:
        return result_queue.get() or default


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
        result = timeout(_do_calc, args=[expr,], timeout=CALC_TIMEOUT, default=u"Nop.")
        return result
    else:
        raise UnsafeExpressionException


class CalcCommand(BaseCommand):
    NAME = "calc"
    ALIASES = ['c']
    HELP = u"!calc EXPRESSION: a simple calculator."
    
    def parse_options(self):
        if not len(self.options):
            raise BadCommandLineException

    def get_response(self):
        try:
            result = safe_calc(self.options[0])
        except TypeError, e:
            self.plugin.bot.error_logger.warning(u"Invalid calc %s : %s" % (self.options[0], e))
            return u"Sorry, this calculator is stupid, try something more explicit."
        except TimeoutException, e:
            self.plugin.bot.error_logger.error(u'timeout trying to calculate : %s.' % self.options[0])
            return 'Sorry, it was taking me too long, i quit.'
        except UnsafeExpressionException, e:
            self.plugin.bot.error_logger.warning(u'Unsafe expression %s.' % self.options[0])
            return u'What are you trying to do exactly ?'

        return result


class CalcPlugin(BaseBotPlugin):
    COMMANDS = [CalcCommand,]
