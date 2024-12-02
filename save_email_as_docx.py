import json
import boto3
import email
from email import policy
from email.parser import BytesParser
from botocore.exceptions import NoCredentialsError, PartialCredentialsError

# Initialize S3 client
s3_client = boto3.client('s3')

def lambda_handler(event, context):
    try:
        # Get the object from the S3 bucket
        bucket_name = 'originemail'
        key = event['Records'][0]['s3']['object']['key']
        
        response = s3_client.get_object(Bucket=bucket_name, Key=key)
        raw_email = response['Body'].read()
        
        # Parse the raw email
        msg = BytesParser(policy=policy.default).parsebytes(raw_email)
        
        # Extract metadata from email body
        email_body = msg.get_body(preferencelist=('plain')).get_content()
        
        metadata = extract_metadata(email_body)
        
        # Process attachments
        for part in msg.iter_attachments():
            if part.get_content_disposition() == 'attachment':
                filename = part.get_filename()
                attachment_data = part.get_payload(decode=True)
                
                # Save the attachment to the same S3 bucket
                s3_client.put_object(
                    Bucket="forreceiving",
                    Key=f"{filename}",
                    Body=attachment_data,
                    Metadata=metadata
                )
        
        return {
            'statusCode': 200,
            'body': json.dumps('Attachments processed and saved successfully')
        }
    
    except NoCredentialsError:
        return {
            'statusCode': 403,
            'body': json.dumps('Credentials not available')
        }
    except PartialCredentialsError:
        return {
            'statusCode': 403,
            'body': json.dumps('Incomplete credentials')
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps(f"Error processing email: {str(e)}")
        }

def extract_metadata(email_body):
    metadata = {}
    
    try:
        lines = email_body.split('\n')
        for line in lines:
            if line.startswith('Student Name:'):
                metadata['Student-Name'] = line.split('Student Name:')[1].strip()
            elif line.startswith('Student Number:'):
                metadata['Student-Number'] = line.split('Student Number:')[1].strip()
            elif line.startswith('Student Email:'):
                metadata['Student-Email'] = line.split('Student Email:')[1].strip()
            elif line.startswith('Course Code:'):
                metadata['Course-Code'] = line.split('Course Code:')[1].strip()
            elif line.startswith('Assignment:'):
                metadata['Assignment'] = line.split('Assignment:')[1].strip()
            elif line.startswith('Section Number:'):
                metadata['Section-Number'] = line.split('Section Number:')[1].strip()
            elif line.startswith('Professor:'):
                metadata['Professor'] = line.split('Professor:')[1].strip()
            elif line.startswith('Professor Email:'):
                metadata['Professor-Email'] = line.split('Professor Email:')[1].strip()
    except Exception as e:
        print(f"Error extracting metadata: {str(e)}")
    
    return metadata
