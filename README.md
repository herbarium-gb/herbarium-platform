# herbarium-platform

Platform for serving herbarium images using a IIIF image server (currently RAIS), fronted by Caddy and viewed with OpenSeadragon.

## Overview

- Serves large JP2 images via a IIIF-compliant image server
- Uses Caddy for routing, clean URLs, and HTTPS
- Uses OpenSeadragon for zoomable image viewing
- Resolves image IDs to file paths with static JSON lookup files ("shards"), not a database
- Hosts a PostgreSQL database used as the publication layer for specimen data (GBIF publishing, see herbarium-data) — the image viewer and Caddy do **not** use it yet
- Supports three contexts:
  - local development
  - server staging
  - server production

## How prod and stage are separated

On the server, prod and stage use the same Caddy container, but they are still separated by hostname-based routing.

Caddy serves different content depending on which host is requested:

- `$HOST_PROD` → production viewer files and production IIIF service
- `$HOST_STAGE` → staging viewer files and staging IIIF service

This means one web container can serve two different environments:

- prod uses `viewer/prod` and `iiif_prod`
- stage uses `viewer/stage` and `iiif_stage`

So there is only one Caddy container, but it routes requests to different HTML roots and different backend services.

## Image lookup (shards)

Images are stored in delivery directories organized by date (e.g. `Delivery/2023/01/23/CP1_.../GB-0500017.jp2`), but URLs contain only the image ID (`/GB-0500017`).

Static JSON shards map IDs to directories without a database or backend.

1. `viewer/scripts/build_shards.py` scans `IMAGE_DATA_PATH` and maps each `.jp2` ID to its directory relative to the delivery root.
2. Entries are grouped by ID prefix into small JSON files:
   - `GB-0500017` → `GB-0500.json`
   - `GB-Folder_0018345` → `GB-Folder_0018.json`
3. Each shard (e.g. `viewer/prod/idx/GB-0500.json`) contains:
   ```json
   { "GB-0500017": "2023/01/23/CP1_20230123_BATCH_0001" }
   ```
4. The viewer derives the shard name from the ID, fetches `/idx/<shard>.json` and constructs the IIIF URL (`/iiif/<rel-path>/<id>.jp2/...`). Missing IDs are shown as "not found".
5. Caddy uses the same shards for short download URLs (`/<id>.jpg`).

**Keep shard-key rules in sync** across:
- `shard_key_for()` in `build_shards.py`
- `shardKeyFor()` in each `viewer/*/index.html`
- `@iiif_short` regexp in `caddy/Caddyfile.server`

### Rebuilding shards

Shard files (`viewer/*/idx/`) are generated and git-ignored. Rebuild after each delivery, either fully or for a specific folder:

```bash
make shards-prod
make shards-prod SUBPATH=2023/09/21/new-batch
```

The server serves `/idx/*` with `Cache-Control: no-cache`, making new images available once the shards are updated.

## Requirements

- Docker + Docker Compose (or Podman equivalents)
- Python 3 (for shard generation)

## Configuration

Copy and edit:

`cp .env.template .env`

## Running locally

`docker compose -f compose.base.yml -f compose.local.yml up -d`
or
`make up-local`

- http://localhost:8080 → prod-like viewer  
- http://localhost:8081 → stage-like viewer  

## Running on server

`docker compose -f compose.base.yml -f compose.server.yml up -d`
or
`make up-server`

- https://$HOST_PROD  
- https://$HOST_STAGE  

## Deploying changes

Files under `viewer/` and `data/` are directory mounts — a `git pull` on the
server takes effect immediately, no container action.

`caddy/Caddyfile.server` is a single-file mount: `git pull` and `caddy reload`
do **not** pick it up. Run `docker compose ... up -d --force-recreate web`.

If the site is down after a server reboot, check in this order:

1. `systemctl is-enabled docker` should print `enabled`.
2. `make ps-server` should show all containers running (otherwise `make up-server`).
3. If the containers run but the site is unreachable from outside,
   try `sudo firewall-cmd --reload` (restores the 80/443 → 8080/8443 forward).

## Makefile

A `Makefile` is included to simplify common tasks such as starting the stack and generating shards.

See the `Makefile` for available commands.

## Tests

`viewer/scripts/test_build_shards.py` checks that `build_shards.py` puts IDs in
the right shard files, and that rebuilding — fully or for a single folder —
adds new images, removes deleted ones and leaves everything else untouched.

Run it in a Python environment where `python-dotenv` is installed:

```
python3 -m venv viewer/.venv
viewer/.venv/bin/pip install -r viewer/scripts/requirements.txt
viewer/.venv/bin/python viewer/scripts/test_build_shards.py -v
```

These are the only automated tests in the repo.

## PostgreSQL and IPT

The PostgreSQL database (schema in `db/init/`) is used for publishing specimen
data to GBIF via IPT. Loading and publishing are handled by
[herbarium-data](https://github.com/herbarium-gb/herbarium-data) — see its README.

Restrict database port access to the IPT server only via the host firewall.

To reach the database from your own machine (psql, a GUI client, loading
scripts), use an SSH tunnel instead of opening the port. Example
`~/.ssh/config` entry (replace the placeholders):

```
Host herbarium-db
  HostName <server-hostname>
  User <your-ssh-user>
  LocalForward 5433 localhost:5432
```

Start the tunnel with `ssh -N herbarium-db` and connect to `localhost:5433`.
The local port is arbitrary; 5433 avoids clashing with a local PostgreSQL.

IPT connects as the read-only `ipt_herbarium` role, which can only read
`public.dwc_occurrence`. It is created from `PG_IPT_PASSWORD` in `.env` when the
database is first initialised. On an existing database, set the variable,
recreate the container and run the script by hand:

```
docker compose -f compose.base.yml -f compose.server.yml up -d --force-recreate db
docker compose -f compose.base.yml -f compose.server.yml exec db bash /docker-entrypoint-initdb.d/002_ipt_role.sh
```

## IIIF access

**Viewer** — `https://<base-url>/<qr-id>`

**Direct download** — `https://<base-url>/<qr-id>.jpg`

**Full IIIF** — `https://<base-url>/iiif/<rel-path>/<qr-id>.jp2/{region}/{size}/{rotation}/{quality}.{format}`

Parameters follow the [IIIF Image API](https://iiif.io/api/image/2.1/):

| Parameter | Example | Notes |
|-----------|---------|-------|
| region | `full` | Full image; or `x,y,w,h` for a crop |
| size | `full` | Full resolution; `1200,` for 1200px wide |
| rotation | `0` | Degrees clockwise |
| quality | `default` | |
| format | `jpg` | `jpg` or `png` |

Note: sizes above 3999px are blocked.

**Image metadata** — `https://<base-url>/iiif/<rel-path>/<qr-id>.jp2/info.json`

## Batch download

Users can download multiple images at once via the instructions page at `/batch-download`.

Scripts in `viewer/scripts/` (`batch_download.R` and `batch_download.py`) accept either a plain list of GB-IDs or a TSV export from FileMaker. Each script downloads images via the short URL format (`/<qr-id>.jpg`) and skips files already present in the output directory.
