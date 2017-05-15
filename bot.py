# -*- coding: UTF-8 -*-
import os
import difflib
import json
from urlparse import urlparse
import psycopg2
from pyee import EventEmitter
from flask import Flask, request, make_response
from slackclient import SlackClient

SLACK_VERIFICATION_TOKEN = os.environ["SLACK_VERIFICATION_TOKEN"]
SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
CLIENT = SlackClient(SLACK_BOT_TOKEN)

url = urlparse(os.environ["DATABASE_URL"])
conn = psycopg2.connect(
    database=url.path[1:],
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=url.port
)
cur = conn.cursor()

class SlackServer(Flask):
    def __init__(self, verification_token, endpoint, emitter):
        Flask.__init__(self, __name__)
        self.verification_token = verification_token

        @self.route(endpoint, methods=['GET', 'POST'])
        def event():
            # If a GET request is made, return 404.
            if request.method == 'GET':
                return make_response("These are not the slackbots you're looking for.", 404)

            # Parse the request payload into JSON
            event_data = json.loads(request.data)

            # Echo the URL verification challenge code
            if "challenge" in event_data:
                return make_response(
                    event_data.get("challenge"), 200, {"content_type": "application/json"}
                )

            # Parse the Event payload and emit the event to the event listener
            if "event" in event_data:
                # Verify the request token
                request_token = event_data.get("token")
                if self.verification_token != request_token:
                    emitter.emit('error', 'invalid verification token')
                    message = "Request contains invalid Slack verification token: %s\n" \
                              "Slack adapter has: %s" % (request_token, self.verification_token)
                    return make_response(message, 403)

                event_type = event_data["event"]["type"]
                emitter.emit(event_type, event_data)
                return make_response("", 200)

class SlackEventAdapter(EventEmitter):
    def __init__(self, verification_token, endpoint="/slack/events"):
        EventEmitter.__init__(self)
        self.verification_token = verification_token
        self.server = SlackServer(verification_token, endpoint, self)
    def start(self, port=None, debug=False):
        self.server.run(host='0.0.0.0', port=port)

slack_events_adapter = SlackEventAdapter(SLACK_VERIFICATION_TOKEN, endpoint="/slack_events")

def h_help():
    '''gets all terms from the database'''
    cur.execute("SELECT term FROM horace")
    terms = cur.fetchall()
    terms.sort()
    terms = '; '.join([i[0] for i in terms])
    return terms

def admin():
    '''returns admin message'''
    admin_m = '''"horace add entry term : definiton" adds a new item to the style guide. There has to be a space on either side of the :.
                "horace overwrite term : definition" changes the definiton of an existing term. Again, space on either side.
                Only use these in direct messages with me! The style guide will get messy if everyone knows how to change it.'''
    return admin_m

def add_entry(entry):
    '''adds entry to database'''
    text = entry.split(' ')
    text = text[3:]
    term = ' '.join(text[0:text.index(':')])
    definition = ' '.join(text[text.index(':')+1:])
    term.lower()
    cur.execute("SELECT * FROM horace WHERE term=%s", (term,))
    if len(cur.fetchall()) != 0:
        message = 'I already have an entry for %s. Use "horace overwrite term : new definiton" if you really want to change it.' % term
    else:
        cur.execute("INSERT INTO horace VALUES (%s, %s)", (term, definition))
        conn.commit()
        message = 'I added %s to the style guide, with definition %s.' % (term, definition)
    return message

def overwrite(entry):
    '''overwrites existing entry'''
    text = entry.split(' ')
    text = text[2:]
    term = ' '.join(text[0:text.index(':')])
    definition = ' '.join(text[text.index(':')+1:])
    term.lower()
    cur.execute("UPDATE horace SET definition=%s WHERE term=%s", (definition, term))
    conn.commit()
    message = 'I added %s to the style guide, with definition %s.' % (term, definition)
    return message

def delete(entry):
    '''delete entry from database'''
    text = entry.split(' ')
    text = ' '.join(text[2:])
    cur.execute("DELETE FROM horace WHERE term=%s", (text,))
    conn.commit()
    message = 'I deleted %s from the style guide.' % text
    return message

def lookup(entry):
    '''Get definition from database'''
    text = entry.split(' ')
    text.remove('Horace')
    text = ' '.join(text).lower()
    cur.execute("SELECT definition FROM horace WHERE term=%s", (text,))
    response = cur.fetchall()
    if len(response) != 0:
        message = response[0][0]
    else:
        cur.execute("SELECT term FROM horace")
        keys = cur.fetchall()
        keys = [i[0] for i in keys]
        suggestions = difflib.get_close_matches(text, keys)
        for i in keys:
            if text in i:
                suggestions.append(i)
        suggestions = [i for i in suggestions]
        suggestions = list(set(suggestions))
        if len(suggestions) > 0:
            message = "I don't have an entry for %s, try one of these: %s" % (text, '; '.join(suggestions))
        else:
            message = "I don't have an entry for %s. Try searching a letter or fragment, or use 'horace help' to see everything in the style guide." % text
    return message

@slack_events_adapter.on("message")
def handle_message(event_data):
    '''checks message and invokes corresponding function'''
    message = event_data["event"]
    if message.get('text') == 'Horace help':
        channel = message["channel"]
        message = h_help()
        CLIENT.api_call("chat.postMessage", channel=channel, text=message)
    elif message.get('text') == 'Horace admin':
        channel = message["channel"]
        message = admin()
        CLIENT.api_call("chat.postMessage", channel=channel, text=message)
    elif 'Horace add entry' in message.get('text'):
        channel = message["channel"]
        message = add_entry(message.get('text'))
        CLIENT.api_call("chat.postMessage", channel=channel, text=message)
    elif 'Horace overwrite' in message.get('text'):
        channel = message["channel"]
        message = overwrite(message.get('text'))
        CLIENT.api_call("chat.postMessage", channel=channel, text=message)
    elif 'Horace delete' in message.get('text'):
        channel = message["channel"]
        message = delete(message.get('text'))
        CLIENT.api_call("chat.postMessage", channel=channel, text=message)
    elif 'Horace' in message.get('text'):
        channel = message["channel"]
        message = lookup(message.get('text'))
        CLIENT.api_call("chat.postMessage", channel=channel, text=message)

slack_events_adapter.start(port=int(os.environ.get('PORT', 5000)))
