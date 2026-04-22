#  CLI for the whole app, gets info through clearML_reader and aws_pricing
import click
import shlex
from clearml_reader import get_task_data
from aws_pricing import get_ec2_instances, get_instance_price
from dotenv import load_dotenv
import os
import re
import copy
from knowledge_base import insert_experiment

load_dotenv()

VALID_PRICING_MODELS = ['ondemand', 'spot']
VALID_REGION_FORMAT = r'^[a-z]+-[a-z]+-[0-9]+$'


def get_token_value(tokens, i, flag): # Helper for input sanitisation, bounds check for input string
    if i+1 >= len(tokens):
        click.echo(f"  Missing value for {flag}")
        return None
    return tokens[i+1].strip()

FLAG_MAP = {
    '--project': 'project',
    '--task': 'task',
    '--instance-family': 'instance_family',
    '--instance-type': 'instance_type',
    '--region': 'region',
    '--pricing-model': 'pricing_model',
}

def parse_args(tokens, defaults):
    args = copy.deepcopy(defaults)  # Copy defaults so we don't mutate the original
    
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token not in FLAG_MAP:
            click.echo(f"  Unknown option: '{token}'")
            return None
        
        value = get_token_value(tokens, i, token)
        if value is None:
            return None
        
        key = FLAG_MAP[token]
        if isinstance(args.get(key), list):
            args[key].append(value.lower())
        else:
            args[key] = value.lower() if key in ['pricing_model'] else value
        
        i += 2
    
    return args

def validate_args(args, required_fields):
    errors = []
    
    for field in required_fields:
        if not args.get(field):
            errors.append(f"  Missing --{field.replace('_', '-')}")
    
    if 'pricing_model' in args and args['pricing_model'] not in VALID_PRICING_MODELS:
        errors.append(f"  Invalid --pricing-model '{args['pricing_model']}'. Choose from: {', '.join(VALID_PRICING_MODELS)}")
    
    if args.get('region') and not re.match(VALID_REGION_FORMAT, args['region']):
        errors.append(f"  Invalid --region format '{args['region']}'. Expected format: us-east-1")
    
    if errors:
        click.echo("\nErrors:")
        for e in errors:
            click.echo(e)
        return False
    
    return True

def print_experiment_summary(task_data): # Used by both print results and print_report
    click.echo(f"\n--- Experiment Summary ---")
    click.echo(f"  Name:   {task_data['name']}")
    click.echo(f"  ID:     {task_data['id']}")
    click.echo(f"  Status: {task_data['status']}")
    click.echo(f"  Runtime: {task_data['runtime_seconds'] // 60}:{str(task_data['runtime_seconds'] % 60).zfill(2)}m")

    click.echo(f"\n--- Model Performance ---")
    for k, v in task_data['model_metrics'].items():
        if 'accuracy' in k:
            click.echo(f"  {k}: {v:.4f} ({v * 100:.2f}%)")
        else:
            click.echo(f"  {k}: {v}")

def print_results(task_data, pricing_model, instance_prices): # Print all results fetched from API calls, used by analyze command

    print_experiment_summary(task_data)

    click.echo(f"\n--- Hyperparameters ---")
    for k, v in task_data['hyperparameters'].items():
        click.echo(f"  {k}: {v}")

    click.echo(f"\n--- Machine Metrics ---")
    for k, v in task_data['machine_metrics'].items():
        click.echo(f"  {k}: {v}")

    # AWS data
    click.echo(f"\n--- Available Instances ({pricing_model} pricing) ---")
    for instance, price in instance_prices:
        if price:
            click.echo(f"  {instance['instance_type']} - ${price['price']}/hr | vCPUs: {instance['vcpus']} | Memory: {instance['memory_mb']}MB | GPU: {instance['gpu']}")

def print_report(task_data, instance_type, price): # Used by report command
    runtime_seconds = task_data['runtime_seconds']
    actual_cost = (runtime_seconds / 3600) * price['price']

    print_experiment_summary(task_data)

    click.echo(f"\n--- Cost Analysis ---")
    click.echo(f"  Instance:             {instance_type}")
    click.echo(f"  Price/hr:             ${price['price']}")
    click.echo(f"  Actual cost:          ${actual_cost:.4f}")
    for k, v in task_data['model_metrics'].items():
        if 'accuracy' in k and v > 0:
            click.echo(f"  Cost/accuracy point:  ${actual_cost / (v * 100):.4f}")

ANALYZE_DEFAULTS = {
    'project': None,
    'task': None,
    'instance_family': [],
    'region': os.getenv('AWS_DEFAULT_REGION', None),
    'pricing_model': 'ondemand'
}

REPORT_DEFAULTS = {
    'project': None,
    'task': None,
    'instance_type': None,
    'region': os.getenv('AWS_DEFAULT_REGION', None),
}

def run_analyze(tokens):
    args = parse_args(tokens, ANALYZE_DEFAULTS)

    if args is None: # Check none of the args is empty
        return
    
    if not validate_args(args, ['project', 'task', 'instance_family']): # Check args aren't invalid
        return
    
    if args['pricing_model'] == 'spot': # Spot pricing not available yet
        click.echo("\n  [!] Spot pricing is not yet available. Please re-run with --pricing-model ondemand.")
        return
    
    # Getting ClearML data 
    click.echo(f"\nFetching ClearML experiment: {args['task']}...")
    try:
        task_data = get_task_data(args['project'], args['task']) # ClearML API call; from clearml_reader
    except Exception as e:
        click.echo(f"  ClearML error: {e}")
        return

    # Getting AWS data
    click.echo(f"\nFetching AWS instances...")
    try:
        instances = get_ec2_instances(instance_families=args['instance_family'], region=args['region']) # AWS API call from aws_pricing
    except Exception as e:
        click.echo(f"  AWS error: {e}")
        return
    
    if not instances: # Instance family not found error
        click.echo(f"  No instances found for families: {args['instance_family']}")
        return

    instance_prices = [] # Instance prices
    for instance in instances:
        try:
            price = get_instance_price(instance['instance_type'], region=args['region'], pricing_model=args['pricing_model']) # AWS API call from aws_pricing (uses different API than earlier one)
            instance_prices.append((instance, price))
        except Exception as e:
            click.echo(f"  Could not fetch price for {instance['instance_type']}: {e}")

    print_results(task_data, args['pricing_model'], instance_prices)

def run_report(tokens):
    args = parse_args(tokens, REPORT_DEFAULTS)
    if args is None:
        return

    if not validate_args(args, ['project', 'task', 'instance_type']):
        return

    click.echo(f"\nFetching ClearML experiment: {args['task']}...")
    try:
        task_data = get_task_data(args['project'], args['task'])
    except Exception as e:
        click.echo(f"  ClearML error: {e}")
        return

    click.echo(f"\nFetching price for {args['instance_type']}...")
    try:
        price = get_instance_price(args['instance_type'], region=args['region'])
    except Exception as e:
        click.echo(f"  AWS error: {e}")
        return

    if not price:
        click.echo(f"  Could not fetch price for {args['instance_type']}")
        return

    print_report(task_data, args['instance_type'], price)

    save = input("\nSave this result to the knowledge base? (yes/no): ").strip().lower()
    if save == 'yes':
        model = input("  Model architecture: ").strip()
        dataset = input("  Dataset: ").strip()
        cloud = input("  Cloud provider (aws): ").strip().lower()
        
        cloud_map = { # Will change as more cloud computing platforms get supported
            'aws': ('AWS', 'EC2'),
        }
        
        if cloud not in cloud_map:
            click.echo(f"  Unknown cloud provider '{cloud}'. Record not saved.")
            return
        
        cloud_provider, compute_type = cloud_map[cloud]
        
        record = {
            'model': model,
            'dataset': dataset,
            'clearml_task_id': task_data['id'],
            'clearml_project': args['project'],
            'hyperparameters': task_data['hyperparameters'],
            'instance_type': args['instance_type'],
            'region': args['region'] or 'us-east-1',
            'price_per_hour': price['price'],
            'runtime_seconds': task_data['runtime_seconds'],
            'actual_cost': (task_data['runtime_seconds'] / 3600) * price['price'],
            'test_accuracy': task_data['model_metrics'].get('test/accuracy'),
            'train_loss': task_data['model_metrics'].get('train/loss'),
            'test_loss': task_data['model_metrics'].get('test/loss'),
            'cost_per_accuracy_point': (task_data['runtime_seconds'] / 3600) * price['price'] / (task_data['model_metrics'].get('test/accuracy', 1) * 100),
            'cloud_provider': cloud_provider,
            'compute_type': compute_type
        }
        
        try:
            insert_experiment(record)
            click.echo("  Saved to knowledge base.")
        except Exception as e:
            click.echo(f"  Could not save to knowledge base: {e}")

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
                click.echo("  analyze --project <name> --task <name> --instance-family <family> [--region <region>] [--pricing-model <ondemand|spot>]")
                click.echo("  report --project <name> --task <name> --instance-type <type> [--region <region>]")
                click.echo("  quit -- exit the tool\n")
                continue
            
            tokens = shlex.split(user_input)
            command = tokens[0]
            
            if command == 'analyze':
                run_analyze(tokens[1:])
            elif command == 'report':
                run_report(tokens[1:])
            else:
                click.echo(f"  Unknown command: '{command}'. Type 'help' for available commands.")
        
        except KeyboardInterrupt:
            click.echo("\nGoodbye!")
            break

if __name__ == '__main__':
    shell()