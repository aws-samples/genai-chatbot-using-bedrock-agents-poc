import boto3
import logging
import random
import time
import zipfile
from io import BytesIO
import json
import uuid
import pprint
import os
#from requests_aws4auth import AWS4Auth
from create_kb import create_knowledgebase
from create_agent import create_agent


# getting boto3 clients for required AWS services
sts_client = boto3.client('sts')
iam_client = boto3.client('iam')
s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')
bedrock_agent_client = boto3.client('bedrock-agent')
bedrock_agent_runtime_client = boto3.client('bedrock-agent-runtime')
#open_search_serverless_client = boto3.client('opensearchserverless')

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    return logger

 #call logging
logger = setup_logging()

def main():
    session = boto3.session.Session()
    region = session.region_name
    account_id = sts_client.get_caller_identity()["Account"]
    
    
    # Create Knowledge base
    print("Creating Knowledge base...")
    kb_arn = create_knowledgebase(region, account_id)
    #fetch the string after / in knowledge_base_arn and assign it to knowledge_base_id variable.
    kb_id = kb_arn.split('/')[-1]
    
    
    # If you want to stop here and start using the KB for other purposes you can do so. 
    # We will create Agent in the next step and will use the KB created
    print("Creating Agent...")
    va_agent_id = create_agent(region, account_id, kb_arn, kb_id)
    print("Setup Complete!")

if __name__ == "__main__":
    main()
