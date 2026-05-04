/* 
Knowledge base supabase (PostGRE SQL) code to build database. Create with RLS on. 
*/

CREATE TABLE experiments (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at TIMESTAMP DEFAULT NOW(),
    model VARCHAR NOT NULL,
    dataset VARCHAR NOT NULL,
    clearml_task_id VARCHAR NOT NULL,
    clearml_project VARCHAR NOT NULL,
    hyperparameters JSONB,
    instance_type VARCHAR NOT NULL,
    region VARCHAR NOT NULL,
    cloud_provider VARCHAR NOT NULL,
    compute_type VARCHAR NOT NULL,
    price_per_hour FLOAT NOT NULL,
    runtime_seconds INTEGER NOT NULL,
    actual_cost FLOAT NOT NULL,
    test_accuracy FLOAT,
    train_loss FLOAT,
    test_loss FLOAT,
    cost_per_accuracy_point FLOAT,
    gpu_type JSONB
);

CREATE POLICY "allow_read" ON experiments
FOR SELECT USING (true);

CREATE POLICY "allow_insert" ON experiments
FOR INSERT WITH CHECK (true);