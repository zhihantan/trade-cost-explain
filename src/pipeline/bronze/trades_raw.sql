-- OMS/EMS executions as landed: one Parquet file per trade date (Auto Loader, exactly-once).
USE SCHEMA bronze;

CREATE OR REFRESH STREAMING TABLE trades_raw
COMMENT 'Bronze: OMS/EMS executions as landed (Parquet, one file per trade date). Synthetic — Meridian Group.'
CLUSTER BY (trade_date)
AS SELECT
  *,
  _metadata.file_path              AS source_file,
  _metadata.file_modification_time AS source_file_ts,
  current_timestamp()              AS ingested_at
FROM STREAM read_files('${landing_root}/trades/', format => 'parquet');
