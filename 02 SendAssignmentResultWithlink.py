import json
import boto3
import os
import random
import string
import urllib.parse
from botocore.exceptions import ClientError
from datetime import datetime

# Initialize clients
s3_client = boto3.client('s3')
ses_client = boto3.client('ses')
dynamodb = boto3.client('dynamodb')

# Set your SES verified email
SENDER = "info@caa900.store"

# DynamoDB Table
DYNAMODB_TABLE = 'AssignmentResults'

# S3 Bucket for storage
DEST_BUCKET = 'storeassignments'

def generate_random_key(length=10):
    letters_and_digits = string.ascii_letters + string.digits
    return ''.join(random.choice(letters_and_digits) for i in range(length))

def get_metadata_value(metadata, key):
    return metadata.get(f'x-amz-meta-{key}', metadata.get(key))

def lambda_handler(event, context):
    # Log the received event
    print("Received event: " + json.dumps(event, indent=2))

    # Get the object from the event
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']
    key = urllib.parse.unquote_plus(key)

    try:
        # Get the object metadata
        response = s3_client.head_object(Bucket=bucket, Key=key)
        metadata = response['Metadata']
        print("Metadata:", metadata)

        # Convert metadata keys to lowercase and check for both prefixed and non-prefixed keys
        metadata_lower = {k.lower(): v for k, v in metadata.items()}
        print("Converted Metadata Keys:", metadata_lower.keys())

        student_email = get_metadata_value(metadata_lower, 'student-email')
        professor_email = get_metadata_value(metadata_lower, 'professor-email')

        # Debug: Print extracted emails
        print("Student Email:", student_email)
        print("Professor Email:", professor_email)

        if not student_email or not professor_email:
            raise ValueError("Student email or Professor email is missing in metadata")

        # Get other metadata values
        student_name = get_metadata_value(metadata_lower, 'student-name')
        assignment = get_metadata_value(metadata_lower, 'assignment')
        student_number = get_metadata_value(metadata_lower, 'student-number')
        course_code = get_metadata_value(metadata_lower, 'course-code')
        overall_grade = get_metadata_value(metadata_lower, 'overallgrade')
        section_number = get_metadata_value(metadata_lower, 'section-number')
        professor_name = get_metadata_value(metadata_lower, 'professor')

        # Get the object content
        obj = s3_client.get_object(Bucket=bucket, Key=key)
        content = obj['Body'].read()

        # Generate a new random key for the object
        new_key = generate_random_key() + '.docx'

        # Store the object in the new S3 bucket without metadata
        s3_client.put_object(Bucket=DEST_BUCKET, Key=new_key, Body=content)
        
        # Generate a pre-signed URL for the stored object
        presigned_url = s3_client.generate_presigned_url('get_object',
                                                         Params={'Bucket': DEST_BUCKET, 'Key': new_key},
                                                         ExpiresIn=3600)
        
        # Store metadata in DynamoDB with timestamp
        timestamp = datetime.utcnow().isoformat()
        dynamodb.put_item(
            TableName=DYNAMODB_TABLE,
            Item={
                'AssignmentID': {'S': new_key},
                'StudentEmail': {'S': student_email},
                'ProfessorEmail': {'S': professor_email},
                'StudentName': {'S': student_name},
                'Assignment': {'S': assignment},
                'StudentNumber': {'S': student_number},
                'CourseCode': {'S': course_code},
                'OverallGrade': {'S': overall_grade},
                'SectionNumber': {'S': section_number},
                'ProfessorName': {'S': professor_name},
                'Timestamp': {'S': timestamp},
                'Metadata': {'S': json.dumps(metadata)}
            }
        )

        # Send the email to the student and professor
        send_email(student_email, professor_email, student_name, assignment, student_number, course_code, overall_grade, section_number, professor_name, new_key, presigned_url)

        return {
            'statusCode': 200,
            'body': json.dumps('Email sent successfully and metadata stored in DynamoDB')
        }

    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            print(f"Error: The object {key} does not exist in the bucket {bucket}.")
        else:
            print(f"Error: {e.response['Error']['Message']}")
        raise e

    except Exception as e:
        print(e)
        print(f"Error processing object {key} from bucket {bucket}.")
        raise e

def send_email(student_email, professor_email, student_name, assignment, student_number, course_code, overall_grade, section_number, professor_name, key, presigned_url):
    # Create the email body
    body_html = f"""<html>
    <head></head>
    <body>
      <h1>Assignment Grading Report</h1>
      <table border="1">
        <tr>
          <th>Item</th>
          <th>Detail</th>
        </tr>
        <tr>
          <td>Student Name</td>
          <td>{student_name}</td>
        </tr>
        <tr>
          <td>Student ID</td>
          <td>{student_number}</td>
        </tr>
        <tr>
          <td>Student Email</td>
          <td>{student_email}</td>
        </tr>
        <tr>
          <td>Course Code</td>
          <td>{course_code}</td>
        </tr>
        <tr>
          <td>Assignment</td>
          <td>{assignment}</td>
        </tr>
        <tr>
          <td>Overall Grade</td>
          <td>{overall_grade}</td>
        </tr>
        <tr>
          <td>Section Number</td>
          <td>{section_number}</td>
        </tr>
        <tr>
          <td>Professor</td>
          <td>{professor_name}</td>
        </tr>
        <tr>
          <td>Professor Email</td>
          <td>{professor_email}</td>
        </tr>
        <tr>
          <td>Object Key</td>
          <td>{key}</td>
        </tr>
        <tr>
          <td>Download Link</td>
          <td><a href="{presigned_url}">Download Graded Assignment</a></td>
        </tr>
      </table>
    </body>
    </html>"""

    body_text = f"""Assignment Grading Report
    Student Name: {student_name}
    Student ID: {student_number}
    Student Email: {student_email}
    Course Code: {course_code}
    Assignment: {assignment}
    Overall Grade: {overall_grade}
    Section Number: {section_number}
    Professor: {professor_name}
    Professor Email: {professor_email}
    Object Key: {key}
    Download Link: {presigned_url}
    """

    # Send the email
    try:
        response = ses_client.send_email(
            Destination={
                'ToAddresses': [student_email, professor_email]
            },
            Message={
                'Body': {
                    'Html': {
                        'Charset': "UTF-8",
                        'Data': body_html,
                    },
                    'Text': {
                        'Charset': "UTF-8",
                        'Data': body_text,
                    },
                },
                'Subject': {
                    'Charset': "UTF-8",
                    'Data': "Assignment Grading Report",
                },
            },
            Source=SENDER,
        )
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        print("Email sent! Message ID:"),
        print(response['MessageId'])
