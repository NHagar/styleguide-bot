# -*- coding: UTF-8 -*-
import os
import pickle
import difflib
from pyee import EventEmitter
from flask import Flask, request, make_response
import json
from slackclient import SlackClient

SLACK_VERIFICATION_TOKEN = os.environ["SLACK_VERIFICATION_TOKEN"]
SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
CLIENT = SlackClient(SLACK_BOT_TOKEN)

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
styleguide = pickle.load(open('style_guide', 'rb'))

@slack_events_adapter.on("message")
def handle_message(event_data):
    message = event_data["event"]
    if message.get('text') == 'Horace help':
        channel = message["channel"]
        message = list(styleguide.keys())
        message.sort()
        CLIENT.api_call("chat.postMessage", channel=channel, text=message)
    elif message.get('text') == 'Horace admin':
        channel = message["channel"]
        message = '''"horace add entry term : definiton" adds a new item to the style guide. There has to be a space on either side of the :.
"horace overwrite term : definition" changes the definiton of an existing term. Again, space on either side.
Only use these in direct messages with me! The style guide will get messy if everyone knows how to change it.'''
        CLIENT.api_call("chat.postMessage", channel=channel, text=message)
    elif 'Horace add entry' in message.get('text'):
        text = message.get('text').split(' ')
        text = text[3:]
        term = ' '.join(text[0:text.index(':')])
        definition = ' '.join(text[text.index(':')+1:])
        term.lower()
        check = styleguide.get(term)
        if check != None:
            channel = message["channel"]
            message = 'I already have an entry for %s. Use "horace overwrite term : new definiton" if you really want to change it.' % term
            CLIENT.api_call("chat.postMessage", channel=channel, text=message)
        else:
            styleguide[term.lower()] = definition
            pickle.dump(styleguide, open('style_guide', 'wb'))
            channel = message["channel"]
            message = 'I added %s to the style guide, with definition %s.' % (term, definition)
            CLIENT.api_call("chat.postMessage", channel=channel, text=message)
    elif 'Horace overwrite' in message.get('text'):
        text = message.get('text').split(' ')
        text = text[2:]
        term = ' '.join(text[0:text.index(':')])
        definition = ' '.join(text[text.index(':')+1:])
        term.lower()
        styleguide[term.lower()] = definition
        pickle.dump(styleguide, open('style_guide', 'wb'))
        channel = message["channel"]
        message = 'I added %s to the style guide, with definition %s.' % (term, definition)
        CLIENT.api_call("chat.postMessage", channel=channel, text=message)
    elif 'Horace' in message.get('text'):
        text = message.get('text').split(' ')
        text.remove('Horace')
        text = ' '.join(text)
        response = styleguide.get(text.lower())
        if response != None:
            channel = message["channel"]
            message = response
            CLIENT.api_call("chat.postMessage", channel=channel, text=message)
        else:
            keys = list(styleguide.keys())
            suggestions = difflib.get_close_matches(text, keys)
            for i in keys:
                if text in i:
                    suggestions.append(i)
            suggestions = [i for i in suggestions]
            suggestions = list(set(suggestions))
            channel = message["channel"]
            if len(suggestions) > 0:
                message = "I don't have an entry for %s, try one of these: %s" % (text, '; '.join(suggestions))
            else:
                message = "I don't have an entry for %s. Try searching a letter or fragment, or use 'horace help' to see everything in the style guide." % text
            CLIENT.api_call("chat.postMessage", channel=channel, text=message)

slack_events_adapter.start(port=int(os.environ.get('PORT', 5000)))
