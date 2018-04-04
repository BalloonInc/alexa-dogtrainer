"""
Alexa skill for dog training, to be ran in AWS lambda.

(c) 2018 Balloon Inc. VOF
Wouter Devriendt
"""

###
### ------------------ Imports ------------------
###

# General imports
import os
import datetime

#Amazon libraries import
import boto3

# Custom imports
import alexahelpers as ah

###
### ------------------ DEBUG ------------------

import os
DEBUG = os.environ['DEBUG']


###
### ------------------ Constants for the dog table ------------------
###

# Table name
DOGS_TABLE = "dogs"
# fields
DOG_NAME ="dogName"
NUMBER_OF_TRAININGS = "number_of_trainings"
CREATED_AT="created_at"
UPDATED_AT="updated_at"
NUMBER_OF_RENAMES="number_of_renames"



###
### ------------------ Constants for last_question session attribute ------------------
###

# Key
LAST_QUESTION = "last_question"
# Values
NOTHING = 0
SHOULD_START_TRAINING = 1
TRAINING_CONFIRMATION = 2
MALE_OR_FEMALE = 3



###
### --------------- DynamoDB Init and table definitions ------------------
###

dynamodb = boto3.resource('dynamodb')
dogs_table = dynamodb.Table(DOGS_TABLE)



###
### --------------- Handlers for the supported actions ------------------
###

def getWelcomeResponse():
    session_attributes = {LAST_QUESTION:SHOULD_START_TRAINING}
    card_title = "Welcome"
    speech_output = "This is your dog trainer. " \
                    "Ask me to start the training, or ask for more info."
    # If the user either does not reply to the welcome message or says something
    # that is not understood, they will be prompted again with this text.
    reprompt_text = "Can I start the training?"
    should_end_session = False
    return ah.build_response(session_attributes, ah.build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))


def getDetailedHelp():
    session_attributes = {LAST_QUESTION:SHOULD_START_TRAINING}
    card_title = "Help for Dog trainer"
    speech_output = "I can make your dog do tricks, but I need your help the first few times. " \
                    "Go get some treats for the dog, and ask me to start training. "
    # If the user either does not reply to the welcome message or says something
    # that is not understood, they will be prompted again with this text.
    reprompt_text = "Do you want to start training now?"
    should_end_session = False
    return ah.build_response(session_attributes, ah.build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))
        

def setDogNameHandler(intent, session):
    user = session['user']['userId']  # get the userId of the current user
    session_attributes = {LAST_QUESTION:SHOULD_START_TRAINING}
    should_end_session = False
    
    dogNameFromIntent = getDogNameFromIntent(intent)

    if not dogNameFromIntent:
        return ah.build_response(session_attributes, ah.build_speechlet_directive())
    else:
        saveDogNameForUser(dogNameFromIntent, user)

    reprompt_text = "What's your dog's name?"
    speech_output = "I'll remember that your dog is called {0}. Hi, {0}! Should I start training now?".format(dogNameFromIntent)

    return ah.build_response(session_attributes, ah.build_speechlet_response(
        "Dog name updated", speech_output, reprompt_text, should_end_session))


def startTrainingHandler(intent, session, confirmed=False):
    user = session['user']['userId']  # get the userId of the current user
    try:
        session_attributes = session["attributes"]
    except:
        session_attributes = {}
    should_end_session = False
    
    dogNameFromIntent = getDogNameFromIntent(intent)
    dogFromDynamoDB = getDogFromDynamoDB(user)

    # If we don't know the dogname at all, ask again
    if not (dogNameFromIntent or dogFromDynamoDB):
        return ah.build_response(session_attributes, ah.build_speechlet_directive())
    # If it it in the DB, but not in the intent, just get it from the DB
    elif not dogNameFromIntent:
        dog = dogFromDynamoDB
    # If it is in the intent, use that one and update DB if needed:
    else:
        dog = saveDogNameForUser(dogNameFromIntent, user)


    if dog[NUMBER_OF_TRAININGS] < 2 and not confirmed:
        speech_output = """<speak>Lets get started. 
                            Take your treats, motivate {0} to listen to me, 
                            by giving him a treat when he follows the commands. 
                            Ready to start?</speak>
                            """.format(dog[DOG_NAME]) 
        reprompt_text = "Are you ready to start the training?"
        session_attributes[LAST_QUESTION]=TRAINING_CONFIRMATION
        card_output = "Let's get started. Take your treats, and give {0} one everytime a command is executed correctly.".format(dog[DOG_NAME])

        return ah.build_response(session_attributes, ah.build_speechlet_response(
            "Prepare Training", speech_output, reprompt_text, should_end_session, card_output=card_output, ssml=True))

    else:
        sex="boy"

        speech_output = """<speak>{0}, come here! <break time="2.0s" />
                        <emphasis level="strong"> Good {1}!</emphasis> <break time="1.0s" />
                        {0}, sit! <break time="1.5s" />
                        Good {1}! <break time="1.0s" />
                        {0}, down! <break time="1.5s" />
                        <emphasis level="strong">Good dog! <break time="0.2s" /> Good {1}.</emphasis> <break time="0.3s" /> 
                        That concludes the training session. Should we train again?</speak>""".format(dog[DOG_NAME], sex)

        reprompt_text = "Do you want me to train your dog again?"
        
        dog[NUMBER_OF_TRAININGS] += 1
        saveDogToDynamoDB(dog, user)
        session_attributes[LAST_QUESTION]=SHOULD_START_TRAINING

        return ah.build_response(session_attributes, ah.build_speechlet_response(
            "Start training", speech_output, reprompt_text, should_end_session, card_output="We trained: Come, Sit, Down!", ssml=True))


def endSession(session):
    user = session['user']['userId'] 
    dog = getDogFromDynamoDB(user)
    if dog:
        name = dog[DOG_NAME]
    else:
        name = "you"
        
    card_title = "Session Ended"
    speech_output = "Dog trainer out, have a nice day! "
    card_output = "Thanks for using Dog Trainer, I hope {0} had fun!".format(name)
    should_end_session = True

    return ah.build_response({}, ah.build_speechlet_response(
        card_title, speech_output, None, should_end_session, card_output=card_output))



###
### ---------------  Local Helpers ---------------
###

def printDebug(output):
    if not DEBUG or DEBUG == "0" or str(DEBUG).lower() == "false":
        return
    print(output)

def getDogNameFromIntent(intent):
    if 'slots' not in intent:
        return None
    if 'Dog' not in intent['slots']:
        return None
    if 'value' not in intent['slots']['Dog']:
        return None
    return intent['slots']['Dog']['value']
       

def saveDogNameForUser(dogName, user):
    dog = getDogFromDynamoDB(user)

    if not dog:
        dog = {
            NUMBER_OF_TRAININGS:0,
            NUMBER_OF_RENAMES:0
        }
    else:
        dog[NUMBER_OF_RENAMES] += 1
    dog[DOG_NAME] = dogName
    return saveDogToDynamoDB(dog, user)



###
### ---------------  Routes for multi-purpose intents --------------- 
###

def routeYesIntent(intent, session):
    try:
        sessionAttributes = session["attributes"]
    except:
        sessionAttributes = {}

    if LAST_QUESTION in sessionAttributes:
        last_question =sessionAttributes[LAST_QUESTION]
        if last_question == SHOULD_START_TRAINING:
            return startTrainingHandler(intent, session)
        elif last_question == TRAINING_CONFIRMATION:
            return startTrainingHandler(intent, session, confirmed=True)
        else:
            return endSession(session)
    else:
        print("Unknown last question")
        return endSession(session)

def routeNoIntent(intent, session):
    try:
        sessionAttributes = session["attributes"]
    except:
        sessionAttributes = {}

    if LAST_QUESTION in sessionAttributes:
        last_question =sessionAttributes[LAST_QUESTION]
        if last_question == SHOULD_START_TRAINING:
            return endSession(session)
        else:
            return endSession(session)
    else:
        return endSession(session)


###
### --------------- DB Getters and setters --------------- 
###

def getDogFromDynamoDB(user):
    try:
        response = dogs_table.get_item(Key={ 'account': user })
        return response['Item']['dog']
    except Exception as e:
        print("exception while getting dog: ")
        print(e)
        return None


def saveDogToDynamoDB(dog, user):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not CREATED_AT in dog:
        dog[CREATED_AT] = now
    dog[UPDATED_AT] = now

    try:
        dogs_table.put_item(Item={'account':user,'dog':dog })
        return dog
    except Exception as e:
        print("exception while saving dog: ")
        print(e)
        return None



###
### --------------- Events ------------------
###

def on_session_started(session_started_request, session):
    """ If we wanted to initialize the session to have some attributes we could
    add those here
    """
    printDebug("on_session_started requestId=" + session_started_request['requestId']
          + ", sessionId=" + session['sessionId'])


def on_launch(launch_request, session):
    """ Called when the user launches the skill without specifying what they
    want
    """
    printDebug("on_launch requestId=" + launch_request['requestId'] +
          ", sessionId=" + session['sessionId'])
    return getWelcomeResponse()


def on_intent(intent_request, session):
    """ Called when the user specifies an intent for this skill """
    printDebug("on_intent requestId=" + intent_request['requestId'] +
          ", sessionId=" + session['sessionId']+", intentName=" + intent_request['intent']['name'])

    intent = intent_request['intent']
    intent_name = intent_request['intent']['name']

    # Dispatch to the skill's intent handlers
    if intent_name == "StartTrainingIntent":
        return startTrainingHandler(intent, session)
    elif intent_name == "SetDogNameIntent":
        return setDogNameHandler(intent, session)
    elif intent_name == "AMAZON.HelpIntent":
        return getDetailedHelp()
    elif intent_name == "AMAZON.YesIntent":
        return routeYesIntent(intent,session)
    elif intent_name == "AMAZON.CancelIntent" or intent_name == "AMAZON.StopIntent" or intent_name == "AMAZON.NoIntent":
        return endSession(session)
    else:
        raise ValueError("Invalid intent")


def on_session_ended(session_ended_request, session):
    """ Called when the user ends the session.
    Is not called when the skill returns should_end_session=true
    """
    printDebug("on_session_ended requestId=" + session_ended_request['requestId'] +
          ", sessionId=" + session['sessionId'])



###
### --------------- Main handler ------------------
###
def lambda_handler(event, context):
    """ Route the incoming request based on type (LaunchRequest, IntentRequest,
    etc.) The JSON body of the request is provided in the event parameter.
    """

    if event['session']['application']['applicationId'] != "amzn1.ask.skill.a674b63d-50b6-4d2d-b5af-a55fef85c6aa":
        print("Wrong calling application")
        print("event.session.application.applicationId=" + event['session']['application']['applicationId'])

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
