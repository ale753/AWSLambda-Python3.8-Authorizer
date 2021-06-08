# AWS Lambda dependencies for Python(3.8) KWT Authenticator
[Python Cryptography Toolkit (pycrypto)] compiled and packaged for AWS Lambda python version 3.8 .


# Setup
You can simply download and include the Crypto folder in your project, zip and upload it to Lambda.

Steps to setup this from scratch :
```
git clone https://github.com/ale753/awslambda-pycrypto.git
```
Create a folder named "package" on desktop or wherever you want. Copy the content of the cloned repo in this folder.

Copy your python authorizer lambda function in the package folder and name it "lambda_function.py"

Zip the content of the folder 

```
cd package && zip -r9 package.zip .
```

Now you must deploy your lambda function with this zip archive. For more informations, see : https://docs.aws.amazon.com/lambda/latest/dg/python-package.html

Correctly configure your AWS CLI with an access key id and a secret access key id, then launch :

```
aws lambda update-function-code --function-name authorizer_test --zip-file fileb://package.zip
```

In my case I have created a lambda function called "authorizer_test"	
```

