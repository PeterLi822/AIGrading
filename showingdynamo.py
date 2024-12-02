import json
import boto3
from boto3.dynamodb.conditions import Key, Attr

# Initialize a session using Amazon DynamoDB
dynamodb = boto3.resource('dynamodb', region_name='us-east-2')

# Select your DynamoDB table
table = dynamodb.Table('AssignmentResults')

def lambda_handler(event, context):
    try:
        response = table.scan()
        items = response['Items']
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
            },
            'body': json.dumps({'Items': items})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
