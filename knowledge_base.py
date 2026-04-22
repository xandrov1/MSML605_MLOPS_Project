# Handles all interactions with the Supabase knowledge base
from supabase import create_client
from dotenv import load_dotenv
import os
import re

load_dotenv()

def get_client():
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_ANON_KEY')
    if not url or not key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_ANON_KEY in .env")
    return create_client(url, key)

def normalize_name(name):
    return re.sub(r'[-_\s]', '', name).lower()

def insert_experiment(record):
    record['model'] = normalize_name(record['model'])
    record['dataset'] = normalize_name(record['dataset'])
    client = get_client()
    response = client.table('experiments').insert(record).execute()
    return response

def search_experiments(model=None, dataset=None, instance_type=None):
    client = get_client()
    query = client.table('experiments').select('*')
    
    if model:
        query = query.ilike('model', f'%{normalize_name(model)}%')
    if dataset:
        query = query.ilike('dataset', f'%{normalize_name(dataset)}%')
    if instance_type:
        query = query.eq('instance_type', instance_type)
    
    response = query.execute()
    return response.data