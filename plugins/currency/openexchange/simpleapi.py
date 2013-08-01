import urllib2
import json
from decimal import Decimal

import settings

#URL = 'http://finance.yahoo.com/d/quotes.csv?e=.csv&f=sl1d1t1&s={from_curr}{to_curr}=X'
URL = 'http://openexchangerates.org/api/latest.json?app_id={app_id}'
CURRENCIES_URL = 'http://openexchangerates.org/api/currencies.json?app_id={app_id}'

API_ID = settings.OPEN_EXCHANGE_API_ID

def _get_data(url):
    request = urllib2.Request(url, None, {'Accept-encoding': 'utf8'})
    try:
        response = urllib2.urlopen(request)
    except urllib2.URLError:
        return None
    result = response.read()
    return result

def convert(from_curr, to_curr='EUR', amount=1.0):
    if from_curr.lower() == to_curr.lower():
        return amt
    
    data = _get_data(URL.format(app_id=API_ID))
    if data:
        try:
            exchange = json.loads(data)
            from_rate = float(exchange['rates'][from_curr.upper()])
            to_rate = float(exchange['rates'][to_curr.upper()])

            rate = to_rate / from_rate

            return u'{0:.3f}'.format(round(rate * amount, 3))
        except (IndexError, ValueError, KeyError):
            pass
    return None

def get_currencies():
    data = _get_data(CURRENCIES_URL.format(app_id=API_ID))
    if data:
        try:
            jd = json.loads(data)
            return sorted(jd.keys())
        except ValueError,e:
            raise #pass
    return None
