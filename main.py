#  MiniSHELL for the whole app, gets info through clearML_reader and aws_pricing
import click
import shlex
from clearml_reader import get_task_data
from aws_pricing import get_ec2_instances, get_instance_price
from dotenv import load_dotenv
import os
import re

load_dotenv()

VALID_PRICING_MODELS = ['ondemand', 'spot', 'reserved']
VALID_REGION_FORMAT = r'^[a-z]+-[a-z]+-[0-9]+$'


def parse_analyze_args(tokens):
    args = {
        'project': None,
        'task': None,
        'instance_family': [],
        'region': os.getenv('AWS_DEFAULT_REGION', 'us-east-1'),
        'pricing_model': 'OnDemand'
    }
    
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token == '--project':
            args['project'] = tokens[i+1].strip()
            i += 2
        elif token == '--task':
            args['task'] = tokens[i+1].strip()
            i += 2
        elif token == '--instance-family':
            args['instance_family'].append(tokens[i+1].lower().strip())
            i += 2
        elif token == '--region':
            args['region'] = tokens[i+1].strip()
            i += 2
        elif token == '--pricing-model':
            args['pricing_model'] = tokens[i+1].lower().strip()
            i += 2
        else:
            click.echo(f"  Unknown option: '{token}'")
            return None
    
    return args

def validate_analyze_args(args):
    errors = []
    
    if not args['project']:
        errors.append("  Missing --project")
    
    if not args['task']:
        errors.append("  Missing --task")
    
    if not args['instance_family']:
        errors.append("  Missing --instance-family")
    
    if args['pricing_model'] not in VALID_PRICING_MODELS:
        errors.append(f"  Invalid --pricing-model '{args['pricing_model']}'. Choose from: {', '.join(VALID_PRICING_MODELS)}")
    
    if not re.match(VALID_REGION_FORMAT, args['region']):
        errors.append(f"  Invalid --region format '{args['region']}'. Expected format: us-east-1")
    
    if errors:
        click.echo("\nErrors:")
        for e in errors:
            click.echo(e)
        return False
    
    return True

def run_analyze(tokens):
    args = parse_analyze_args(tokens)
    if args is None:
        return
    
    if not validate_analyze_args(args):
        return
    
    # Getting ClearML data
    click.echo(f"\nFetching ClearML experiment: {args['task']}...")
    try:
        task_data = get_task_data(args['project'], args['task'])
    except Exception as e:
        click.echo(f"  ClearML error: {e}")
        return
    
    click.echo(f"\n--- Experiment Summary ---")
    click.echo(f"  Name:   {task_data['name']}")
    click.echo(f"  ID:     {task_data['id']}")
    click.echo(f"  Status: {task_data['status']}")

    click.echo(f"\n--- Hyperparameters ---")
    for k, v in task_data['hyperparameters'].items():
        click.echo(f"  {k}: {v}")

    click.echo(f"\n--- Model Performance ---")
    for k, v in task_data['model_metrics'].items():
        click.echo(f"  {k}: {v}")

    click.echo(f"\n--- Machine Metrics ---")
    for k, v in task_data['machine_metrics'].items():
        clean_key = k.replace(':monitor:machine/', '').replace(':monitor:machine', '')
        click.echo(f"  {clean_key}: {v}")

    # Getting AWS data
    click.echo(f"\nFetching AWS instances...")
    try:
        instances = get_ec2_instances(instance_families=args['instance_family'])
    except Exception as e:
        click.echo(f"  AWS error: {e}")
        return
    
    if not instances:
        click.echo(f"  No instances found for families: {args['instance_family']}")
        return

    click.echo(f"\n--- Available Instances ({args['pricing_model']} pricing) ---")
    for i in instances:
        try:
            price = get_instance_price(i['instance_type'], region=args['region'], pricing_model=args['pricing_model'])
            if price:
                click.echo(f"  {i['instance_type']} - ${price['price']}/hr | vCPUs: {i['vcpus']} | Memory: {i['memory_mb']}MB | GPU: {i['gpu']}")
        except Exception as e:
            click.echo(f"  Could not fetch price for {i['instance_type']}: {e}")

def shell():
    click.echo("ML Cost-Performance Tool")
    click.echo("Type 'help' for available commands or 'quit' to exit\n")
    
    while True:
        try:
            user_input = input("> ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                click.echo("Goodbye!")
                break
            
            if user_input.lower() == 'help':
                click.echo("\nAvailable commands:")
                click.echo("  analyze --project <name> --task <name> --instance-family <family> [--region <region>] [--pricing-model <OnDemand|Spot|Reserved>]")
                click.echo("  quit -- exit the tool\n")
                continue
            
            tokens = shlex.split(user_input)
            command = tokens[0]
            
            if command == 'analyze':
                run_analyze(tokens[1:])
            else:
                click.echo(f"  Unknown command: '{command}'. Type 'help' for available commands.")
        
        except KeyboardInterrupt:
            click.echo("\nGoodbye!")
            break

if __name__ == '__main__':
    shell()