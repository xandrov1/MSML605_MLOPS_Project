# Connect to AWS and get EC2 instances data

import boto3
import json
from dotenv import load_dotenv
import os

load_dotenv()

def get_ec2_instances(instance_families=None, region=None): # Gets EC2's instances info. Needs "AmazonEC2FullAccess" policy on IAM group
    ec2 = boto3.client('ec2', region_name=region or os.getenv('AWS_DEFAULT_REGION'))
    
    filters = []
    if instance_families:
        patterns = [f'{family}.*' for family in instance_families]
        filters.append({
            'Name': 'instance-type',
            'Values': patterns
        })
    
    response = ec2.describe_instance_types(Filters=filters) # JSON with all info on ec2's
    
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

def get_instance_price( 
    instance_type, 
    region='us-east-1', #  Gets overridden if the user passes a different region from main.py
    operatingSystem='Linux', 
    tenancy='Shared', 
    pricing_model=None,
    capacity_status='Used',
    preinstalled_sw='NA',
): # Gets price per hour of each instance. Needs "AWSPriceListServiceFullAccess" policy on IAM group
    
    # --- SPOT: disabled, implementation preserved for possible future use ---
    # if pricing_model == 'spot':
    #     ec2 = boto3.client('ec2', region_name=region)
    #     response = ec2.describe_spot_price_history(
    #         InstanceTypes=[instance_type],
    #         ProductDescriptions=['Linux/UNIX'],
    #         MaxResults=1
    #     )
    #     if response['SpotPriceHistory']:
    #         spot = response['SpotPriceHistory'][0]
    #         return {
    #             'price': float(spot['SpotPrice']),
    #             'timestamp': spot['Timestamp'].strftime('%Y-%m-%d %H:%M:%S')
    #         }
    #     return None
    # --------------------------------------------------------------

    # OnDemand
    pricing = boto3.client('pricing', region_name='us-east-1') # region_name is where to connect to the API. Never changes regardless of user input, because of the two-region limitation
    response = pricing.get_products(
        ServiceCode='AmazonEC2',
        Filters=[
            {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
            {'Type': 'TERM_MATCH', 'Field': 'regionCode', 'Value': region}, # Region here is which region's prices to return
            {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': operatingSystem},
            {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': tenancy},
            {'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': capacity_status},
            {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': preinstalled_sw},
        ]
    )
    for price in response['PriceList']:
        price_data = json.loads(price)
        terms = price_data.get('terms', {}).get('OnDemand', {})
        for term in terms.values():
            for dimension in term['priceDimensions'].values():
                usd = dimension['pricePerUnit'].get('USD', '0')
                if float(usd) > 0:
                    return {'price': float(usd), 'timestamp': None}
    return None