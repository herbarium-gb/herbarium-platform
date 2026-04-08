# herbarium-platform

Minimal platform for serving herbarium images using a IIIF image server (currently RAIS), fronted by Caddy and viewed with OpenSeadragon.

## Overview

- Serves large JP2 images via a IIIF-compliant image server
- Uses Caddy for routing, clean URLs, and HTTPS
- Uses OpenSeadragon for zoomable image viewing
- Includes a PostgreSQL database that can be used as a publication layer for specimen data (e.g. via IPT)
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

## Requirements

- Docker + Docker Compose (or Podman equivalents)
- Python 3 (for shard generation)

## Configuration

Copy and edit:

`cp .env.example .env`

## Running locally

`docker compose -f docker-compose.yml -f docker-compose.local.yml up -d`
or
`make up-local`

- http://localhost:8080 → prod-like viewer  
- http://localhost:8081 → stage-like viewer  

## Running on server

`docker compose -f docker-compose.yml -f docker-compose.server.yml up -d`
or
`make up-server`

- https://$HOST_PROD  
- https://$HOST_STAGE  

## Makefile

A `Makefile` is included to simplify common tasks such as starting the stack and generating shards.

See the `Makefile` for available commands.

## PostgreSQL and IPT

The included PostgreSQL database is intended as a publication layer for specimen data.

Typical use:

- data is prepared externally (e.g. via `hbdb-to-dwc`)
- data is loaded into PostgreSQL
- IPT connects directly to the database and publishes datasets

Access should be restricted to trusted clients (e.g. a specific IPT IP).

## IIIF access

Example:

`/iiif/2023/01/23/CP1_20230123_BATCH_0001/GB-0500017.jp2/info.json`

## Notes

- Real image data is not stored in the repo (mounted in production)
- Viewer shards are generated files and ignored by Git
- Certificates and runtime data are not tracked
