import boto3
import json
from dotenv import load_dotenv
import os

load_dotenv()

def get_ec2_instances(): # Gets EC2's instances info. Needs "AmazonEC2FullAccess" policy on IAM group
    ec2 = boto3.client('ec2', region_name=os.getenv('AWS_DEFAULT_REGION'))
    
    response = ec2.describe_instance_types() # JSON with all info on ec2's
    #     Filters=[
    #         {
    #             'Name': 'instance-type',
    #             'Values': ['t3.*', 'p3.*', 'g4dn.*']  # common ML instance families
    #         }
    #     ]
    # )
    
    instances = []
    for instance in response['InstanceTypes']:
        info = {
            'instance_type': instance['InstanceType'],
            'vcpus': instance['VCpuInfo']['DefaultVCpus'],
            'memory_mb': instance['MemoryInfo']['SizeInMiB'],
            'gpu': len(instance.get('GpuInfo', {}).get('Gpus', [])) > 0
        }
        instances.append(info)
    
    return instances

def get_instance_price(instance_type, region='us-east-1'): # Gets price per hour of each instance. Needs "AWSPriceListServiceFullAccess" policy on IAM group
    pricing = boto3.client('pricing', region_name='us-east-1')
    
    response = pricing.get_products( # JSON with all prices
        ServiceCode='AmazonEC2',
        Filters=[ # Prices vary on 
            {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type}, # Instance type
            {'Type': 'TERM_MATCH', 'Field': 'regionCode', 'Value': region}, # Region
            {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'}, # OS
            {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'}, # Host tenancy type
            {'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': 'Used'}, # Capacitus 
            {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'}, # Which software was preinstalled on the instance
        ] 
    )
    
    for price in response['PriceList']:
        price_data = json.loads(price)
        terms = price_data.get('terms', {}).get('OnDemand', {}) # Getting on demand pricing
        for term in terms.values():
            for dimension in term['priceDimensions'].values():
                usd = dimension['pricePerUnit'].get('USD', '0')
                if float(usd) > 0:
                    return float(usd)
    return None

    # Response's JSON structure for reference:
    # {
    #     "product": {
    #         "instanceType": "g5.4xlarge",
    #         "operatingSystem": "Linux",
    #         ...
    #     },
    #     "terms": {
    #         "OnDemand": {
    #             "RANDOMKEYID123": {
    #                 "priceDimensions": {
    #                     "ANOTHERRANDOMKEY": {
    #                         "pricePerUnit": {
    #                             "USD": "1.6240000000"
    #                         },
    #                         "description": "per On Demand Linux g5.4xlarge Instance Hour",
    #                         "unit": "Hrs"
    #                     }
    #                 }
    #             }
    #         },
    #         "Reserved": {
    #         ...
    #         }
    #     }
    # }

if __name__ == "__main__":
    print("Available ML instances:")
    instances = get_ec2_instances()
    for i in instances:
        print(f"\n  {i['instance_type']}")
        print(f"    vCPUs: {i['vcpus']}")
        print(f"    Memory: {i['memory_mb']}MB")
        print(f"    GPU: {i['gpu']}")
        price = get_instance_price(i['instance_type'])
        print(f"    Price/hr: ${price}")

# To do: make it so user can change filters values 