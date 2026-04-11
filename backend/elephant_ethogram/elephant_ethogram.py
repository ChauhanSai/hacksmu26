import yt_dlp

def download_vimeo_video(url):
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',   # Merges best video and audio
        'outtmpl': '%(title)s.%(ext)s',         # Name file after the video title
        'cookiesfrombrowser': ('chrome',),
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        print("Download complete")
    except Exception as e:
        print(f"An error occurred: {e}")

# Example usage
vimeo_url = 'https://vimeo.com/360485669'
download_vimeo_video(vimeo_url)