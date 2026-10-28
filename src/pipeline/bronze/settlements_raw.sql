-- Settlement status and fails per cash execution: one Parquet file per settlement due date.
USE SCHEMA bronze;

CREATE OR REFRESH STREAMING TABLE settlements_raw
COMMENT 'Bronze: settlement and fail records from the settlements system (Parquet).'
AS SELECT
  *,
  _metadata.file_path AS source_file,
  current_timestamp() AS ingested_at
FROM STREAM read_files('${landing_root}/settlements/', format => 'parquet');
