import boto3
import time
from io import BytesIO
import json
import os
import requests

# getting boto3 clients for required AWS services
sts_client = boto3.client('sts')
iam_client = boto3.client('iam')
secret_manager_client = boto3.client('secretsmanager')
s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')
bedrock_agent_client = boto3.client('bedrock-agent')
bedrock_agent_runtime_client = boto3.client('bedrock-agent-runtime')
kb_key = f'bedrock-ug.pdf'
upload_file_url = f'https://docs.aws.amazon.com/pdfs/bedrock/latest/userguide/bedrock-ug.pdf'

def create_knowledgebase(region, account_id ):
    
    suffix = f"{region}-{account_id}"
    agent_name = "virtual-assistant-agent"
    bucket_name = f'{agent_name}-{suffix}'
    kb_name = f'virtual-assistant-kb-{suffix}'
    bucket_arn = f"arn:aws:s3:::{bucket_name}"
    data_source_name = f'virtual-assistant-kb-docs-{suffix}'
    embedding_model_arn = f'arn:aws:bedrock:{region}::foundation-model/cohere.embed-english-v3' #amazon.titan-embed-text-v1
    
    


    print(region, account_id)

    kb_textField = 'textfield'
    kb_pinecone_conn='https://datafield-wwgx1at.svc.aped-4627-b74a.pinecone.io'
    pinecone_key_sm_arn=f'arn:aws:secretsmanager:{region}:{account_id}:secret:pinekey-6j3iCT'

    try:
        print("Creating KB role...")
        # create required role for KB
        kb_role_arn = create_kb_role(region, account_id, pinecone_key_sm_arn)

        print("Creating Knowledge Base...")
        #create knowledgebase with pinecone storage configuration
        kb_obj = bedrock_agent_client.create_knowledge_base(
            name=kb_name,
            description='Virtual Assistant KB',
            knowledgeBaseConfiguration={
                'type': 'VECTOR',
                'vectorKnowledgeBaseConfiguration': {
                    'embeddingModelArn' : embedding_model_arn,
                }

            },
            storageConfiguration={
                'type': 'PINECONE',
                'pineconeConfiguration': {
                    'connectionString' : kb_pinecone_conn,
                    'credentialsSecretArn': pinecone_key_sm_arn,
                    'namespace': 'datafield',                    
                    'fieldMapping': { 
                        'metadataField': 'metadata',
                        'textField': kb_textField
                    },                    
                }
            },
            roleArn=kb_role_arn,
            tags= {
                'Name': kb_name
            }            
        )
        # nosemgrep
        time.sleep(20)

        s3_configuration = {
        'bucketArn': bucket_arn,
        'inclusionPrefixes': [kb_key]  
        }

        # Define the data source configuration
        data_source_configuration = {
            's3Configuration': s3_configuration,
            'type': 'S3'
        }

        knowledge_base_id = kb_obj["knowledgeBase"]["knowledgeBaseId"]
        knowledge_base_arn = kb_obj["knowledgeBase"]["knowledgeBaseArn"]

        chunking_strategy_configuration = {
            "chunkingStrategy": "FIXED_SIZE",
            "fixedSizeChunkingConfiguration": {
                "maxTokens": 512,
                "overlapPercentage": 20
            }
        }

        # Create the data source
        try:
            # ensure that the KB is created and available
            # nosemgrep
            #time.sleep(15)
            data_source_response = bedrock_agent_client.create_data_source(
                knowledgeBaseId=knowledge_base_id,
                name=data_source_name,
                description='DataSource for the virtual agent document source',
                dataSourceConfiguration=data_source_configuration,
                vectorIngestionConfiguration = {
                    "chunkingConfiguration": chunking_strategy_configuration
                }
            )
            # nosemgrep
            time.sleep(15)
            print("Ingest Job")
            ingest_job(data_source_response, knowledge_base_id)
             
            print("KnowledgeBase created successfully")
        except Exception as e:
            print(f"Error occurred: {e}")

    except Exception as e:
        print(f"Error occurred while creating KB: {e}")

    return knowledge_base_arn
    
#This Job will load the S3 document to vector DB - Pinecone in this case            
def ingest_job(data_source_response, knowledge_base_id):
    # Start an ingestion job
    data_source_id = data_source_response["dataSource"]["dataSourceId"]
    start_job_response = bedrock_agent_client.start_ingestion_job(
        knowledgeBaseId=knowledge_base_id, 
        dataSourceId=data_source_id
    )



def create_kb_role(region, account_id, pinecone_key_sm_arn):

    suffix = f"{region}-{account_id}"
    agent_name = "virtual-assistant-agent"
    bucket_name = f'{agent_name}-{suffix}'
    embedding_model_arn = f'arn:aws:bedrock:us-east-1::foundation-model/cohere.embed-english-v3' #amazon.titan-embed-text-v1
    kb_files_path = '../documents/'
    schema_key = f'{agent_name}-schema.json'
    schema_file = f'{kb_files_path}/{schema_key}'
   
    embedding_model_arn = f'arn:aws:bedrock:us-east-1::foundation-model/cohere.embed-english-v3' #amazon.titan-embed-text-v1
    
    s3_folder = f'kbdocuments'
    kb_role_name = f'BedrockExecutionRoleForKB_vakb'
    kb_bedrock_allow_model_policy_name = f"va-kb-bedrock-allow-model-{suffix}"
    kb_secretmanager_api_policy_name = f"va-kb-secretmanager-api-allow-{suffix}"
    kb_s3_allow_policy_name = f"va-kb-s3-allow-{suffix}"
    create_bucket = True
    create_role = True

    if create_bucket:
        #create S3 bucket
        res = s3_client.create_bucket(Bucket=bucket_name)

        if res['ResponseMetadata']['HTTPStatusCode'] == 200:
            #upload schema to S3 bucket
            s3_client.upload_file(schema_file, bucket_name, schema_key)
            #upload kb document to S3
            for f in os.listdir(kb_files_path):
                if f.endswith(".pdf"):
                        #Sample PDF. Using Amazon Bedrock user guide here 
                    
                    
                    # download the file from a url and upload to S3
                    r = requests.get(url)
                    file_content = BytesIO(r.content)
                    s3_client.upload_fileobj(file_content, bucket_name, s3_folder+'/'+kb_key)
                    
        else:
            print("Error creating S3 bucket")
    else:
        print("Bucket exists, skipping S3 bucket creation")
    
    if create_role:
        print("Creating required policies for KB role...")
        #create policy for knowledgebase to invoke the model
        bedrock_kb_allow_fm_model_policy_statement = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "BedrockInvokeModelStatement",
                    "Effect": "Allow",
                    "Action": "bedrock:InvokeModel",
                    "Resource": [
                        embedding_model_arn
                    ]
                }
            ]
        }

        kb_bedrock_model_policy_json = json.dumps(bedrock_kb_allow_fm_model_policy_statement)
    # POLICY 1
        kb_bedrock_model_access_policy = iam_client.create_policy(
            PolicyName=kb_bedrock_allow_model_policy_name,
            PolicyDocument=kb_bedrock_model_policy_json
        )
        #create policy for knowledgebase to access the secret manager
        bedrock_kb_allow_secretmanager_policy_statement = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "BedrockAccessSecretManagerStatement",
                    "Effect": "Allow",                    
                    "Action": [
                        "secretsmanager:GetSecretValue"
                    ],
                    "Resource": [
                        pinecone_key_sm_arn
                    ]
                }
            ]
        }
        kb_bedrock_sm_policy_json = json.dumps(bedrock_kb_allow_secretmanager_policy_statement)
    #POLICY 2
        kb_bedrock_sm_access_policy = iam_client.create_policy(
            PolicyName=kb_secretmanager_api_policy_name,
            PolicyDocument=kb_bedrock_sm_policy_json
        )

        kb_s3_allow_policy_statement = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowKBAccessDocuments",
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:ListBucket"
                    ],
                    "Resource": [
                        f"arn:aws:s3:::{bucket_name}/*",
                        f"arn:aws:s3:::{bucket_name}"
                    ],
                    "Condition": {
                        "StringEquals": {
                            "aws:ResourceAccount": f"{account_id}"
                        }
                    }
                }
            ]
        }


        kb_s3_policy_json = json.dumps(kb_s3_allow_policy_statement)

    #POLICY 3
        kb_s3_access_policy = iam_client.create_policy(
            PolicyName=kb_s3_allow_policy_name,
            PolicyDocument=kb_s3_policy_json
        )
        # nosemgrep
        time.sleep(10)
    #create assume role policy for knowledgebase
        bedrock_kb_assume_role_policy_statement = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "bedrock.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }

        kb_bedrock_assume_role_policy_json = json.dumps(bedrock_kb_assume_role_policy_statement)

        #create role for knowledgebase
        bedrock_kb_role = iam_client.create_role(
            RoleName=kb_role_name,
            AssumeRolePolicyDocument=kb_bedrock_assume_role_policy_json
        )

        #wait for role to be created
        # nosemgrep
        time.sleep(20)

        #print("Attach policy 1...")
        iam_client.attach_role_policy(
            RoleName=kb_role_name,
            PolicyArn=kb_bedrock_model_access_policy['Policy']['Arn']
        )

        #print("Attach policy 2...")
        iam_client.attach_role_policy(
            RoleName=kb_role_name,
            PolicyArn=kb_bedrock_sm_access_policy['Policy']['Arn']
        )

        #print("Attach policy 3...")
        iam_client.attach_role_policy(
            RoleName=kb_role_name,
            PolicyArn=kb_s3_access_policy['Policy']['Arn']
        )   
        # nosemgrep
        time.sleep(10)
        kb_role_arn = bedrock_kb_role["Role"]["Arn"]

        #attach this role as resource policy on secret
        
        secret_policy_stmt = {
            "Version": "2012-10-17",
            "Statement": [
                {                    
                    "Effect": "Allow",
                    "Principal": {
                        "AWS": kb_role_arn
                    },
                    "Action": [
                        "secretsmanager:GetSecretValue"
                    ],
                    "Resource": [
                        pinecone_key_sm_arn
                    ]
                },
            ],
        }

        # Attach the resource-based policy to the secret
        secret_policy_json = json.dumps(secret_policy_stmt)
        print("Attaching resource permissions to secret...")
        secret_manager_client.put_resource_policy(SecretId=pinecone_key_sm_arn, ResourcePolicy=secret_policy_json)             
        #Role created for KB and all set for next step
        print("KB role created successfully",kb_role_arn)
        return kb_role_arn
    else:
        print("Role exists, skipping role creation")
        return f'arn:aws:iam::{account_id}:role/{kb_role_name}'

