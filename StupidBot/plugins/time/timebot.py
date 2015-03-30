import pytz
from datetime import datetime
from dateutil.parser import parse

from basebot import BaseCommand, BaseBotPlugin, BadCommandLineException


class TimeCommand(BaseCommand):
    NAME = "time"
    ALIASES = ['t',]
    HELP = u"time [[TIME|FROM_TIMEZONE] [TO_TIMEZONE]] - Will (attempt to) convert TIME from FROM_TIMEZONE to TO_TIMEZONE, TIME defaults to the local time and TO_TIMEZONE to CET (== GMT+1)."

    DEFAULT_TIMEZONE = 'CET'
    OUTPUT_FORMAT = '%Hh%M'

    def parse_options(self):
        try:
            nbopts = len(self.options)
            if nbopts == 0:
                self.date = datetime.now()
                self.fromtz = pytz.timezone(self.DEFAULT_TIMEZONE)
                self.totz = pytz.timezone(self.DEFAULT_TIMEZONE)
            else:
                try:
                    if nbopts == 1:
                        self.totz = pytz.timezone(self.options[0])
                        self.fromtz = pytz.timezone(self.DEFAULT_TIMEZONE)
                    else:
                        self.fromtz = pytz.timezone(self.options[0])
                        
                    self.date = datetime.now()
                except pytz.UnknownTimeZoneError:
                    # if it's not a timezone, let's hope it's a time
                    self.date = parse(self.options[0])
                    self.fromtz = pytz.timezone(self.DEFAULT_TIMEZONE)

                if len(self.options) == 2:
                    self.totz = pytz.timezone(self.options[1])
                
        except ValueError:
            raise BadCommandLineException(u'Invalid time format. Try something like "15h32" or "15:32".')

        except pytz.UnknownTimeZoneError:
            raise BadCommandLineException(u'Unknow time zone. Try something like "GMT", "Europe/Paris".')

    def get_response(self):
        try:
            aware = self.fromtz.localize(self.date)  # the date is now tz aware
        except ValueError:
            # the date was already aware
            aware = self.date
        converted = aware.astimezone(self.totz)
        return converted.strftime(self.OUTPUT_FORMAT)


class TimePlugin(BaseBotPlugin):
    COMMANDS = [TimeCommand,]
