# alexa-dogtrainer
Use Alexa to train your dog. You start by telling the Dog Trainer your dog's name, and train together with the trainer (e.g. by rewarding with a treat).


## Use on your Alexa device:
Available in the Alexa store: https://www.amazon.com/gp/product/B07BVJ1G1K

Just log in with your Amazon account and click "Enable Skill".

## Support
For any issues or suggestion, mail <support@ballooninc.be> or create an [issue](https://github.com/BalloonInc/alexa-dogtrainer/issues) here on Github.

## Requirements
- Amazon echo family device, or home made alternative (raspberry pi + alexa)
- An [Amazon development account](https://developer.amazon.com) (free to register)
- An [Amazon AWS account](https://console.aws.amazon.com) (also free)
- Python 3 on your pc

## How to develop / deploy

See [here](https://developer.amazon.com/blogs/post/Tx14R0IYYGH3SKT/Flask-Ask-A-New-Python-Framework-for-Rapid-Alexa-Skills-Kit-Development) for how to run the python code locally and use ngrok.

1. Create an Amazon lambda in Python 3.

2. Run `pip install -r flask-ask -t lambda/custom/lib` to install all necessary libs locally.

2. Create a zip of the content of this folder (Python files)

3. Upload the zip file as content of the lambda.

4. Create an Amazon Alexa skill.

5. Create a new table called "dognames" in DynamoDB

6. Use language-model.json as language model. Don't forget to build it.

7. Set the created Lambda as endpoint for the alexa skill.

8. Optional: automate this process with [aws-cli](https://aws.amazon.com/cli‎) and [ask-cli](https://developer.amazon.com/docs/smapi/ask-cli-command-reference.html). The folder structure of this project is in such a way that you can just run `ask deploy` after linking both your AWS and AVS accounts.

If your echo is linked with the same account as your development account, you should be able to test on your device already.

## Developing tips
- all `print` statements are written to Amazon's CloudWatch logging. This is very convenient.
- You can test your lambda with test events. This way you don't need to use a voice controlled device all the time.
- Setting `should_end_session` to `False` in the intents (`lambda_function.py`) ensures your echo session never closes, which is nice for testing purposes.


## Deployment when not on a linux machine

`pip` builds some platform specific binaries, so when on MacOS or Windows, you're best to install the libs via docker.

First run a docker ubuntu container:
`docker run -v "$PWD":/working -it --rm lambci/lambda:build-python3.6 bash`

Then build the libs to the lib folder and zip everything

`pip install flask-ask -t lib`
`zip -r ../lambda-deploy.zip .`

Upload the zip manually to the lambda. `ask deploy` doesn't seem to work for now because hidden folders are not uploaded.
