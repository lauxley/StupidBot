#! -*- coding: utf-8 -*-
from datetime import datetime
from unidecode import unidecode

from basebot import BaseAuthCommand, BaseBotModule
import settings

from worldweatheronline import get_weather

class MeteoCommand(BaseAuthCommand):
    NAME = "meteo"
    ALIASES = ["weather",]

    # custom
    DATE_REQUEST_CHOICES = ['current', 'today', 'tomorrow', 'weekend']
    oops = u"Wrong parameters, or service unreachable."

    HELP = u"meteo CITY[,COUNTRY] [%s] - Note that weekend is only available from Tuesday to Friday." % '|'.join(DATE_REQUEST_CHOICES)

    def get_user_from_line(self):
        return self.ev.source.nick

    def get_response(self):
        user = self.bot.auth_module.get_username(self.user) 
        
        location = self.module.user_location_map.get(user, None) or getattr(settings, 'DEFAULT_LOCATION', 'Paris,france')
        day = 'tomorrow'
        
        for arg in self.options:
            if arg in ['current', 'today', 'tomorrow', 'weekend']:
                day = arg
            else:
                location = unidecode(arg)

        self.module.user_location_map[user] = location

        # TODO : this is blocking, is it a good idea ?
        weather, error = get_weather(location, day)
        if not weather:
            if error:
                self.module.bot.error_logger.error("Cannot fetch the weather : %s" % error)
            return self.oops

        if type(weather[2]) == tuple:
            temp = u'%s° to %s°' % (weather[2][0], weather[2][1])
        else:
            temp = u'%s°' % weather[2]
        return u'%s (%s): %s, %s, precipitations: %smm' % (weather[0], datetime.strftime(weather[4], '%d %b'), weather[1], temp, weather[3])

    

class MeteoModule(BaseBotModule):
    # TODO: save the default location by user

    COMMANDS = [ MeteoCommand ]        
    
    # used to remember each user choice
    user_location_map = {}
    
