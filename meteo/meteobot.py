#! -*- coding: utf-8 -*-
from datetime import datetime
from unidecode import unidecode

import settings

from worldweatheronline import get_weather

class MeteoBot():
    is_bot_module = True
    oops = u"Wrong parameters, or service unreachable."

    DATE_REQUEST_CHOICES = ['current', 'today', 'tomorrow']
    COMMANDS = {
        'meteo':'meteo_handler',
        'weather':'meteo_handler',
        }


    # HANDLERS
    def meteo_handler(self, ev, *args):
        # defaults
        location = getattr(settings, 'DEFAULT_LOCATION', 'Paris,france')
        day = 'tomorrow'
        
        for arg in args:
            if arg == 'current':
                day = 'current'
            elif arg == 'today':
                day = 'today'
            elif arg == 'tomorrow':
                day = 'tomorrow'
            else:
                location = unidecode(arg)

        weather = get_weather(location, day)
        if not weather:
            return ev.target, self.oops

        if type(weather[2]) == tuple:
            temp = u'%s° to %s°' % (weather[2][0], weather[2][1])
        else:
            temp = u'%s°' % weather[2]
        return ev.target, u'%s (%s): %s, %s, precipitations: %smm' % (weather[0], datetime.strftime(weather[4], '%d %b'), weather[1], temp, weather[3])

    meteo_handler.help = u"!meteo CITY[,COUNTRY] [%s]" % '|'.join(DATE_REQUEST_CHOICES)
