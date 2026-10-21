"""Authenticated metadata-only dedicated conversion-registry inventory."""
from __future__ import annotations
import argparse
import json
import os

from empire_os.predictive_original_conversion_catalogue import (
    SCHEMA, ConversionCatalogueHold, review_original_conversion_catalogue,
)

ENV="EMPIREDB_TENANT_OUTCOME_READER_DSN"


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only",action="store_true",required=True)
    parser.parse_args(argv)
    try:
        result=review_original_conversion_catalogue(dsn=os.environ.get(ENV,""))
    except (ConversionCatalogueHold,TypeError,ValueError,OSError):
        result={
            "schema_version":SCHEMA,
            "mode":"OBSERVE",
            "status":"DEDICATED_CONVERSION_CATALOGUE_AUTHENTICATION_HELD",
            "catalogue_metadata_completeness_verified":False,
            "original_conversion_rows_queried":False,
            "forecast_immutable_registration_proven":False,
            "scientific_training_or_customer_forecast_authorized":False,
            "new_roles_grants_ddl_migrations_or_credentials":False,
            "database_writes":False,
            "execution_authority":"none",
        }
    print(json.dumps(result,sort_keys=True,allow_nan=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
