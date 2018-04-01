"""
Alexa skill helpers

(c) 2018 Balloon Inc. VOF
Wouter Devriendt
"""

# --------------- Helpers that build all of the responses ----------------------


def build_speechlet_response(title, output, reprompt_text, should_end_session, card_output=None, ssml=False):
    if ssml:
        outputSpeech = {
                'type': 'SSML',
                'ssml': output
            }
    else:
        outputSpeech = {
                'type': 'PlainText',
                'text': output
            }
    if not card_output:
        card_output = output
    return {
        'outputSpeech': outputSpeech,
        'card': {
            'type': 'Simple',
            'title': "Dog Trainer - " + title,
            'content': card_output
        },
        'reprompt': {
            'outputSpeech': {
                'type': 'PlainText',
                'text': reprompt_text
            }
        },
        'shouldEndSession': should_end_session
    }

def build_speechlet_directive():
    return {
      "outputSpeech" : None,
      "card" : None,
      "directives" : [ {
        "type" : "Dialog.Delegate"
      } ],
      "reprompt" : None,
      "shouldEndSession" : False
    }

def build_response(session_attributes, speechlet_response):
    return {
        'version': '1.0',
        'sessionAttributes': session_attributes,
        'response': speechlet_response
    }

def build_response(session_attributes, speechlet_response):
    return {
        'version': '1.0',
        'sessionAttributes': session_attributes,
        'response': speechlet_response
    }
