# jenkins-dogtrainer
Use Alexa to train your dog. You start by telling the Dog Trainer your dog's name, and train together with the trainer (e.g. by rewarding with a candy)


## Requirements
- Amazon echo family device, or home made alternative (raspberry pi + alexa)
- An [Amazon development account](https://developer.amazon.com) (free to register)
- An [Amazon AWS account](https://console.aws.amazon.com) (also free)
- Python 3 on your pc

## How to use

1. Create an Amazon lambda in Python 3.

2. Create a zip of the content of this folder (Python files)

3. Upload the zip file as content of the lambda.

4. Create an Amazon Alexa skill.

5. Use language-model.json as language model. Don't forget to build it.

6. Set the created Lambda as endpoint for the alexa skill.

If your echo is linked with the same account as your development account, you should be able to test on your device already.

## For developing
- all `print` statements are written to Amazon's CloudWatch logging. This is very convenient.
- You can test your lambda with test events. This way you don't need to use a voice controlled device all the time.
- Setting `should_end_session` in the intents (`lambda_function.py`) ensures your echo session never closes, which is nice for testing purposes.
