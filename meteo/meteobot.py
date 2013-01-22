#! -*- coding: utf-8 -*-
from datetime import datetime
from unidecode import unidecode

from basebot import BaseCommand, BaseBotModule
import settings

from worldweatheronline import get_weather

class MeteoCommand(BaseCommand):
    NAME = "meteo"
    ALIASES = ["weather",]

    # custom
    DATE_REQUEST_CHOICES = ['current', 'today', 'tomorrow'] #TODO : weekend
    oops = u"Wrong parameters, or service unreachable."

    HELP = u"meteo CITY[,COUNTRY] [%s]" % '|'.join(DATE_REQUEST_CHOICES)

    def get_response(self):
        location = getattr(settings, 'DEFAULT_LOCATION', 'Paris,france')
        day = 'tomorrow'
        
        for arg in self.options:
            if arg == 'current':
                day = 'current'
            elif arg == 'today':
                day = 'today'
            elif arg == 'tomorrow':
                day = 'tomorrow'
            else:
                location = unidecode(arg)

        # TODO : this is blocking, is it a good idea ?
        weather = get_weather(location, day)
        if not weather:
            return self.oops

        if type(weather[2]) == tuple:
            temp = u'%s° to %s°' % (weather[2][0], weather[2][1])
        else:
            temp = u'%s°' % weather[2]
        return u'%s (%s): %s, %s, precipitations: %smm' % (weather[0], datetime.strftime(weather[4], '%d %b'), weather[1], temp, weather[3])

    

class MeteoModule(BaseBotModule):
    # TODO: save the default location by user

    COMMANDS = [ MeteoCommand ]        
