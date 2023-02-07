import requests
import os
import json
import logging

from datetime import datetime, timezone
from dotenv import load_dotenv
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from schema import Schema, Use, Optional

logging.basicConfig(handlers=[logging.FileHandler('nbe.log'), logging.StreamHandler()],
                    format='%(asctime)s %(levelname)s: %(message)s',
                    level=logging.INFO)

load_dotenv()
KEYBOT_URL = os.environ["NBE_KEYBOT_URL"]
KEYBOT_USER = os.environ["NBE_KEYBOT_USER"]
KEYBOT_PASS = os.environ["NBE_KEYBOT_PASS"]
DB_FILE = os.environ["NBE_DB_FILE"]
YOUTUBE_API_KEY = os.environ["NBE_YOUTUBE_API_KEY"]
YOUTUBE_CHANNEL_ID = os.environ["NBE_YOUTUBE_CHANNEL_ID"]


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_FILE}"
db = SQLAlchemy(app)
migrate = Migrate(app, db)


class StreamKey():
    iso_date = Use(datetime.fromisoformat)
    stream_key_schema = Schema(
        {
            "id": str,
            "cooldown": iso_date,
            "priority": int,
            "state": str,
            "pending_cooldown": iso_date,
            "live_since": iso_date,
            Optional("nick"): str,
            Optional("discord_id"): Use(int)
        },
            ignore_extra_keys=True
    )

    def __init__(self, stream_key_json):
        stream_key = json.loads(stream_key_json)
        self.stream_key_schema.validate(stream_key)
        self.id = stream_key.get("id")
        self.nick = stream_key.get("nick")
        self.discord_id = stream_key.get("discord_id")
    
    def get_active_key():
        r = requests.get(KEYBOT_URL, auth=(KEYBOT_USER, KEYBOT_PASS))
        if r.status_code == requests.codes.ok:
            return StreamKey(r.text)
    
    def __repr__(self):
        return f"{self.id[0:4]}..{self.id[-4:]}"


class StreamerInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stream_key_id = db.Column(db.String(36), primary_key=False, unique=True)
    discord_id = db.Column(db.BigInteger, nullable=True)
    info_text = db.Column(db.Unicode(400), nullable=False)

    def get_instance_by_stream_key(stream_key, discord_fallback=False):
         # try getting info from exact stream key.
        streamer_info = db.session.execute(db.select(StreamerInfo).where(StreamerInfo.stream_key_id==stream_key.id)).scalar()
        # attempt lookup using discord_id if match from key not found.
        if streamer_info is None and discord_fallback and stream_key.discord_id:
            streamer_info = db.session.execute(db.select(StreamerInfo).where(StreamerInfo.discord_id==stream_key.discord_id)).scalar()
        return streamer_info


class StreamMarker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    marker_datetime_utc = db.Column(db.DateTime(), nullable=False)
    stream_key_id = db.Column(db.String(36), nullable=True)
    stream_key_nick = db.Column(db.String(100), nullable=True)
    stream_key_dicord_id = db.Column(db.BigInteger(), nullable=True)
    video_id = db.Column(db.String(15), nullable=True)
    offset_secs = db.Column(db.Integer(), nullable=True)
    marker_text = db.Column(db.String(400), nullable=True)
    

    def __init__(self, marker_datetime_utc, marker_text, stream_key, video_id, offset_seconds):
        self.marker_datetime_utc = marker_datetime_utc
        self.marker_text = marker_text
        self.stream_key_id = stream_key.id
        self.stream_key_nick = stream_key.nick
        self.stream_key_discord_id = stream_key.discord_id
        self.video_id = video_id
        self.offset_seconds = int(offset_seconds)

    def __str__(self):
        return f"https://youtu.be/{self.video_id}?t={self.offset_seconds}"

@app.route("/api/nbe/marker/add")
def save_stream_marker():
    logging.info("Stream marker requested")
    try:
        stream_key = StreamKey.get_active_key()
        timenow = datetime.now(timezone.utc)
        marker_text = request.args.get(key='text')
        r = requests.get(f"https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={YOUTUBE_CHANNEL_ID}&eventType=live&type=video&key={YOUTUBE_API_KEY}")
        stream_info = r.json()
        stream_start = datetime.fromisoformat(stream_info['items'][0]['snippet']['publishTime'])
        offset_seconds = (timenow-stream_start).total_seconds()
        stream_video_id = stream_info['items'][0]['id']['videoId']
        marker = StreamMarker(timenow, marker_text, stream_key, stream_video_id, offset_seconds)
        db.session.add(marker)
        db.session.commit()
        return str(marker)
    except:
        return "Sorry, something went wrong saving the marker."


@app.route("/api/nbe/streamer")
def get_streamer_info():
    try:
        stream_key = StreamKey.get_active_key()
        streamer_info = StreamerInfo.get_instance_by_stream_key(stream_key, discord_fallback=True)
        if streamer_info:
            return streamer_info.info_text
        else:
            return "No info found for current streamer"
    except:
        logging.exception("Error getting streamer info")
        return "Sorry, there was a problem getting streamer info"


@app.route("/api/nbe/streamer/add") # this isn't done as a 'POST' request to /streamer-info because NightBot can only sent GET requests.
def add_streamer_info():
    streamer_text = request.args.get(key='text')
    if not streamer_text:
        return "Please include the artist info you would like to save."
    try:
        stream_key = StreamKey.get_active_key()
        streamer_info = StreamerInfo.get_instance_by_stream_key(stream_key, discord_fallback=False)
        if streamer_info is not None: # if existing streamer info not found, create new one.
            streamer_info.discord_id = stream_key.discord_id
            streamer_info.info_text = streamer_text
            db.session.commit()
        else: # otherwise update existing record.
            streamer_info = StreamerInfo()
            streamer_info.stream_key_id = stream_key.id
            streamer_info.discord_id = stream_key.discord_id
            streamer_info.info_text = streamer_text
            db.session.add(streamer_info)
            db.session.commit()
        return f"That info has been saved for the current streamer, you can ask me to recall it by saying !who."
    except:
        logging.exception("Error saving streamer info")
        return "Sorry, there was a problem saving the streamer info."
