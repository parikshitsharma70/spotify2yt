import requests
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import time
from googleapiclient.errors import HttpError

# ---------- STEP 1: Authenticate to YouTube ----------
def get_authenticated_service():
    scopes = ["https://www.googleapis.com/auth/youtube"]
    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", scopes)
    credentials = flow.run_local_server(port=0)
    return build("youtube", "v3", credentials=credentials)

# ---------- STEP 2: Get Track Names from Spotify ----------
def get_spotify_track_names(token: str, playlist_id: str) -> list:
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Spotify error: {response.status_code} - {response.text}")

    data = response.json()
    items = data.get("tracks", {}).get("items", [])
    
    track_names = []
    for item in items:
        track = item.get("track")
        if track:
            name = track.get("name")
            artists = ', '.join(artist["name"] for artist in track.get("artists", []))
            full_name = f"{name} {artists}"
            track_names.append(full_name)

    return track_names

# ---------- STEP 3: Search for each track on YouTube ----------
def search_youtube_video_id(youtube, query):
    search_response = youtube.search().list(
        part="snippet",
        q=query,
        type="video",
        maxResults=1
    ).execute()

    items = search_response.get("items", [])
    if not items:
        return None

    return items[0]["id"]["videoId"]

# ---------- STEP 4: Create a new YouTube playlist ----------
def create_youtube_playlist(youtube, title, description="Created from Spotify tracks"):
    playlist = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": description
            },
            "status": {
                "privacyStatus": "private"
            }
        }
    ).execute()

    return playlist["id"]

def add_video_to_playlist(youtube, playlist_id, video_id, max_retries=5):
    for attempt in range(1, max_retries + 1):
        try:
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": video_id
                        }
                    }
                }
            ).execute()
            return  # Success
        except HttpError as e:
            if e.resp.status in [500, 503, 409]:
                wait_time = 2 ** attempt  # exponential backoff
                print(f"Retry {attempt}/{max_retries}: Temporary error ({e.resp.status}). Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"Failed to add video {video_id} due to unexpected error:")
                raise  # re-raise for unexpected errors
    print(f"Failed to add video {video_id} after {max_retries} retries.")

# ---------- MAIN ----------
if __name__ == "__main__":
    spotify_token = "$token"
    spotify_playlist_id = "0plEmZPnuHojzoAqdYDqZ6"

    # Step 1: Auth
    youtube = get_authenticated_service()

    # Step 2: Fetch tracks from Spotify
    track_names = get_spotify_track_names(spotify_token, spotify_playlist_id)

    # Step 3: Create playlist on YouTube
    playlist_id = create_youtube_playlist(youtube, "Alt")
    print(f"Created YouTube playlist: https://www.youtube.com/playlist?list={playlist_id}")

    # Step 4: Search and add videos
    for name in track_names:
        video_id = search_youtube_video_id(youtube, name)
        if video_id:
            add_video_to_playlist(youtube, playlist_id, video_id)
            print(f"Added: {name}")
        else:
            print(f"No YouTube result for: {name}")