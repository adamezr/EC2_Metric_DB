import os
import sys
import csv
import oracledb

# --- Config -----------------------------------------------------------------
WORK_DIR    = "/Users/ebenadam/DB"
WALLET_PATH = "/Users/ebenadam/Wallet_SEIS6302026SPRING"
LIB_DIR     = "/Users/ebenadam/instantclient_23_26"
DSN         = "seis6302026spring_low"
CSV_FILE    = "servers_steampipe.csv"
BATCH_SIZE  = 100

# Table column -> CSV header name. Edit the right-hand side to match the
# headers in your Steampipe export. If a header isn't found, the script
# prints the headers it did find so you can fix this mapping.
COLUMN_MAP = {
    "id":          "id",
    "hostname":    "hostname",
    "ip_address":  "ip_address",
    "os":          "os",
    "environment": "environment",
}

SQL = """
INSERT INTO servers (id, hostname, ip_address, os, environment)
VALUES (:1, :2, :3, :4, :5)
"""


def load_env(path):
    """Load KEY=VALUE pairs into os.environ, skipping blanks and comments."""
    if not os.path.exists(path):
        sys.exit(f"Credentials file not found: {path}")
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ[key.strip()] = val.strip().strip('"\'')


def load_file(conn, cursor, filename, sql, column_map):
    total = 0
    failed = 0

    with open(filename, "r", newline="") as csv_file:
        reader = csv.DictReader(csv_file)

        missing = [h for h in column_map.values() if h not in reader.fieldnames]
        if missing:
            sys.exit(
                f"CSV is missing expected headers: {missing}\n"
                f"Headers found: {reader.fieldnames}\n"
                "Update COLUMN_MAP to match."
            )

        headers = list(column_map.values())

        def flush(batch):
            nonlocal failed
            cursor.executemany(sql, batch, batcherrors=True)
            for err in cursor.getbatcherrors():
                failed += 1
                print(f"  Row {total - len(batch) + err.offset + 1}: {err.message}")

        data = []
        for row in reader:
            data.append([row[h] or None for h in headers])  # '' -> NULL
            total += 1
            if len(data) >= BATCH_SIZE:
                flush(data)
                data = []
        if data:
            flush(data)

    conn.commit()
    return total, failed


def main():
    os.chdir(WORK_DIR)
    load_env(os.path.join(WORK_DIR, "credentials.env"))

    oracledb.init_oracle_client(lib_dir=LIB_DIR, config_dir=WALLET_PATH)

    with oracledb.connect(
        user=os.getenv("user"),
        password=os.getenv("password"),
        dsn=DSN,
    ) as conn:
        with conn.cursor() as cursor:
            total, failed = load_file(conn, cursor, CSV_FILE, SQL, COLUMN_MAP)

    print(f"Servers loaded: {total - failed} of {total} rows"
          + (f" ({failed} failed, see above)" if failed else "."))


if __name__ == "__main__":
    main()
