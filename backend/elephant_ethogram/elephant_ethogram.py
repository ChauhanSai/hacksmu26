import yt_dlp
import csv
import os

os.makedirs('data', exist_ok=True)

def download_data(url, title=None):
    if title is None:
        title = '%(title)s'
    ydl_opts = {
        'format': 'bestaudio/best',   # Audio only
        'outtmpl': os.path.join('data', title + '.%(ext)s'),  # Save to data folder
        'cookiesfrombrowser': ('chrome',),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        print("Download complete")
    except Exception as e:
        print(f"An error occurred: {e}")

# input = [("url", "name", "context", "age", "gender", "description", "mode")]
input = [("https://vimeo.com/360485669", "name", "context", "age", "gender", "description", "mode")]
inputCsv = "input.csv"

if os.path.isfile(inputCsv):
    input = []
    with open(inputCsv, mode='r', encoding='utf-8') as infile:
        reader = csv.reader(infile)
        next(reader, None)  # Skip header row
        for row in reader:
            if len(row) >= 7:
                input.append(tuple(row[:7]))

freq = {}
downloaded_urls = {}

outputCsv = 'data.csv'
file_exists = os.path.isfile(outputCsv)

with open(outputCsv, mode='a', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    if not file_exists:
        writer.writerow(['file_name', 'name', 'context', 'age', 'gender', 'description', 'url', 'mode'])

    for tuple in input:
        print(tuple)
        url, context, name, mode, age, gender, description = tuple

        if url in downloaded_urls:
            title = downloaded_urls[url]
            print(f"Skipped download (duplicate URL), reusing file: {title}")
            writer.writerow([title, name, context, mode, age, gender, url, description])
            continue

        if name in freq:
            freq[name] += 1
        else:
            freq[name] = 1

        title = f'{freq[name]:02d}_{name}_{context}'
        download_data(tuple[0], title)
        print(f"Downloaded: {title}\n")

        downloaded_urls[url] = title

        writer.writerow([title, name, context, age, gender, description, url, mode])
