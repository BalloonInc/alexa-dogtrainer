"""
Alexa skill for dog training, to be ran in AWS lambda.

(c) 2018 Balloon Inc. VOF
Wouter Devriendt
"""

import alexahelpers as ah
import boto3

dynamodb = boto3.resource('dynamodb')


# --------------- Functions that control the skill's behavior ------------------


def getWelcomeResponse():
    session_attributes = {}
    card_title = "Welcome"
    speech_output = "This is your dog trainer. " \
                    "At your service."
    # If the user either does not reply to the welcome message or says something
    # that is not understood, they will be prompted again with this text.
    reprompt_text = "You can ask me to train your dog."
    should_end_session = False
    return ah.build_response(session_attributes, ah.build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))


def endSession():
    card_title = "Session Ended"
    speech_output = "Dog trainer out, have a nice day! "
    should_end_session = True
    return ah.build_response({}, ah.build_speechlet_response(
        card_title, speech_output, None, should_end_session))

def setDogNameHandler(intent, session):
    user = session['user']['userId']  # get the userId of the current user
    session_attributes = {}
    should_end_session = False
    
    dogNameFromIntent = getDogNameFromIntent(intent)

    if not dogNameFromIntent:
        return ah.build_response(session_attributes, ah.build_speechlet_directive())
    else:
        saveDogNameForUser(user, dogNameFromIntent)

    reprompt_text = "What's your dog's name?"
    speech_output = "I'll remember that your dog is called {0}. Hi {0}!".format(dogNameFromIntent)

    return ah.build_response(session_attributes, ah.build_speechlet_response(
        "Dog name updated", speech_output, reprompt_text, should_end_session))


def startTrainingHandler(intent, session):
    user = session['user']['userId']  # get the userId of the current user
    session_attributes = {}
    should_end_session = True
    
    dogNameFromIntent = getDogNameFromIntent(intent)
    dogNameFromDynamoDB = getDogNameFromDynamoDB(user)

    # If we don't know the dogname at all, ask again
    if not (dogNameFromIntent or dogNameFromDynamoDB):
        return ah.build_response(session_attributes, ah.build_speechlet_directive())
    # If it it in the DB, but not in the intent, just get it from the DB
    elif not dogNameFromIntent:
        dogName = dogNameFromDynamoDB
    # If it is in the intent, use that one and update DB if needed:
    else:
        saveDogNameForUser(user, dogNameFromIntent)
        dogName = dogNameFromIntent

    reprompt_text = "Which dog should I train?"
    speech_output = """<speak>{0}, come here! <break time="2.0s" />
                    <emphasis level="strong"> Good boy!</emphasis> <break time="1.0s" />
                    {0}, sit! <break time="1.5s" />
                    Good boy! <break time="1.0s" />
                    {0}, down! <break time="1.5s" />
                    <emphasis level="strong">Good boy! <break time="0.2s" /> Good dog.</emphasis></speak>""".format(dogName)

    return ah.build_response(session_attributes, ah.build_speechlet_response(
        "Start training", speech_output, reprompt_text, should_end_session, card_output="We trained: Come, Sit, Down!", ssml=True))


def getDogNameFromIntent(intent):
    if 'slots' not in intent:
        return None
    if 'Dog' not in intent['slots']:
        return None
    if 'value' not in intent['slots']['Dog']:
        return None
    return intent['slots']['Dog']['value']

def getDogNameFromDynamoDB(user):
    dognames = dynamodb.Table('dognames')
    try:
        print("will get dogname for user " + user)
        response = dognames.get_item(Key={ 'account': user })
        print("response: ")
        print(response)
        return response['Item']['dogName']
    except Exception as e:
        print("exception: ")
        print(e)
        return None

def saveDogNameForUser(user, dogName):
    dognames = dynamodb.Table('dognames')
    dognames.put_item(Item={'account':user,'dogName':dogName })
# --------------- Events ------------------


def on_session_started(session_started_request, session):
    """ If we wanted to initialize the session to have some attributes we could
    add those here
    """
    print("on_session_started requestId=" + session_started_request['requestId']
          + ", sessionId=" + session['sessionId'])


def on_launch(launch_request, session):
    """ Called when the user launches the skill without specifying what they
    want
    """
    print("on_launch requestId=" + launch_request['requestId'] +
          ", sessionId=" + session['sessionId'])
    # Dispatch to your skill's launch
    return getWelcomeResponse()


def on_intent(intent_request, session):
    """ Called when the user specifies an intent for this skill """
    print(intent_request)
    print(intent_request['intent'])
    print("on_intent requestId=" + intent_request['requestId'] +
          ", sessionId=" + session['sessionId']+", intentName=" + intent_request['intent']['name'])

    intent = intent_request['intent']
    intent_name = intent_request['intent']['name']

    # Dispatch to your skill's intent handlers
    if intent_name == "StartTrainingIntent":
        return startTrainingHandler(intent, session)
    elif intent_name == "SetDogNameIntent":
        return setDogNameHandler(intent, session)
    elif intent_name == "AMAZON.HelpIntent":
        return getWelcomeResponse()
    elif intent_name == "AMAZON.CancelIntent" or intent_name == "AMAZON.StopIntent":
        return endSession()
    else:
        raise ValueError("Invalid intent")


def on_session_ended(session_ended_request, session):
    """ Called when the user ends the session.
    Is not called when the skill returns should_end_session=true
    """
    print("on_session_ended requestId=" + session_ended_request['requestId'] +
          ", sessionId=" + session['sessionId'])


# --------------- Main handler ------------------

def lambda_handler(event, context):
    """ Route the incoming request based on type (LaunchRequest, IntentRequest,
    etc.) The JSON body of the request is provided in the event parameter.
    """
    print("event.session.application.applicationId=" +
          event['session']['application']['applicationId'])

    if (event['session']['application']['applicationId'] !=
            "amzn1.ask.skill.a674b63d-50b6-4d2d-b5af-a55fef85c6aa"):
        raise ValueError("Invalid Application ID")

    if event['session']['new']:
        on_session_started({'requestId': event['request']['requestId']},
                           event['session'])

    if event['request']['type'] == "LaunchRequest":
        return on_launch(event['request'], event['session'])
    elif event['request']['type'] == "IntentRequest":
        return on_intent(event['request'], event['session'])
    elif event['request']['type'] == "SessionEndedRequest":
        return on_session_ended(event['request'], event['session'])
