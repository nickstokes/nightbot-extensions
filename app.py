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
            #"cooldown": iso_date,
            "priority": int,
            "state": str,
            #"pending_cooldown": iso_date,
            #"live_since": iso_date,
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
        r = requests.get(KEYBOT_URL + '/key/active', auth=(KEYBOT_USER, KEYBOT_PASS))
        if r.status_code == requests.codes.ok:
            return StreamKey(r.text)
        elif r.status_code == 404:
            return None
        else:
            raise LookupError("Error retrieving active key")


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


@app.route("/api/nbe/get-streamer-info")
def get_streamer_info():
    try:
        stream_key = StreamKey.get_active_key()
        if stream_key is None:
            return "Hmm, it looks like nobody is streaming right now."
        streamer_info = StreamerInfo.get_instance_by_stream_key(stream_key, discord_fallback=True)
        if streamer_info:
            return streamer_info.info_text
        else:
            return "I couldn't fine any info for the current streamer."
    except:
        logging.exception("Error getting streamer info")
        return "Sorry, there was a problem getting streamer info."


@app.route("/api/nbe/add-streamer-info") # this isn't done as a 'POST' request to /streamer-info because NightBot can only sent GET requests.
def add_streamer_info():
    try:
        streamer_text = request.args.get(key='text')
        if not streamer_text:
            return "Please include the artist info you would like to save."
        stream_key = StreamKey.get_active_key()
        if stream_key is None:
            return "Hmm, it looks like nobody is streaming right now."
        streamer_info = StreamerInfo.get_instance_by_stream_key(stream_key, discord_fallback=False)
        if streamer_info is not None: # if existing streamer info us found, update existing record.
            streamer_info.discord_id = stream_key.discord_id
            streamer_info.info_text = streamer_text
            db.session.commit()
        else: # otherwise create new one.
            streamer_info = StreamerInfo()
            streamer_info.stream_key_id = stream_key.id
            streamer_info.discord_id = stream_key.discord_id
            streamer_info.info_text = streamer_text
            db.session.add(streamer_info)
            db.session.commit()
        return f"Done! Info has been saved for the current streamer."
    except:
        logging.exception("Error saving streamer info")
        return "Sorry, there was a problem saving the streamer info."
