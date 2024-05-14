import boto3

sts_client = boto3.client('sts')
iam_client = boto3.client('iam')
s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')
bedrock_agent_client = boto3.client('bedrock-agent')
bedrock_agent_runtime_client = boto3.client('bedrock-agent-runtime')
agent_name = "virtual-assistant-agent"
# Get this information from the console/CLI for the launched instances.
agent_id="NENJLFDGN9"
knowledge_base_id="S77VRWSXCB"

def main():
    session = boto3.session.Session()
    region = session.region_name
    account_id = sts_client.get_caller_identity()["Account"]
    
    if delete_agent_kb(region, account_id):
        delete_lambda_function(region, account_id)
        delete_s3_bucket(region, account_id)

# delete agent by name
def delete_agent_kb(region, account_id):
    suffix = f"{region}-{account_id}"
    kb_role_name = f'BedrockExecutionRoleForKB_vakb'
    #kb_role_arn = f'arn:aws:iam::{account_id}:role/{kb_role_name}'
    kb_bedrock_allow_model_policy_name = f"va-kb-bedrock-allow-model-{suffix}"
    kb_bedrock_allow_model_policy_arn = f"arn:aws:iam::{account_id}:policy/{kb_bedrock_allow_model_policy_name}"
    kb_secretmanager_api_policy_name = f"va-kb-secretmanager-api-allow-{suffix}"
    kb_secretmanager_api_policy_arn = f"arn:aws:iam::{account_id}:policy/{kb_secretmanager_api_policy_name}"
    kb_s3_allow_policy_name = f"va-kb-s3-allow-{suffix}"
    kb_s3_allow_policy_arn = f"arn:aws:iam::{account_id}:policy/{kb_s3_allow_policy_name}"
    va_agent_bedrock_allow_policy_name = f"va-bedrock-allow-{suffix}"
    va_agent_bedrock_allow_policy_arn = f"arn:aws:iam::{account_id}:policy/{va_agent_bedrock_allow_policy_name}"
    va_agent_s3_allow_policy_name = f"va-s3-allow-{suffix}"
    va_agent_s3_allow_policy_arn = f"arn:aws:iam::{account_id}:policy/{va_agent_s3_allow_policy_name}"    
    va_agent_kb_allow_policy_name = f"va-kb-allow-{suffix}"
    va_agent_kb_allow_policy_arn = f"arn:aws:iam::{account_id}:policy/{va_agent_kb_allow_policy_name}"
    lambda_role_name = f'{agent_name}-lambda-role-{suffix}'
    agent_role_name = f'AmazonBedrockExecutionRoleForAgents_va'

    try:

        print("Deleting Agent...")

        aliaslist = bedrock_agent_client.list_agent_aliases(
            agentId=agent_id
        )
        
        #loop through alias list and delete every alias
        for alias in aliaslist['agentAliasSummaries']:         
            agent_alias_id = alias['agentAliasId']
            bedrock_agent_client.delete_agent_alias(
                agentId=agent_id,
                agentAliasId=agent_alias_id
            )
        print("Deleting Agent...")
        try:
            response = bedrock_agent_client.delete_agent(
                agentId=agent_id
            )
        except Exception as e:
            print("Exception")
            
        #print(response) 

        print("Deleting Knowledge base...")
        try:
            kb_response = bedrock_agent_client.delete_knowledge_base(
                knowledgeBaseId=knowledge_base_id
            )
        except Exception as e:           
            print("Exception")
        #print(kb_response) 

        print("Deleting policies & roles...")
        for policyarn in [
            va_agent_bedrock_allow_policy_arn, 
            va_agent_s3_allow_policy_arn, 
            va_agent_kb_allow_policy_arn,
            kb_bedrock_allow_model_policy_arn,
            kb_secretmanager_api_policy_arn,
            kb_s3_allow_policy_arn
        ]:
            try:
                response = iam_client.list_entities_for_policy(
                    PolicyArn=policyarn,
                    EntityFilter='Role'
                )         
                for role in response['PolicyRoles']:
                    try:
                        iam_client.detach_role_policy(
                            RoleName=role['RoleName'], 
                            PolicyArn=policyarn
                        )
                    except Exception as e:
                        print("Exception")
                try:
                    iam_client.delete_policy(
                        PolicyArn=policyarn
                    )
                except Exception as e:
                    print("Exception")
            except Exception as e:
                print("Exception")

        try:
            iam_client.detach_role_policy(RoleName=lambda_role_name, PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole')
        except Exception as e:
            print("Exception")

        for role_name in [
            agent_role_name, 
            lambda_role_name, 
            kb_role_name
        ]:
            try: 
                iam_client.delete_role(
                    RoleName=role_name
                )
            except Exception as e:
                print("Exception")
        return True        

    except Exception as e:
        print(f"Error occurred: {e}")
        return False
    
def get_all_agents():
    response = bedrock_agent_client.list_agents()

def delete_lambda_function(region, account_id):
    print("Deleting lambda function...")
    try:
        suffix = f"{region}-{account_id}"
        lambda_name = f'{agent_name}-{suffix}'
        lambda_client = boto3.client('lambda')
        lambda_client.delete_function(FunctionName=lambda_name)
        print(f"Lambda function {lambda_name} deleted")
    except Exception as e:
            print("Exception")

def delete_s3_bucket(region, account_id):
    print("Deleting S3 bucket with the content...")
    try:
        suffix = f"{region}-{account_id}"
        bucket_name = f'{agent_name}-{suffix}'
        #empty S3 bucket content
        s3_client.list_objects_v2(Bucket=bucket_name)['Contents']
        for obj in s3_client.list_objects_v2(Bucket=bucket_name)['Contents']:            
            s3_client.delete_object(Bucket=bucket_name, Key=obj['Key'])    
        s3_client.delete_bucket(Bucket=bucket_name)
        print(f"S3 bucket {bucket_name} deleted") 
    except Exception as e:
        print("Exception")
        

if __name__ == "__main__":
    main()