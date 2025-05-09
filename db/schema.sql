-- Create enum types for the various enums in the code
CREATE TYPE vcon_version AS ENUM ('0.0.2');
CREATE TYPE encoding_type AS ENUM ('base64url', 'json', 'none');
CREATE TYPE dialog_type AS ENUM ('recording', 'text', 'transfer', 'incomplete');
CREATE TYPE disposition_type AS ENUM ('no-answer', 'congestion', 'failed', 'busy', 'hung-up', 'voicemail-no-message');

-- Main vCon table
CREATE TABLE vcons (
    id SERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE,
    vcon vcon_version NOT NULL DEFAULT '0.0.2',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE,
    subject TEXT,
    meta JSONB,
    -- For redacted/appended/group references
    redacted_uuid UUID,
    redacted_type TEXT,
    appended_uuid UUID,
    group_items JSONB,
    -- The complete vCon JSON
    vcon_json JSONB NOT NULL
);

-- Materialized view for parties
CREATE MATERIALIZED VIEW vcon_parties AS
SELECT 
    v.id as vcon_id,
    v.uuid as vcon_uuid,
    (p->>'tel') as tel,
    (p->>'stir') as stir,
    (p->>'mailto') as mailto,
    (p->>'name') as name,
    (p->>'validation') as validation,
    (p->>'gmlpos') as gmlpos,
    (p->>'uuid') as party_uuid,
    (p->>'role') as role,
    (p->>'contact_list') as contact_list,
    (p->'civicaddress') as civicaddress,
    (p->'meta') as meta
FROM vcons v,
     jsonb_array_elements(v.vcon_json->'parties') as p;

-- Materialized view for dialogs
CREATE MATERIALIZED VIEW vcon_dialogs AS
SELECT 
    v.id as vcon_id,
    v.uuid as vcon_uuid,
    (d->>'type')::dialog_type as type,
    (d->>'start')::TIMESTAMP WITH TIME ZONE as start,
    (d->>'duration')::FLOAT as duration,
    (d->'parties') as parties,
    (d->>'originator')::INT as originator,
    (d->>'mediatype') as mediatype,
    (d->>'filename') as filename,
    (d->>'body') as body,
    (d->>'encoding')::encoding_type as encoding,
    (d->>'url') as url,
    (d->'content_hash') as content_hash,
    (d->>'disposition')::disposition_type as disposition,
    (d->'party_history') as party_history,
    (d->>'transferee')::INT as transferee,
    (d->>'transferor')::INT as transferor,
    (d->>'transfer_target')::INT as transfer_target,
    (d->>'original')::INT as original,
    (d->>'consultation')::INT as consultation,
    (d->>'target_dialog')::INT as target_dialog,
    (d->>'campaign') as campaign,
    (d->>'interaction_type') as interaction_type,
    (d->>'interaction_id') as interaction_id,
    (d->>'skill') as skill,
    (d->>'application') as application,
    (d->>'message_id') as message_id,
    (d->'meta') as meta
FROM vcons v,
     jsonb_array_elements(v.vcon_json->'dialog') as d;

-- Materialized view for analysis
CREATE MATERIALIZED VIEW vcon_analysis AS
SELECT 
    v.id as vcon_id,
    v.uuid as vcon_uuid,
    (a->>'type') as type,
    (a->'dialog') as dialog,
    (a->>'mediatype') as mediatype,
    (a->>'filename') as filename,
    (a->>'vendor') as vendor,
    (a->>'product') as product,
    (a->>'schema') as schema,
    (a->>'body') as body,
    (a->>'encoding')::encoding_type as encoding,
    (a->>'url') as url,
    (a->'content_hash') as content_hash
FROM vcons v,
     jsonb_array_elements(v.vcon_json->'analysis') as a;

-- Materialized view for attachments
CREATE MATERIALIZED VIEW vcon_attachments AS
SELECT 
    v.id as vcon_id,
    v.uuid as vcon_uuid,
    (a->>'type') as type,
    (a->>'start')::TIMESTAMP WITH TIME ZONE as start,
    (a->>'party')::INT as party,
    (a->>'mediatype') as mediatype,
    (a->>'filename') as filename,
    (a->>'dialog')::INT as dialog,
    (a->>'body') as body,
    (a->>'encoding')::encoding_type as encoding,
    (a->>'url') as url,
    (a->'content_hash') as content_hash
FROM vcons v,
     jsonb_array_elements(v.vcon_json->'attachments') as a;

-- Create indexes for common queries
CREATE INDEX idx_vcons_uuid ON vcons(uuid);
CREATE INDEX idx_vcons_created_at ON vcons(created_at);
CREATE INDEX idx_vcon_parties_tel ON vcon_parties(tel);
CREATE INDEX idx_vcon_parties_name ON vcon_parties(name);
CREATE INDEX idx_vcon_dialogs_type ON vcon_dialogs(type);
CREATE INDEX idx_vcon_dialogs_start ON vcon_dialogs(start);
CREATE INDEX idx_vcon_analysis_type ON vcon_analysis(type);
CREATE INDEX idx_vcon_analysis_vendor ON vcon_analysis(vendor);
CREATE INDEX idx_vcon_attachments_type ON vcon_attachments(type);

-- Function to refresh all materialized views
CREATE OR REPLACE FUNCTION refresh_vcon_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY vcon_parties;
    REFRESH MATERIALIZED VIEW CONCURRENTLY vcon_dialogs;
    REFRESH MATERIALIZED VIEW CONCURRENTLY vcon_analysis;
    REFRESH MATERIALIZED VIEW CONCURRENTLY vcon_attachments;
END;
$$ LANGUAGE plpgsql; 