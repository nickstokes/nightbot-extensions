import requests
import os
import logging

from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify
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
    def __init__(self, stream_key: object):
            self.id = stream_key.get("id")
            self.nick = stream_key.get("nick")
            self.discord_id = stream_key.get("discord_id")
    
    @classmethod
    def active_key(cls):
        r = requests.get(f'{KEYBOT_URL}/key/active', auth=(KEYBOT_USER, KEYBOT_PASS))
        if r.status_code == requests.codes.ok:
            return StreamKey(r.json())
        elif r.status_code == 404:
            return None
        else:
            raise LookupError("Error retrieving active key")
    
    @classmethod
    def from_id(cls, key_id: str):
        r = requests.get(f'{KEYBOT_URL}/key/{key_id}', auth=(KEYBOT_USER, KEYBOT_PASS))
        if r.status_code == requests.codes.ok:
            return StreamKey(r.json())
        elif r.status_code == 404:
            return None
        else:
            raise LookupError("Error retrieving specific key")


class StreamerInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stream_key_id = db.Column(db.String(36), primary_key=False, unique=True)
    discord_id = db.Column(db.BigInteger, nullable=True)
    info_text = db.Column(db.Unicode(400), nullable=False)

    def __init__(self, stream_key_id: str=None, info_text: str=None, discord_id=None):
        self.stream_key_id=stream_key_id
        self.info_text=info_text
        self.discord_id=discord_id
    
    @property
    def as_dict(self):
       return {c.name: getattr(self, c.name) for c in self.__table__.columns}

    @classmethod
    def from_stream_key(cls, stream_key: StreamKey, discord_fallback: bool=False):
         # try getting info from exact stream key.
        streamer_info = StreamerInfo.from_stream_key_id(stream_key.id)
        # attempt lookup using discord_id if match from key not found.
        if streamer_info is None and discord_fallback and stream_key.discord_id:
            streamer_info = StreamerInfo.from_discord_id(stream_key.discord_id)
        # if not found, create a new one with the stream key
        if streamer_info is None:
            streamer_info = StreamerInfo(stream_key_id=stream_key.id, discord_id=stream_key.discord_id)
        return streamer_info
    
    @classmethod
    def from_stream_key_id(cls, stream_key_id):
        streamer_info = db.session.execute(db.select(StreamerInfo).where(StreamerInfo.stream_key_id==stream_key_id)).scalar()
        return streamer_info
    
    @classmethod
    def from_discord_id(cls, discord_id):
        streamer_info = db.session.execute(db.select(StreamerInfo).where(StreamerInfo.discord_id==discord_id)).scalar()
        return streamer_info

@app.get("/api/nbe/get-streamer-info") # plain text response for NightBot
def get_streamer_info():
    try:
        active_stream_key = StreamKey.active_key()
        if not active_stream_key:
            return "There is nobody currently streaming"
        streamer_info = StreamerInfo.from_stream_key(stream_key=active_stream_key, discord_fallback=True)
        if streamer_info and streamer_info.info_text:
            return streamer_info.info_text
        else:
            return f"No info found for current streamer"
    except:
        logging.exception("Error getting streamer info")
        return "Sorry, there was a problem getting streamer info"


@app.get("/api/nbe/add-streamer-info") # this isn't done as a 'PUT/POST' request to /streamer-info because NightBot can only sent GET requests.
def add_streamer_info():
    streamer_text = request.args.get(key='text')
    if not streamer_text:
        return "Please include the artist info you would like to save."
    try:
        stream_key = StreamKey.active_key()
        if not stream_key:
            return "There doesn't seem to be anyone streaming right now."
        streamer_info = StreamerInfo.from_stream_key(stream_key=stream_key, discord_fallback=False)
        streamer_info.info_text = streamer_text
        streamer_info = db.session.merge(streamer_info)
        db.session.commit()
        return f"The info has been saved for the current streamer."
    except:
        logging.exception("Error saving streamer info")
        return "Sorry, there was a problem saving the streamer info."


@app.route("/api/nbe/streamer-info", methods=['PUT', 'POST'])  # standard json endpoint for put requests
def put_streamer_info():
    try:
        request_data = request.get_json(silent=True)
        if not request_data.get('stream_key_id') or not request_data.get('info_text'):
            return 'Please supply stream_key_id and info_text', 400

        stream_key = StreamKey.from_id(request_data.get('stream_key_id'))
        if not stream_key:  # return 404 if not found.
            return "Stream key not found", 404

        streamer_info = StreamerInfo.from_stream_key(stream_key)
        streamer_info.info_text = request_data.get('info_text')
        streamer_info = db.session.merge(streamer_info)
        db.session.commit()
        return jsonify(streamer_info.as_dict)
    except:
        logging.exception("Error while streamer info")
        return "Sorry, there was a problem getting the streamer info", 500


@app.get("/api/nbe/streamer-info") # standard json endpoint
def get_all_streamer_info():
    try:
        all_streamers = list(db.session.execute(db.select(StreamerInfo)).scalars())
        return jsonify([streamer_info.as_dict for streamer_info in all_streamers])
    except:
        logging.exception("Error getting streamer info")
        return "Sorry, there was a problem getting streamer info"