import requests

def get_weather(city):
    url = f"https://wttr.in/{city}?format=3" # OUTPUT WILL BE IN ONE LINE
    #url = f"https://wttr.in/{city}?format=j1"  FOR FULL INFO ONLY. OUTPUT WILL BE ARROUND 1100 LINES OF RAW JASON 
    response = requests.get(url)
    return response.text
