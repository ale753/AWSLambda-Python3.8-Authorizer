from __future__ import print_function
import json
import time
from jose import jwk, jwt
from jose.utils import base64url_decode
import urllib3
import re
import json
import os

import boto3

#pip install python-jose[cryptography] -t .

client = boto3.client('cognito-idp')

REGION = os.environ['REGION']

COGNITO_APP_CLIENT_ID = os.environ['COGNITO_APP_CLIENT_ID']
COGNITO_USER_POOL_ID = os.environ['COGNITO_USER_POOL_ID']


#JWKS altri provider
#https://www.googleapis.com/oauth2/v3/certs #Google
#https://www.facebook.com/.well-known/oauth/openid/jwks/ #Facebook #access_token
#



def lambda_handler(event, context):

    print(event)
    #print(context)

    #print("Client token: " + event['authorizationToken'])
    #print("Method ARN: " + event['methodArn'])
    
    #Settare bene questi parametri
    region = 'us-east-1'
    userpool_id = COGNITO_USER_POOL_ID
    app_client_id = COGNITO_APP_CLIENT_ID


    keys_url = 'https://cognito-idp.' + REGION + '.amazonaws.com/' + userpool_id + '/.well-known/jwks.json'

    http = urllib3.PoolManager()
    response = http.request('GET', keys_url)
    #with urllib3.request.urlopen(keys_url) as f:
    #    response = f.read()
    
    keys = json.loads(response.data.decode('utf-8'))['keys'] 
    '''
    Validate the incoming token and produce the principal user identifier
    associated with the token. This can be accomplished in a number of ways:

    1. Call out to the OAuth provider
    2. Decode a JWT token inline
    3. Lookup in a self-managed DB
      '''
    token =  event['headers']['Authorization']
    headers = jwt.get_unverified_headers(token) #Download public keys
    kid = headers['kid']
    
    
    # search for the kid in the downloaded public keys
    key_index = -1
    for i in range(len(keys)):
        if kid == keys[i]['kid']:
            key_index = i
            break
    if key_index == -1:
        print('Public key not found in jwks.json')
        return False
        
    # construct the public key
    public_key = jwk.construct(keys[key_index])
    # get the last two sections of the token,
    # message and signature (encoded in base64)
    message, encoded_signature = str(token).rsplit('.', 1)
    
    decoded_signature = base64url_decode(encoded_signature.encode('utf-8'))
    # verify the signature
    if not public_key.verify(message.encode("utf8"), decoded_signature):
        print('Signature verification failed')
        return False
    print('Signature successfully verified')
    
    claims = jwt.get_unverified_claims(token)
    # additionally we can verify the token expiration
    if time.time() > claims['exp']:
        print('Token is expired')
        return False
    # and the Audience  (use claims['client_id'] if verifying an access token)
    if claims['aud'] != app_client_id:
        print('Token was not issued for this audience')
        return False
    # now we can use the claims
    print("CLAIMS :")
    print(claims)
    
    
    
    
    
    

    principalId = claims['cognito:username']
    print(principalId)

    '''
    response = client.list_users(
        UserPoolId= userpool_id,
        Limit=1,
        Filter='username = "' + principalId + '" '
    )
    
    
    print(response['Users'][0]['Attributes'])
    
    trial_already_requested = 0
    for element in response['Users'][0]['Attributes'] :
        if (element['Name'] == "custom:TrialRequested") :
            if (element['Value'] == "true") :
                trial_already_requested = 1
                break
    
     
    if (trial_already_requested == 0) :          
                
        response = client.admin_update_user_attributes(
                UserPoolId=userpool_id,
                Username=principalId,
                UserAttributes=[
                {
                    'Name': 'custom:TrialRequested',
                    'Value': 'true'
                },
            ]
        
            )
  
    print(response)
    '''

    '''
    You can send a 401 Unauthorized response to the client by failing like so:

      raise Exception('Unauthorized')

    If the token is valid, a policy must be generated which will allow or deny
    access to the client. If access is denied, the client will receive a 403
    Access Denied response. If access is allowed, API Gateway will proceed with
    the backend integration configured on the method that was called.

    This function must generate a policy that is associated with the recognized
    principal user identifier. Depending on your use case, you might store
    policies in a DB, or generate them on the fly.

    Keep in mind, the policy is cached for 5 minutes by default (TTL is
    configurable in the authorizer) and will apply to subsequent calls to any
    method/resource in the RestApi made with the same token.

    The example policy below denies access to all resources in the RestApi.
    '''
    tmp = event['methodArn'].split(':')
    apiGatewayArnTmp = tmp[5].split('/')
    awsAccountId = tmp[4]

    policy = AuthPolicy(principalId, awsAccountId)
    policy.restApiId = apiGatewayArnTmp[0]
    policy.region = tmp[3]
    policy.stage = apiGatewayArnTmp[1]
    #policy.denyAllMethods()
    
    #if (trial_already_requested == 0) :
    
    #policy.allowAllMethods()
    
    #else :
        #policy.denyAllMethods()
    policy.allowMethod(event["httpMethod"], event["resource"] + "/*") #'/pets/*'

    # Finally, build the policy
    authResponse = policy.build()

    # new! -- add additional key-value pairs associated with the authenticated principal
    # these are made available by APIGW like so: $context.authorizer.<key>
    # additional context is cached
    context = {
        'key': 'value',  # $context.authorizer.key -> value
        'number': 1,
        'bool': True
    }
    # context['arr'] = ['foo'] <- this is invalid, APIGW will not accept it
    # context['obj'] = {'foo':'bar'} <- also invalid

    authResponse['context'] = context

    return authResponse


class HttpVerb:
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    PATCH = 'PATCH'
    HEAD = 'HEAD'
    DELETE = 'DELETE'
    OPTIONS = 'OPTIONS'
    ALL = '*'


class AuthPolicy(object):
    # The AWS account id the policy will be generated for. This is used to create the method ARNs.
    awsAccountId = ''
    # The principal used for the policy, this should be a unique identifier for the end user.
    principalId = ''
    # The policy version used for the evaluation. This should always be '2012-10-17'
    version = '2012-10-17'
    # The regular expression used to validate resource paths for the policy
    pathRegex = '^[/.a-zA-Z0-9-\*]+$'

    '''Internal lists of allowed and denied methods.

    These are lists of objects and each object has 2 properties: A resource
    ARN and a nullable conditions statement. The build method processes these
    lists and generates the approriate statements for the final policy.
    '''
    allowMethods = []
    denyMethods = []

    # The API Gateway API id. By default this is set to '*'
    restApiId = '*'
    # The region where the API is deployed. By default this is set to '*'
    region = '*'
    # The name of the stage used in the policy. By default this is set to '*'
    stage = '*'

    def __init__(self, principal, awsAccountId):
        self.awsAccountId = awsAccountId
        self.principalId = principal
        self.allowMethods = []
        self.denyMethods = []

    def _addMethod(self, effect, verb, resource, conditions):
        '''Adds a method to the internal lists of allowed or denied methods. Each object in
        the internal list contains a resource ARN and a condition statement. The condition
        statement can be null.'''
        if verb != '*' and not hasattr(HttpVerb, verb):
            raise NameError('Invalid HTTP verb ' + verb + '. Allowed verbs in HttpVerb class')
        resourcePattern = re.compile(self.pathRegex)
        if not resourcePattern.match(resource):
            raise NameError('Invalid resource path: ' + resource + '. Path should match ' + self.pathRegex)

        if resource[:1] == '/':
            resource = resource[1:]

        resourceArn = 'arn:aws:execute-api:{}:{}:{}/{}/{}/{}'.format(self.region, self.awsAccountId, self.restApiId, self.stage, verb, resource)

        if effect.lower() == 'allow':
            self.allowMethods.append({
                'resourceArn': resourceArn,
                'conditions': conditions
            })
        elif effect.lower() == 'deny':
            self.denyMethods.append({
                'resourceArn': resourceArn,
                'conditions': conditions
            })

    def _getEmptyStatement(self, effect):
        '''Returns an empty statement object prepopulated with the correct action and the
        desired effect.'''
        statement = {
            'Action': 'execute-api:Invoke',
            'Effect': effect[:1].upper() + effect[1:].lower(),
            'Resource': []
        }

        return statement

    def _getStatementForEffect(self, effect, methods):
        '''This function loops over an array of objects containing a resourceArn and
        conditions statement and generates the array of statements for the policy.'''
        statements = []

        if len(methods) > 0:
            statement = self._getEmptyStatement(effect)

            for curMethod in methods:
                if curMethod['conditions'] is None or len(curMethod['conditions']) == 0:
                    statement['Resource'].append(curMethod['resourceArn'])
                else:
                    conditionalStatement = self._getEmptyStatement(effect)
                    conditionalStatement['Resource'].append(curMethod['resourceArn'])
                    conditionalStatement['Condition'] = curMethod['conditions']
                    statements.append(conditionalStatement)

            if statement['Resource']:
                statements.append(statement)

        return statements

    def allowAllMethods(self):
        '''Adds a '*' allow to the policy to authorize access to all methods of an API'''
        self._addMethod('Allow', HttpVerb.ALL, '*', [])

    def denyAllMethods(self):
        '''Adds a '*' allow to the policy to deny access to all methods of an API'''
        self._addMethod('Deny', HttpVerb.ALL, '*', [])

    def allowMethod(self, verb, resource):
        '''Adds an API Gateway method (Http verb + Resource path) to the list of allowed
        methods for the policy'''
        self._addMethod('Allow', verb, resource, [])

    def denyMethod(self, verb, resource):
        '''Adds an API Gateway method (Http verb + Resource path) to the list of denied
        methods for the policy'''
        self._addMethod('Deny', verb, resource, [])

    def allowMethodWithConditions(self, verb, resource, conditions):
        '''Adds an API Gateway method (Http verb + Resource path) to the list of allowed
        methods and includes a condition for the policy statement. More on AWS policy
        conditions here: http://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements.html#Condition'''
        self._addMethod('Allow', verb, resource, conditions)

    def denyMethodWithConditions(self, verb, resource, conditions):
        '''Adds an API Gateway method (Http verb + Resource path) to the list of denied
        methods and includes a condition for the policy statement. More on AWS policy
        conditions here: http://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements.html#Condition'''
        self._addMethod('Deny', verb, resource, conditions)

    def build(self):
        '''Generates the policy document based on the internal lists of allowed and denied
        conditions. This will generate a policy with two main statements for the effect:
        one statement for Allow and one statement for Deny.
        Methods that includes conditions will have their own statement in the policy.'''
        if ((self.allowMethods is None or len(self.allowMethods) == 0) and
                (self.denyMethods is None or len(self.denyMethods) == 0)):
            raise NameError('No statements defined for the policy')

        policy = {
            'principalId': self.principalId,
            'policyDocument': {
                'Version': self.version,
                'Statement': []
            }
        }

        policy['policyDocument']['Statement'].extend(self._getStatementForEffect('Allow', self.allowMethods))
        policy['policyDocument']['Statement'].extend(self._getStatementForEffect('Deny', self.denyMethods))

        return policy

