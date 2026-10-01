#!/usr/bin/env python3
"""Apply Dailsmart system tables and seed models directly on dograh-db-vm."""
import subprocess
import sys

zone = "us-central1-a"
vm   = "dograh-db-vm"

ddl_sql = """
CREATE TABLE IF NOT EXISTS system_ai_models (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(64) NOT NULL,
    service_type VARCHAR(32) NOT NULL,
    model_name VARCHAR(256) NOT NULL,
    display_name VARCHAR(256) NOT NULL,
    api_base_url VARCHAR(512),
    is_active BOOLEAN NOT NULL DEFAULT true,
    config_schema JSON NOT NULL DEFAULT '{}'::json,
    extra_config JSON NOT NULL DEFAULT '{}'::json,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_system_ai_models UNIQUE (provider, service_type, model_name)
);

CREATE INDEX IF NOT EXISTS ix_system_ai_models_service_type ON system_ai_models (service_type);
CREATE INDEX IF NOT EXISTS ix_system_ai_models_is_active ON system_ai_models (is_active);

CREATE TABLE IF NOT EXISTS org_billing_accounts (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL UNIQUE REFERENCES organizations(id) ON DELETE CASCADE,
    credits_balance NUMERIC(18, 6) NOT NULL DEFAULT 0,
    currency VARCHAR(8) NOT NULL DEFAULT 'INR',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_org_billing_accounts_org ON org_billing_accounts (organization_id);

CREATE TABLE IF NOT EXISTS org_billing_ledger (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    entry_type VARCHAR(32) NOT NULL,
    credits_delta NUMERIC(18, 6) NOT NULL,
    quantity NUMERIC(18, 6),
    quantity_unit VARCHAR(32),
    rate NUMERIC(18, 6),
    description TEXT,
    workflow_run_id INTEGER,
    meta JSON NOT NULL DEFAULT '{}'::json,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_org_billing_ledger_org ON org_billing_ledger (organization_id);
CREATE INDEX IF NOT EXISTS ix_org_billing_ledger_type ON org_billing_ledger (entry_type);
CREATE INDEX IF NOT EXISTS ix_org_billing_ledger_created ON org_billing_ledger (created_at);

-- Seed models
INSERT INTO system_ai_models (provider, service_type, model_name, display_name)
VALUES
    ('google', 'llm', 'gemini-2.5-flash', 'Google Gemini 2.5 Flash'),
    ('google', 'llm', 'gemini-2.0-flash', 'Google Gemini 2.0 Flash'),
    ('sarvam', 'llm', 'sarvam-2b', 'Sarvam 2B (Indian Languages)'),
    ('groq', 'llm', 'llama-3.3-70b-versatile', 'Groq Llama 3.3 70B (Fast)'),
    ('openai', 'llm', 'gpt-4o-mini', 'OpenAI GPT-4o Mini'),
    ('dograh', 'llm', 'default', 'Dailsmart Default LLM'),

    ('sarvam', 'stt', 'saarika:v2.5', 'Sarvam Saarika (Indian STT)'),
    ('deepgram', 'stt', 'nova-3-general', 'Deepgram Nova-3 (Multilingual)'),
    ('google', 'stt', 'default', 'Google Cloud STT'),
    ('dograh', 'stt', 'default', 'Dailsmart Default STT'),

    ('sarvam', 'tts', 'bulbul:v2', 'Sarvam Bulbul (Indian TTS)'),
    ('deepgram', 'tts', 'aura-2-helena-en', 'Deepgram Aura'),
    ('elevenlabs', 'tts', 'eleven_multilingual_v2', 'ElevenLabs Multilingual'),
    ('google', 'tts', 'default', 'Google Cloud TTS'),
    ('smallest', 'tts', 'lightning_v3.1', 'Smallest AI Lightning'),
    ('dograh', 'tts', 'default', 'Dailsmart Default Voice'),

    ('google_realtime', 'realtime', 'gemini-2.0-flash-exp', 'Google Gemini Live (Realtime)'),
    ('openai_realtime', 'realtime', 'gpt-4o-realtime-preview', 'OpenAI GPT-4o Realtime'),

    ('openai', 'embeddings', 'text-embedding-3-small', 'OpenAI text-embedding-3-small'),
    ('dograh', 'embeddings', 'dograh_embedding_v1', 'Dailsmart Embedding V1')
ON CONFLICT (provider, service_type, model_name) DO NOTHING;
"""

print("Executing DDL & seeding on dograh-db-vm...")
clean_lines = [line.strip() for line in ddl_sql.splitlines() if not line.strip().startswith("--")]
clean_sql = " ".join(clean_lines)

cmd = [
    "gcloud.cmd", "compute", "ssh", vm,
    "--zone", zone,
    "--command",
    f"sudo docker exec dograh-db-postgres-1 psql -U postgres -d postgres -c \"{clean_sql}\""
]

res = subprocess.run(cmd, capture_output=True, text=True)
print("STDOUT:", res.stdout)
print("STDERR:", res.stderr)
if res.returncode != 0:
    print("FAILED")
    sys.exit(1)
print("SUCCESS: Tables created and models seeded!")
