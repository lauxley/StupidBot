import json
import urllib2
from datetime import date, timedelta

import settings

METEO_URL = 'http://free.worldweatheronline.com/feed/weather.ashx?q={q}&format=json&num_of_days=2&key={api_key}'
API_KEY = settings.WORLDWEATHERONLINE_API_KEY

def _get_data(url):
    request = urllib2.Request(url, None, {'Accept-encoding': 'utf8'})
    try:
        response = urllib2.urlopen(request)
    except urllib2.URLError:
        return None
    result = response.read()
    return result

def get_weather(location, qdate='tomorow'):
    """
    date = [current|today|tomorow]

    { "data": 
    { "current_condition": 
    [ {
    "cloudcover": "75", 
    "humidity": "71", 
    "observation_time": "12:08 PM", 
    "precipMM": "0.0", 
    "pressure": "1015", 
    "temp_C": "10", 
    "temp_F": "50", 
    "visibility": "10", 
    "weatherCode": "116",  
    "weatherDesc": [ {"value": "Partly Cloudy" } ],  
    "weatherIconUrl": [ {"value": "http:\/\/www.worldweatheronline.com\/images\/wsymbols01_png_64\/wsymbol_0002_sunny_intervals.png" } ], 
    "winddir16Point": "WSW", 
    "winddirDegree": "240", 
    "windspeedKmph": "28", 
    "windspeedMiles": "17" } ],  
    "request": [ {"query": "Paris, France", "type": "City" } ],  
    "weather": [ 
    {"date": "2012-12-26", "precipMM": "1.5", "tempMaxC": "9", "tempMaxF": "49", "tempMinC": "7", "tempMinF": "44", "weatherCode": "116",  "weatherDesc": [ {"value": "Partly Cloudy" } ],  "weatherIconUrl": [ {"value": "http:\/\/www.worldweatheronline.com\/images\/wsymbols01_png_64\/wsymbol_0002_sunny_intervals.png" } ], "winddir16Point": "WSW", "winddirDegree": "243", "winddirection": "WSW", "windspeedKmph": "34", "windspeedMiles": "21" }, 
    {"date": "2012-12-27", "precipMM": "6.0", "tempMaxC": "11", "tempMaxF": "51", "tempMinC": "5", "tempMinF": "42", "weatherCode": "176",  "weatherDesc": [ {"value": "Patchy rain nearby" } ],  "weatherIconUrl": [ {"value": "http:\/\/www.worldweatheronline.com\/images\/wsymbols01_png_64\/wsymbol_0009_light_rain_showers.png" } ], "winddir16Point": "W", "winddirDegree": "263", "winddirection": "W", "windspeedKmph": "45", "windspeedMiles": "28" } 
    ] 
    }
    }
    """
    data = _get_data(METEO_URL.format(q=location, api_key=API_KEY))
    if data:
        try:
            jd = json.loads(data)['data']
            location = jd['request'][0]['query']
            if qdate == "current":
                root = jd['current_condition'][0]
                day = date.today()
            elif qdate == "today":
                root = jd['weather'][0]
                day = date.today()
            else:
                root = jd['weather'][1] # tomorrow
                day = date.today() + timedelta(days=1)

            # TODO: manage up to 5 days ahead
                
            weather = root['weatherDesc'][0]['value']
            precip = root['precipMM']
            if qdate ==  "current":
                temp = root['temp_C']
            else:
                temp = (root['tempMinC'], root['tempMaxC'])

            return (location, weather, temp, precip, day)

        except (ValueError, IndexError, KeyError), e:
            pass
    return None
    
