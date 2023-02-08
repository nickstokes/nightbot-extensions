import requests
import os
import json
import logging

from datetime import datetime
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
        if isinstance(stream_key, list):

        self.id = stream_key.get("id")
        self.nick = stream_key.get("nick")
        self.discord_id = stream_key.get("discord_id")
    
    def get_active_key():
        r = requests.get(f'{KEYBOT_URL}/key/active', auth=(KEYBOT_USER, KEYBOT_PASS))
        if r.status_code == requests.codes.ok:
            return StreamKey(r.text)
        else:
            return None
    
    def get_key_by_id(key_id):
        r = requests.get(f'{KEYBOT_URL}/key/', auth=(KEYBOT_USER, KEYBOT_PASS))
        keys = r.json()


class StreamerInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stream_key_id = db.Column(db.String(36), primary_key=False, unique=True)
    discord_id = db.Column(db.BigInteger, nullable=True)
    info_text = db.Column(db.Unicode(400), nullable=False)

    def __init__(self, stream_key_id=None, info_text=None, discord_id=None):
        self.stream_key_id=stream_key_id
        self.info_text=info_text
        self.discord_id=discord_id

    @classmethod
    def from_stream_key(stream_key, discord_fallback=False):
         # try getting info from exact stream key.
        streamer_info = StreamerInfo.get_instance_by_stream_key_id(stream_key.id)
        # attempt lookup using discord_id if match from key not found.
        if streamer_info is None and discord_fallback and stream_key.discord_id:
            streamer_info = StreamerInfo.get_instance_by_stream_key_id(stream_key.discord_id).scalar()
        return streamer_info
    
    @classmethod
    def from_stream_key_id(stream_key_id):
        streamer_info = db.session.execute(db.select(StreamerInfo).where(StreamerInfo.stream_key_id==stream_key_id)).scalar()
        return streamer_info
    
    @classmethod
    def from_discord_id(discord_id):
        streamer_info = db.session.execute(db.select(StreamerInfo).where(StreamerInfo.discord_id==discord_id)).scalar()
        return streamer_info


@app.get("/api/nbe/streamer-info/active")
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


@app.post("/api/nbe/streamer-info")
def post_streamer_info():
    try:
        streamer_data = request.get_json(silent=True)
        existing_streamer_info = None
        if 'stream_key_id' in streamer_data:
            existing_streamer_info = StreamerInfo.from_stream_key_id(streamer_data['stream_key_id'])
        if not existing_streamer_info and 'discord_id' in streamer_data:
            existing_streamer_info = StreamerInfo.from_discord_id(streamer_data['discord_id'])

        stream_key = StreamKey.get_active_key()
        streamer_info = StreamerInfo.from_stream_key(stream_key, discord_fallback=True)
        if streamer_info:
            return streamer_info.info_text
        else:
            return "No info found for current streamer"
    except:
        logging.exception("Error getting streamer info")
        return "Sorry, there was a problem getting the streamer info"


@app.route("/api/nbe/add-streamer-info") # this isn't done as a 'POST' request to /streamer-info because NightBot can only sent GET requests.
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
            streamer_info = StreamerInfo(stream_key.id, stream_key.discord_id, streamer_text)
            db.session.add(streamer_info)
            db.session.commit()
        return f"The info has been saved for the current streamer, you can ask me to recall it by saying !who."
    except:
        logging.exception("Error saving streamer info")
        return "Sorry, there was a problem saving the streamer info."

@app.route("/ems-youtube-chat")
def redirect_to_youtube_chat():
    