"""Initial schema: PLM Studio Phase 1

Revision ID: 0001
Revises: -
Create Date: 2026-11-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SQL = """
CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email varchar UNIQUE NOT NULL,
  password_hash varchar NOT NULL,
  role varchar NOT NULL DEFAULT 'viewer'
    CHECK (role IN ('viewer','editor','approver','admin')),
  created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO users (id, email, password_hash, role)
VALUES ('00000000-0000-0000-0000-000000000001', 'admin@plm.local',
        'seeded-no-login', 'admin');

CREATE TABLE part_classes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code varchar UNIQUE NOT NULL,
  name varchar NOT NULL,
  default_attributes jsonb NOT NULL DEFAULT '{}'
);

INSERT INTO part_classes (code, name) VALUES
  ('MECH', 'Mechanik'),
  ('ELEC', 'Elektronik'),
  ('CONS', 'Consumables'),
  ('PACK', 'Verpackung');

CREATE TABLE number_ranges (
  prefix varchar PRIMARY KEY,
  next_value integer NOT NULL DEFAULT 1,
  padding integer NOT NULL DEFAULT 6
);

INSERT INTO number_ranges (prefix) VALUES
  ('P-'), ('ASM-'), ('DOC-'), ('ECR-'), ('ECO-'), ('RPT-');

CREATE TABLE parts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  part_number varchar UNIQUE NOT NULL,
  name varchar NOT NULL,
  description text,
  part_type varchar NOT NULL CHECK (part_type IN ('part','assembly')),
  class_id uuid NOT NULL REFERENCES part_classes(id),
  attributes jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE part_revisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  part_id uuid NOT NULL REFERENCES parts(id),
  revision varchar NOT NULL,
  status varchar NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','review','released','obsolete')),
  change_reason text NOT NULL,
  created_by uuid NOT NULL REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (part_id, revision)
);

CREATE FUNCTION prevent_mutation_of_released() RETURNS trigger AS $$
BEGIN
  IF OLD.status = 'released' AND TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'released revision ist immutable: neue Revision anlegen';
  END IF;
  RETURN COALESCE(NEW, OLD);
END $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_immutable_released
BEFORE UPDATE OR DELETE ON part_revisions
FOR EACH ROW EXECUTE FUNCTION prevent_mutation_of_released();

CREATE TABLE workflow_transitions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type varchar NOT NULL
    CHECK (entity_type IN ('part_revision','doc_revision','ecr','eco')),
  from_status varchar NOT NULL,
  to_status varchar NOT NULL,
  required_role varchar NOT NULL
    CHECK (required_role IN ('viewer','editor','approver','admin'))
);

INSERT INTO workflow_transitions (entity_type, from_status, to_status, required_role) VALUES
  ('part_revision','draft','review','editor'),
  ('part_revision','review','draft','editor'),
  ('part_revision','review','released','approver'),
  ('part_revision','draft','obsolete','editor'),
  ('part_revision','released','obsolete','approver');

CREATE TABLE audit_log (
  id bigserial PRIMARY KEY,
  entity_type varchar NOT NULL,
  entity_id uuid NOT NULL,
  action varchar NOT NULL,
  old_values jsonb,
  new_values jsonb,
  reason text,
  user_id uuid NOT NULL REFERENCES users(id),
  at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  doc_number varchar UNIQUE NOT NULL,
  doc_type varchar NOT NULL
    CHECK (doc_type IN ('vector','raster','cad','report','other')),
  title varchar NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE doc_revisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES documents(id),
  revision varchar NOT NULL,
  status varchar NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','review','released','obsolete')),
  change_reason text NOT NULL,
  created_by uuid NOT NULL REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (document_id, revision)
);

CREATE TABLE doc_files (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  doc_rev_id uuid NOT NULL REFERENCES doc_revisions(id),
  filename varchar NOT NULL,
  storage_key varchar NOT NULL,
  mime_type varchar NOT NULL,
  is_original boolean NOT NULL DEFAULT true,
  preview_file_id uuid REFERENCES doc_files(id)
);

CREATE TABLE doc_links (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES documents(id),
  part_id uuid NOT NULL REFERENCES parts(id),
  link_type varchar NOT NULL CHECK (link_type IN ('referenced-by','owned-by'))
);

CREATE TABLE ecrs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  number varchar UNIQUE NOT NULL,
  description text NOT NULL,
  status varchar NOT NULL DEFAULT 'open'
    CHECK (status IN ('open','in-review','approved','rejected','done')),
  created_by uuid NOT NULL REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ecos (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  number varchar UNIQUE NOT NULL,
  ecr_id uuid REFERENCES ecrs(id),
  status varchar NOT NULL DEFAULT 'planned'
    CHECK (status IN ('planned','in-work','executed','closed')),
  created_by uuid NOT NULL REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE eco_parts (
  eco_id uuid NOT NULL REFERENCES ecos(id),
  part_revision_id uuid NOT NULL REFERENCES part_revisions(id),
  PRIMARY KEY (eco_id, part_revision_id)
);

CREATE TABLE report_exports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  report_id varchar UNIQUE NOT NULL,
  template varchar NOT NULL,
  content_snapshot jsonb NOT NULL,
  created_by uuid NOT NULL REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now()
);
"""

DOWN = """
DROP TABLE report_exports;
DROP TABLE eco_parts;
DROP TABLE ecos;
DROP TABLE ecrs;
DROP TABLE doc_links;
DROP TABLE doc_files;
DROP TABLE doc_revisions;
DROP TABLE documents;
DROP TABLE audit_log;
DROP TABLE workflow_transitions;
DROP TRIGGER trg_immutable_released ON part_revisions;
DROP FUNCTION prevent_mutation_of_released();
DROP TABLE part_revisions;
DROP TABLE parts;
DROP TABLE number_ranges;
DROP TABLE part_classes;
DROP TABLE users;
"""


def upgrade() -> None:
    op.execute(sa.text(SQL))


def downgrade() -> None:
    op.execute(sa.text(DOWN))
