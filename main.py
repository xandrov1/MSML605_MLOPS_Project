#  CLI for the whole app, gets info through clearML_reader and aws_pricing
import click
from clearml_reader import get_task_data
from aws_pricing import get_ec2_instances, get_instance_price
from dotenv import load_dotenv

load_dotenv()

@click.group()
def cli():
    """ML Cost-Performance Analysis Tool"""
    pass
# Possible commands
@cli.command() 
@click.option('--project', required=True, help='ClearML project name')
@click.option('--task', required=True, help='ClearML task name')
@click.option('--instance-family', multiple=True, help='EC2 instance families e.g. g5 p3 t3')
@click.option('--region', default='us-east-1', help='AWS region')
@click.option('--pricing-model', 
              type=click.Choice(['OnDemand', 'Spot', 'Reserved']), 
              default='OnDemand',
              help='AWS pricing model')

def analyze(project, task, instance_family, region, pricing_model):
    """Analyze cost-performance for a ClearML experiment"""
    
    # Getting clearML data
    click.echo(f"\nFetching ClearML experiment: {task}...")
    task_data = get_task_data(project, task) 
    
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
    click.echo(f"\n--- Available Instances ({pricing_model} pricing) ---")
    instances = get_ec2_instances(instance_families=list(instance_family))

    for i in instances:
        price = get_instance_price(i['instance_type'], region=region, pricing_model=pricing_model)
        if price:
            click.echo(f"  {i['instance_type']} - ${price['price']}/hr | vCPUs: {i['vcpus']} | Memory: {i['memory_mb']}MB | GPU: {i['gpu']}")

if __name__ == '__main__':
    cli()