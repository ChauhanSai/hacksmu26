import urllib.request
import sys
from bs4 import BeautifulSoup
import csv

def extract_urls(html_content):
    urls = []

    soup = BeautifulSoup(html_content, 'html.parser')
    #container = soup.find('div', class_='container navcnt')

    a = soup.find_all('a')

    for href in a:
        url = href.get('href')
        if "behavior" in url:
            urls.append("https://www.elephantvoices.org" + url)
    print(urls)

    return urls

if __name__ == "__main__":
    html = """
<h3>Behaviors</h3>
<a href="/elephant-ethogram/search-portal/behavior?id=3">Alarmed-Trumpet (5)</a>
, 
<a href="/elephant-ethogram/search-portal/behavior?id=7">As-Touched-Rumble (3)</a>
, 
<a href="/elephant-ethogram/search-portal/behavior?id=339">Bark (0)</a>
, 
<a href="/elephant-ethogram/search-portal/behavior?id=10">Baroo-Rumble (4)</a>
, 
<a href="/elephant-ethogram/search-portal/behavior?id=12">Begging-Rumble (7)</a>
, 
<a href="/elephant-ethogram/search-portal/behavior?id=329">Blow (2)</a>
, 
<a href="/elephant-ethogram/search-portal/behavior?id=59">Cry (2)</a>
, 
<a href="/elephant-ethogram/search-portal/behavior?id=129">Husky-Cry (20)</a>
, 
<a href="/elephant-ethogram/search-portal/behavior?id=184">Play-Trumpet (6)</a>
, 
<a href="/elephant-ethogram/search-portal/behavior?id=189">Pulsated-Trumpet (11)</a>
, 
<a href="/elephant-ethogram/search-portal/behavior?id=205">Roar (24)</a>
, 
<a href="/elephant-ethogram/search-portal/behavior?id=330">Rumble (0)</a>
, 
<a href="/elephant-ethogram/search-portal/behavior?id=231">Separated-Rumble (4)</a>
, 
<a href="/elephant-ethogram/search-portal/behavior?id=325">Sneeze (2)</a>
, 
<a href="/elephant-ethogram/search-portal/behavior?id=245">Snort (8)</a>
, 
<a href="/elephant-ethogram/search-portal/behavior?id=271">Trumpet-Blast (17)</a>
, 
<br>
<b><i>16 entries matches your search</i></b>
<h3>Behavioral Constellations</h3>
<a href="/elephant-ethogram/search-portal/behaviorconstellation?id=3">Apprehensive (1)</a>
, 
<a href="/elephant-ethogram/search-portal/behaviorconstellation?id=8">Bow-Neck-Charge (4)</a>
, 
<a href="/elephant-ethogram/search-portal/behaviorconstellation?id=9">Bunching (5)</a>
, 
<a href="/elephant-ethogram/search-portal/behaviorconstellation?id=11">Charge (15)</a>
, 
<a href="/elephant-ethogram/search-portal/behaviorconstellation?id=17">Conciliation (11)</a>
, 
<a href="/elephant-ethogram/search-portal/behaviorconstellation?id=104">Cry-Rumble (6)</a>
, 
<a href="/elephant-ethogram/search-portal/behaviorconstellation?id=28">Floppy-Running (11)</a>
, 
<a href="/elephant-ethogram/search-portal/behaviorconstellation?id=34">Group-Charge (6)</a>
, 
<a href="/elephant-ethogram/search-portal/behaviorconstellation?id=107">Husky-Cry-Roar-Rumble (0)</a>
, 
<a href="/elephant-ethogram/search-portal/behaviorconstellation?id=100">Roar-Rumble (2)</a>
, 
<a href="/elephant-ethogram/search-portal/behaviorconstellation?id=105">Rumble-Cry-Rumble (0)</a>
, 
<a href="/elephant-ethogram/search-portal/behaviorconstellation?id=102">Rumble-Roar (3)</a>
, 
<a href="/elephant-ethogram/search-portal/behaviorconstellation?id=101">Rumble-Roar-Rumble (3)</a>
, 
<a href="/elephant-ethogram/search-portal/behaviorconstellation?id=68">Solicit-Food (6)</a>
, 
<a href="/elephant-ethogram/search-portal/behaviorconstellation?id=70">Solicit-Help (0)</a>
, 
<a href="/elephant-ethogram/search-portal/behaviorconstellation?id=73">Solicit-Suckling (13)</a>
, 
<a href="/elephant-ethogram/search-portal/behaviorconstellation?id=74">Sparring (27)</a>
    """

    urls = extract_urls(html)
