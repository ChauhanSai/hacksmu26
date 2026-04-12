import urllib.request
import sys
from bs4 import BeautifulSoup
import csv
import ollama

AGE = "Infant"
GENDER = "N/A"

def download_html(url):
    """Downloads and returns the HTML code from the given URL."""
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"Error downloading {url}: {e}", file=sys.stderr)
        return None

def extract_elephant(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    overview_section = soup.find('div', class_='overview')

    if overview_section:
        # overview_section.find('div', class_='video')
        videos = overview_section.find_all('div', class_='mySlides')
        audios = overview_section.find_all('div', class_='grunt-audio')
        return videos, audios
    else:
        print("Could not find <div class='overview'>", file=sys.stderr)
        return None, None


def extract_video_content(video_element):
    # print(video_element)
    name = video_element.find('strong').text.strip()
    # print(name)
    context = video_element.find('em').text[9:-4].strip()
    # print(context)
    description = video_element.find('p', class_='descr').text
    description = description[description.find(context) + len(context) + 4:].lstrip()
    description = " ".join(description.split())
    # print(description)
    url = video_element.find('iframe')['src']
    url = "https://vimeo.com/" + str(url)[str(url).find("video/") + 6:]
    # print(url)
    return url, name, context, AGE, GENDER, description, "acoustic-vocal"

def extract_audio_content(audio_element, name):
    # print(audio_element)
    description = audio_element.find('p', class_='descr').text
    # print(description)
    url = audio_element.find('iframe')['src']
    # print(url)
    soundcloud_content = download_html(url)
    # print(soundcloud_content)
    soup = BeautifulSoup(soundcloud_content, 'html.parser')
    url = soup.find('link', rel='canonical')['href']
    # print(url)

    class_names = [
        "Advertisement & Attraction", "Affiliative", "Aggressive", "Ambivalent",
        "Attacking & Mobbing", "Attentive", "Avoidance", "Birth",
        "Calf Nourishment & Weaning", "Calf Reassurance & Protection",
        "Coalition Building", "Conflict & Confrontation", "Courtship", "Death",
        "Foraging & Comfort Technique", "Protest & Distress", "Lone & Object Play",
        "Maintenance", "Movement, Space & Leadership", "Novel & Idiosyncratic",
        "Social Play", "Submissive", "Vigilance"
    ]
    response = ollama.chat(model='llama3.2', messages=[
        { 'role': 'system', 'content': 'You are a classification assistant. You will be provided with a paragraph of text. Your task is to categorize the text into EXACTLY ONE of the following IDs: ' + str(class_names) },
        { 'role': 'user', 'content': f"Classify this text: {description}"},
    ])

    context = response['message']['content']
    for class_name in class_names:
        if class_name in context:
            context = class_name
            break

    return url, name, context, AGE, GENDER, description, "acoustic-vocal"

if __name__ == "__main__":
    urls = ['https://www.elephantvoices.org/elephant-ethogram/search-portal/behavior?id=129', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behavior?id=184', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behavior?id=189', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behavior?id=205', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behavior?id=330', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behavior?id=231', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behavior?id=325', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behavior?id=245', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behavior?id=271', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behaviorconstellation?id=3', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behaviorconstellation?id=8', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behaviorconstellation?id=9', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behaviorconstellation?id=11', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behaviorconstellation?id=17', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behaviorconstellation?id=104', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behaviorconstellation?id=28', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behaviorconstellation?id=34', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behaviorconstellation?id=107', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behaviorconstellation?id=100', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behaviorconstellation?id=105', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behaviorconstellation?id=102', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behaviorconstellation?id=101', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behaviorconstellation?id=68', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behaviorconstellation?id=70', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behaviorconstellation?id=73', 'https://www.elephantvoices.org/elephant-ethogram/search-portal/behaviorconstellation?id=74']
    RESET = False
    if RESET:
        open("scrape.csv", mode='w', newline='', encoding='utf-8').close()

    for target_url in urls:
        html_content = download_html(target_url)

        if html_content:
            videos, audios = extract_elephant(html_content)

            with open("scrape.csv", mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                this_name = ""

                for video in videos:
                    url, name, context, age, gender, description, mode = extract_video_content(video)
                    print((url, name, context, age, gender, description, mode))
                    this_name = name
                    writer.writerow([url, name, context, age, gender, description, mode])

                if this_name == "":
                    this_name = input("No videos, enter name for audios: ")
                for audio in audios:
                    url, name, context, age, gender, description, mode = extract_audio_content(audios[0], this_name)
                    print((url, name, context, age, gender, description, mode))
                    writer.writerow([url, name, context, age, gender, description, mode])
