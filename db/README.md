# PostgreSQL Schema for vCons

This directory contains the PostgreSQL schema for storing and querying vCon data. The schema is designed to efficiently store vCon objects while providing easy access to their components through materialized views.

## Schema Overview

The schema consists of:

1. A main `vcons` table that stores:
   - All top-level vCon properties
   - The complete vCon JSON in a JSONB column
   - References to redacted/appended/group items

2. Materialized views for each component:
   - `vcon_parties`: Extracts party information
   - `vcon_dialogs`: Extracts dialog information
   - `vcon_analysis`: Extracts analysis information
   - `vcon_attachments`: Extracts attachment information

## Key Features

- Uses PostgreSQL's JSONB type for flexible JSON storage
- Creates proper enum types for constrained fields
- Provides materialized views for efficient querying of nested data
- Includes indexes for common query patterns
- Handles timestamps with timezone information
- Supports concurrent refresh of materialized views

## Usage Examples

### Inserting a vCon

```sql
INSERT INTO vcons (uuid, vcon, created_at, vcon_json)
VALUES (
    '123e4567-e89b-12d3-a456-426614174000',
    '0.0.2',
    NOW(),
    '{"vcon": "0.0.2", "uuid": "123e4567-e89b-12d3-a456-426614174000", ...}'::jsonb
);
```

### Querying Parties

```sql
-- Find all parties with a specific phone number
SELECT * FROM vcon_parties WHERE tel = '+1234567890';

-- Find all parties with a specific name
SELECT * FROM vcon_parties WHERE name = 'John Doe';
```

### Querying Dialogs

```sql
-- Find all text dialogs
SELECT * FROM vcon_dialogs WHERE type = 'text';

-- Find dialogs within a time range
SELECT * FROM vcon_dialogs 
WHERE start BETWEEN '2024-01-01' AND '2024-12-31';
```

### Querying Analysis

```sql
-- Find all analysis by a specific vendor
SELECT * FROM vcon_analysis WHERE vendor = 'example';

-- Find analysis of a specific type
SELECT * FROM vcon_analysis WHERE type = 'sentiment';
```

### Querying Attachments

```sql
-- Find all attachments of a specific type
SELECT * FROM vcon_attachments WHERE type = 'transcript';
```

## Maintaining Materialized Views

The materialized views need to be refreshed after any changes to the vcons table. You can refresh them using the provided function:

```sql
SELECT refresh_vcon_views();
```

You can set up automatic refresh in several ways:

1. Create a trigger to refresh views after updates
2. Set up a scheduled job to refresh views periodically
3. Refresh views manually after batch updates

## Indexes

The schema includes indexes for common query patterns:

- `idx_vcons_uuid`: For looking up vCons by UUID
- `idx_vcons_created_at`: For time-based queries
- `idx_vcon_parties_tel`: For phone number lookups
- `idx_vcon_parties_name`: For name lookups
- `idx_vcon_dialogs_type`: For dialog type filtering
- `idx_vcon_dialogs_start`: For time-based dialog queries
- `idx_vcon_analysis_type`: For analysis type filtering
- `idx_vcon_analysis_vendor`: For vendor filtering
- `idx_vcon_attachments_type`: For attachment type filtering

## Requirements

- PostgreSQL 12 or later (for JSONB support)
- Sufficient disk space for the materialized views
- Appropriate permissions to create tables and views

## Installation

To install the schema:

1. Create a new database:
```sql
CREATE DATABASE vcon_db;
```

2. Connect to the database and run the schema.sql file:
```bash
psql -d vcon_db -f schema.sql
``` 