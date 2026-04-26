#  CLI for the whole app, gets info through clearML_reader and aws_pricing
import click
import shlex
from clearml_reader import get_task_data
from aws_pricing import get_instance_price, get_gpu_type
from dotenv import load_dotenv
import os
import re
import copy
from knowledge_base import insert_experiment, search_experiments

load_dotenv()

VALID_REGION_FORMAT = r'^[a-z]+-[a-z]+-[0-9]+$'


def get_token_value(tokens, i, flag): # Helper for input sanitisation, bounds check for input string
    if i+1 >= len(tokens):
        click.echo(f"  Missing value for {flag}")
        return None
    return tokens[i+1].strip()

FLAG_MAP = {
    '--project': 'project',
    '--task': 'task',
    '--instance-type': 'instance_type',
    '--region': 'region',
    '--model': 'model',
    '--dataset': 'dataset',
}

REPORT_DEFAULTS = {
    'project': None,
    'task': None,
    'instance_type': None,
    'region': os.getenv('AWS_DEFAULT_REGION', None),
}

LOOKUP_DEFAULTS = {
    'model': None,
    'dataset': None,
    'instance_type': None,
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

def print_report(task_data, instance_type, price, gpu_type=None): # Used by report command
    runtime_seconds = task_data['runtime_seconds']
    actual_cost = (runtime_seconds / 3600) * price['price']

    print_experiment_summary(task_data)

    click.echo(f"\n--- Hyperparameters ---")
    for k, v in task_data['hyperparameters'].items():
        click.echo(f"  {k}: {v}")

    click.echo(f"\n--- Cost Analysis ---")
    click.echo(f"  Instance:             {instance_type}")
    if gpu_type:
        click.echo(f"  GPU:                  {gpu_type['manufacturer']} {gpu_type['name']} x{gpu_type['count']}")
    click.echo(f"  Price/hr:             ${price['price']}")
    click.echo(f"  Actual cost:          ${actual_cost:.4f}")

    for k, v in task_data['model_metrics'].items():
        if 'accuracy' in k and v > 0:
            click.echo(f"  Cost/accuracy point:  ${actual_cost / (v * 100):.4f}")

def run_report(tokens):
    args = parse_args(tokens, REPORT_DEFAULTS)
    if args is None:
        return

    if not validate_args(args, ['project', 'task', 'instance_type']):
        return

    click.echo(f"\nFetching ClearML experiment: {args['task']}...")
    try:
        task_data = get_task_data(args['project'], args['task']) # Experiment info (clearml API call)
    except Exception as e:
        click.echo(f"  ClearML error: {e}")
        return

    click.echo(f"\nFetching price for {args['instance_type']}...")
    try:
        price = get_instance_price(args['instance_type'], region=args['region']) # Pricing info (aws pricing API call)
    except Exception as e:
        click.echo(f"  AWS error: {e}")
        return

    if not price:
        click.echo(f"  Could not fetch price for {args['instance_type']}")
        return
    
    gpu_type = get_gpu_type(args['instance_type'], region=args['region']) # GPU info retrieval (ec2 API call)

    print_report(task_data, args['instance_type'], price, gpu_type)

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
            'compute_type': compute_type,
            'gpu_type': gpu_type
        }
        
        try:
            insert_experiment(record)
            click.echo("  Saved to knowledge base.")
        except Exception as e:
            click.echo(f"  Could not save to knowledge base: {e}")

def run_lookup(tokens):
    args = parse_args(tokens, LOOKUP_DEFAULTS)
    if args is None:
        return

    if not validate_args(args, ['model', 'dataset']):
        return

    click.echo(f"\nSearching knowledge base...")
    try:
        results = search_experiments(
            model=args['model'],
            dataset=args['dataset'],
            instance_type=args.get('instance_type')
        )
    except Exception as e:
        click.echo(f"  Knowledge base error: {e}")
        return

    if not results:
        click.echo(f"  No results found for {args['model']} on {args['dataset']}.")
        return

    click.echo(f"\n--- Knowledge Base Results ---")
    for i, r in enumerate(results, 1):
        accuracy = f"{r['test_accuracy'] * 100:.2f}%" if r['test_accuracy'] else 'N/A'
        cost_per_point = f"${r['cost_per_accuracy_point']:.4f}/accuracy point" if r['cost_per_accuracy_point'] else 'N/A'
        click.echo(f"  {i}. {r['model']} | {r['dataset']} | {r['instance_type']} | {r['runtime_seconds'] // 60}:{str(r['runtime_seconds'] % 60).zfill(2)}m | ${r['actual_cost']:.4f} | {accuracy} | {cost_per_point}")

    try:
        selection = int(input(f"\nSelect a result (1-{len(results)}) or 0 to cancel: ").strip())
    except ValueError:
        click.echo("  Invalid selection.")
        return

    if selection == 0:
        return

    if selection < 1 or selection > len(results):
        click.echo("  Invalid selection.")
        return

    selected = results[selection - 1]
    click.echo(f"\n--- Selected Experiment ---")
    click.echo(f"  Model:          {selected['model']}")
    click.echo(f"  Dataset:        {selected['dataset']}")
    click.echo(f"  Instance:       {selected['instance_type']} ({selected['cloud_provider']} {selected['compute_type']})")
    click.echo(f"  Region:         {selected['region']}")
    click.echo(f"  Runtime:        {selected['runtime_seconds'] // 60}:{str(selected['runtime_seconds'] % 60).zfill(2)}m")
    click.echo(f"  Price/hr:       ${selected['price_per_hour']}")
    click.echo(f"  Actual cost:    ${selected['actual_cost']:.4f}")
    click.echo(f"\n--- Model Performance ---")
    click.echo(f"  Test accuracy:  {selected['test_accuracy'] * 100:.2f}%" if selected['test_accuracy'] else "  Test accuracy:  N/A")
    click.echo(f"  Train loss:     {selected['train_loss']}" if selected['train_loss'] else "  Train loss:     N/A")
    click.echo(f"  Test loss:      {selected['test_loss']}" if selected['test_loss'] else "  Test loss:      N/A")
    click.echo(f"  Cost/acc point: ${selected['cost_per_accuracy_point']:.4f}" if selected['cost_per_accuracy_point'] else "  Cost/acc point: N/A")
    click.echo(f"\n--- Hyperparameters ---")
    for k, v in selected['hyperparameters'].items():
        click.echo(f"  {k}: {v}")
    click.echo(f"\n  ClearML Task ID: {selected['clearml_task_id']}")
    click.echo(f"  Recorded at:     {selected['created_at']}")

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
                click.echo("  report --project <name> --task <name> --instance-type <type> [--region <region>]")
                click.echo("  lookup --model <name> --dataset <name> [--instance-type <type>]")
                click.echo("  quit -- exit the tool\n")
                continue
            
            tokens = shlex.split(user_input)
            command = tokens[0]
            
            if command == 'report':
                run_report(tokens[1:])
            elif command == 'lookup':
                run_lookup(tokens[1:])
            else:
                click.echo(f"  Unknown command: '{command}'. Type 'help' for available commands.")
        
        except KeyboardInterrupt:
            click.echo("\nGoodbye!")
            break

if __name__ == '__main__':
    shell()