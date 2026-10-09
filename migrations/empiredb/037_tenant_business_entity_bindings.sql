-- EmpireOS canonical tenant -> business entity binding foundation.
--
-- IMPORTANT:
--   PREPARED ONLY. Do not apply without explicit founder approval.
--
-- Purpose:
--   Establish durable evidence that a canonical business entity is within a
--   tenant's authorised intelligence scope.
--
-- Security:
--   Tenant identity comes from the trusted DB/session tenant foundation.
--   Caller payloads cannot manufacture this relationship.
--
-- Semantics:
--   This table is many-to-many intentionally. business_entities remains a
--   global canonical identity layer.

CREATE TABLE public.tenant_business_entity_bindings (
    tenant_id uuid NOT NULL,
    entity_id uuid NOT NULL
        REFERENCES public.business_entities(id)
        ON DELETE RESTRICT,

    binding_kind text NOT NULL,
    evidence_ref text NOT NULL,

    active boolean NOT NULL DEFAULT true,

    valid_from timestamptz NOT NULL DEFAULT now(),
    valid_until timestamptz NULL,

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT tenant_business_entity_bindings_pk
        PRIMARY KEY (tenant_id, entity_id, binding_kind),

    CONSTRAINT tenant_business_entity_bindings_kind_check
        CHECK (
            binding_kind IN (
                'owned',
                'managed',
                'customer',
                'prospect',
                'observed'
            )
        ),

    CONSTRAINT tenant_business_entity_bindings_evidence_check
        CHECK (length(btrim(evidence_ref)) > 0),

    CONSTRAINT tenant_business_entity_bindings_validity_check
        CHECK (
            valid_until IS NULL
            OR valid_until > valid_from
        )
);

CREATE INDEX tenant_business_entity_bindings_entity_idx
    ON public.tenant_business_entity_bindings(entity_id)
    WHERE active = true;

CREATE INDEX tenant_business_entity_bindings_tenant_idx
    ON public.tenant_business_entity_bindings(tenant_id)
    WHERE active = true;

COMMENT ON TABLE public.tenant_business_entity_bindings IS
'Canonical evidence-backed tenant scope binding for business_entities. '
'Presence establishes scoped relationship only; it grants no outbound, '
'commercial, payment, traffic or execution authority.';

COMMENT ON COLUMN
public.tenant_business_entity_bindings.evidence_ref IS
'Immutable or durable provenance reference establishing why this tenant/entity binding exists.';
