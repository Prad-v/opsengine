## Local Compose (this repo)

`make start` runs NetBox at [http://localhost:8000](http://localhost:8000) (`admin` / `admin`) beside the provider mock. After NetBox is up, open http://localhost:8099 → **Service Topology** → **Configure Keep with NetBox**. That seeds the NVIDIA GPU inventory and installs this provider (`netbox_url=http://localhost:8000`).

## Setting up the NetBox Community instance using Docker

This guide will help you set up a NetBox Community instance using Docker. The guide assumes you have Docker installed on your system.

1. Clone the NetBox community docker repository

```bash
git clone -b release https://github.com/netbox-community/netbox-docker.git
```

2. Change directory to the cloned repository

```bash
cd netbox-docker
```

3. Create `docker-compose.override.yml` file with the following content

```yaml
version: '3.4'
services:
  netbox:
    ports:
    - 8000:8080
```

4. Start the NetBox Community instance

```bash
docker compose up
```

5. To create first admin user account run the following command and follow the prompts

```bash
docker compose exec netbox /opt/netbox/netbox/manage.py createsuperuser
```

6. You can now access the NetBox Community instance by visiting [http://localhost:8000](http://localhost:8000) in your browser.

## Topology sync

Install the NetBox provider in Keep with `netbox_url` (for example `http://localhost:8000`) and an API token. Keep pulls regions, sites, locations (rows), racks, devices, GPU inventory items/modules, prefixes, and VLANs into Service Topology.

Create the token in NetBox under **Admin → API Tokens** with DCIM and IPAM read permissions. Then use **Service Topology → Pull**. Each pull replaces nodes owned by that provider.

Name slugs so they match alert labels (`host`, `rack`, `row`, `datacenter`, `region`, `gpu_id`). GPU nodes are `{hostname}-gpu{index}`.