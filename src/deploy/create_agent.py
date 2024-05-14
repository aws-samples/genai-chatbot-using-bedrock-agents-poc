import boto3
import time
import zipfile
from io import BytesIO
import json 


# getting boto3 clients for required AWS services
sts_client = boto3.client('sts')
iam_client = boto3.client('iam')
s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')
bedrock_agent_client = boto3.client('bedrock-agent')
bedrock_agent_runtime_client = boto3.client('bedrock-agent-runtime')
agent_name = "virtual-assistant-agent"


def create_agent(region, account_id, kb_arn, kb_id):

    #create all the required policies and roles
    va_agent_role_arn = create_agent_role(region, account_id, kb_arn)
    #va_agent_role_arn = 'arn:aws:iam::722665529886:role/AmazonBedrockExecutionRoleForAgents_va'
    #print(va_agent_role_arn)

    # Create Agent
    agent_instruction = """You are an expert customer service agent helping faculty and students to resolve their queries like accessing the grades, eligibility, login issues, powerschool access issues. You can also guide users with navigation and other assistance on their portal. If the user request for a password reset, ask for email address, name and ID which are required information before fulfilling the <user-request>, once you have all the required information, you can reset the password and provide temporary password to the user"""

    va_agent_obj = bedrock_agent_client.create_agent(
        agentName=agent_name,
        agentResourceRoleArn=va_agent_role_arn,
        description="Virtual assistant agent with ability to reset the password.",
        idleSessionTTLInSeconds=1800,
        foundationModel="anthropic.claude-3-haiku-20240307-v1:0",
        instruction=agent_instruction,
    )
    print("Agent created successfully")
    #print(va_agent_obj)
    va_agent_id = va_agent_obj['agent']['agentId']
    create_action_group(region, account_id, va_agent_id, kb_id)

    #prepare agent
    bedrock_agent_client.prepare_agent(
        agentId=va_agent_id
    )
    # nosemgrep
    time.sleep(25)
    #create alias once agent is prepared
    create_alias(va_agent_id)

    print("Agent prepared and new alias created")
    return va_agent_id

def create_alias(va_agent_id):
    #create alias
    alias_name = "latest"
    alias_description = "Alias for latest version of the agent"
    alias_arn = bedrock_agent_client.create_agent_alias(
        agentId=va_agent_id,
        agentAliasName=alias_name,
        description=alias_description
    )
    #print(alias_arn)
    return alias_arn
    




def create_action_group(region, account_id, va_agent_id, kb_id):
    suffix = f"{region}-{account_id}"
    lambda_role_name = f'{agent_name}-lambda-role-{suffix}'
    lambda_code_path = "lambda_function.py"
    lambda_name = f'{agent_name}-{suffix}'
    bucket_name = f'{agent_name}-{suffix}'
    schema_key = f'{agent_name}-schema.json'

    try:
        print("Creating Agent action group")
        # Pause to make sure agent is created & in available state
        # nosemgrep
        time.sleep(15)
        assume_role_policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": "bedrock:InvokeModel",
                    "Principal": {
                        "Service": "lambda.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }

        assume_role_policy_document_json = json.dumps(assume_role_policy_document)

        lambda_iam_role = iam_client.create_role(
            RoleName=lambda_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json
        )

        # Pause to make sure role is created
        # nosemgrep
        time.sleep(10)
    except:
        lambda_iam_role = iam_client.get_role(RoleName=lambda_role_name)

    iam_client.attach_role_policy(
        RoleName=lambda_role_name,
        PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
    )
    # package lambda function for the agent action group
    # Package up the lambda function code
    s = BytesIO()
    z = zipfile.ZipFile(s, 'w')
    z.write(lambda_code_path)
    z.close()
    zip_content = s.getvalue()

    # Create Lambda Function
    lambda_function = lambda_client.create_function(
        FunctionName=lambda_name,
        Runtime='python3.12',
        Timeout=180,
        Role=lambda_iam_role['Role']['Arn'],
        Code={'ZipFile': zip_content},
        Handler='lambda_function.lambda_handler'
    )

    agent_action_group_response = bedrock_agent_client.create_agent_action_group(
        agentId=va_agent_id,
        agentVersion='DRAFT',
        actionGroupExecutor={
            'lambda': lambda_function['FunctionArn']
        },
        actionGroupName='PasswordResetActionGroup',
        apiSchema={
            's3': {
                's3BucketName': bucket_name,
                's3ObjectKey': schema_key
            }
        },
        description='Actions for password reset'
    )

    # Add required permissions to Lambda
    lm_response = lambda_client.add_permission(
        FunctionName=lambda_name,
        StatementId='allow_bedrock',
        Action='lambda:InvokeFunction',
        Principal='bedrock.amazonaws.com',
        SourceArn=f"arn:aws:bedrock:{region}:{account_id}:agent/{va_agent_id}",
    )

    # Add KB to agent
    agent_kb_description = bedrock_agent_client.associate_agent_knowledge_base(
        agentId=va_agent_id,
        agentVersion='DRAFT',
        description=f'Answer queries from prompts. Double check each source you reference from the CMS help guide to provide a good response. Ask if anything else is needed.',
        knowledgeBaseId=kb_id 
    )


def create_agent_role(region, account_id,knowledge_base_arn ):

    suffix = f"{region}-{account_id}"
    agent_name = "virtual-assistant-agent"
    bucket_name = f'{agent_name}-{suffix}'
    bucket_name = f'{agent_name}-{suffix}'
    schema_key = f'{agent_name}-schema.json'
    schema_arn = f'arn:aws:s3:::{bucket_name}/{schema_key}'
    
    va_agent_bedrock_allow_policy_name = f"va-bedrock-allow-{suffix}"
    va_agent_s3_allow_policy_name = f"va-s3-allow-{suffix}"
    va_agent_kb_allow_policy_name = f"va-kb-allow-{suffix}"
    
    agent_role_name = f'AmazonBedrockExecutionRoleForAgents_va'
   
    va_agent_bedrock_allow_policy_statement = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AmazonBedrockAgentBedrockFoundationModelPolicy",
                "Effect": "Allow",
                "Action": "bedrock:InvokeModel",
                "Resource": [
                    f"arn:aws:bedrock:{region}::foundation-model/*"
                ]
            }
        ]
    }

    bedrock_policy_json = json.dumps(va_agent_bedrock_allow_policy_statement)

    va_agent_bedrock_policy = iam_client.create_policy(
        PolicyName=va_agent_bedrock_allow_policy_name,
        PolicyDocument=bedrock_policy_json
    )

    bedrock_agent_s3_allow_policy_statement = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowAgentAccessOpenAPISchema",
                "Effect": "Allow",
                "Action": ["s3:GetObject"],
                "Resource": [
                    schema_arn
                ]
            }
        ]
    }


    bedrock_agent_s3_json = json.dumps(bedrock_agent_s3_allow_policy_statement)
    va_agent_s3_schema_policy = iam_client.create_policy(
        PolicyName=va_agent_s3_allow_policy_name,
        Description=f"Policy to allow invoke Lambda that was provisioned for it.",
        PolicyDocument=bedrock_agent_s3_json
    )

    va_agent_kb_retrival_policy_statement = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock:Retrieve"
                ],
                "Resource": [
                    knowledge_base_arn
                ]
            }
        ]
    }
    va_bedrock_agent_kb_json = json.dumps(va_agent_kb_retrival_policy_statement)

    va_agent_kb_schema_policy = iam_client.create_policy(
        PolicyName=va_agent_kb_allow_policy_name,
        Description=f"Policy to allow agent to retrieve documents from knowledge base.",
        PolicyDocument=va_bedrock_agent_kb_json
    )

    # Create IAM Role for the agent and attach IAM policies
    assume_role_policy_document = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {
                "Service": "bedrock.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }]
    }

    assume_role_policy_document_json = json.dumps(assume_role_policy_document)
    va_agent_role = iam_client.create_role(
        RoleName=agent_role_name,
        AssumeRolePolicyDocument=assume_role_policy_document_json
    )
    # nosemgrep
    time.sleep(15)

    iam_client.attach_role_policy(
        RoleName=agent_role_name,
        PolicyArn=va_agent_bedrock_policy['Policy']['Arn']
    )

    iam_client.attach_role_policy(
        RoleName=agent_role_name,
        PolicyArn=va_agent_s3_schema_policy['Policy']['Arn']
    )

    iam_client.attach_role_policy(
        RoleName=agent_role_name,
        PolicyArn=va_agent_kb_schema_policy['Policy']['Arn']
    )

    

    return va_agent_role['Role']['Arn']