if [ $1 == "lambda" ]; then
    lambda="-t lambda"
fi

cd lambda/custom/
rm -rf ../deploy.zip
zip -r ../deploy.zip . 

cd ../..
ask deploy $lambda