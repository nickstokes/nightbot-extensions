Nightbot Extensions for EMS
-------------------------

This is a simple API to extend what the Nightbot youtube chatbot can do.
Nightbot supports [fetching text and json responses from a GET request](https://docs.nightbot.tv/variables/urlfetch)

This flask app interfaces with other EMS systems like stream-key-manage so that we can show extra info in the youtube chat.

Currently, the only feature is an endpoint that can save and retrieve info text for the current streamer. 
This could replace the individual !artistname commands with a single command like !whoisplaying.

How it works
------------

 - Get current streamer info

    ```
    GET /api/nbe/get-streamer-info
    ```

This will attempt to look up the current streamer key from the /api/key/active endpoint on stream-key-manage,
then check to see if it has any streamer info text stored locally. If it can't find any streamer info assigned to the key, it will attempt to 
see if there are any keys with the current streamers discord id, and return that instead. This is so that discord users that have multiple keys
can have different artist names and social media addresses. The endpoint responds in plain text with the streamer infomation if found. If no info was 
found, nobody is streaming, or there was an error, plaintext messages are returned indicating as such. 


- Save current streamer info

    ```
    GET /api/nbe/add-streamer-info?text=streamer%20info%20goes%20here.
    ```

A GET request to this endpoint with a querystring that has a 'text' attribute will save the URL Encoded text under the current live streamer's stream key.  
This is done in a GET request instead of a POST request because Nightbot doesn't support POST requests. This could be used in a command like "!saveinfo Check out artistname's instagram here". The endpoint responds in plain text whether the infomation is successfully saved.

There is no authentication, so auth will need to be added at the server level and saved in the Nightbot commands.  
Nightbot can also restrict certain commands so that everyone can access the !whoisplaying command, but only mods can access the !saveinfo command.  

- Get all streamer info

    ```
    GET /api/nbe/streamer-info
    ```

This endpoint will return json representations of all current streamer info


- Save streamer info

    ```
    PUT/POST /api/nbe/streamer-info
    ```

This endpoint will accept a json object with a valid 'stream_key_id' and 'info_text' and save streamer info for that key.
The endpoint will return a json representation of the updated streamer info.

e.g. {"stream-key-id":  "c0507a93-d3b0-4b8b-b939-6e951600507a9f051d",
    "info_text": "Check out this artist at these links!!!!"
}}


Todo:
 - Requesting and saving streamer info other than the currently active streamer on nightbot.
 - Allow users to set/edit their own text using a discord bot (waffle/nightbot?) 

Installing
--------

To run this locally, you will need python and pip.  

In the project directory you can either use `pip install -e .` or `pip install -r requirements`.  
You will need to create a `.env` file with the API address, Auth, and a filename for the SQLite database.  
Before running you will need to initialize the SQLite database with the `flask db upgrade`.
To run a test/development server, use the `flask run` command.
