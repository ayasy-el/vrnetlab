# vrnetlab / Juniper cRPD

This is the vrnetlab docker builder for Juniper's cRPD (containerized Routing Protocols Daemon).

> Available with [containerlab](https://containerlab.dev) as native `juniper_crpd` kind.

## Supported Image Formats

This vrnetlab builder accepts:
1. **Community / EVE-NG package (`junipercrpd-*.tgz` or `virtioa.qcow2`)**: Automatically extracts the embedded Docker image from the virtual disk via headless QEMU.
2. **Official Juniper Docker tarball (`crpd-*.tgz`)**: Imports and standardizes official container packages.

## Building the docker image

Download or copy your cRPD archive to this directory:
```bash
cp /path/to/junipercrpd-20.2R1.10.tgz .
```

After typing `make`, a new image will appear in your Docker daemon:
* `vrnetlab/juniper_crpd:<version>`

Run `docker images` to confirm this.

Additionally, a standalone archive `crpd-<version>.docker.tar.gz` will be created in this directory for easy sharing across machines.

## System requirements

* **CPU**: 1 vCPU
* **RAM**: 512MB - 1GB
* **DISK**: ~300MB

## Usage with Containerlab

cRPD runs as a native container node in Containerlab without VM overhead:

```yaml
name: crpd-lab

topology:
  nodes:
    r1:
      kind: juniper_crpd
      image: vrnetlab/juniper_crpd:20.2R1.10
    r2:
      kind: juniper_crpd
      image: vrnetlab/juniper_crpd:20.2R1.10

  links:
    - endpoints: ["r1:eth1", "r2:eth1"]
```

Deploy the lab:
```bash
sudo clab deploy -t topology.yml
```

## Management Access

* **Junos CLI**:
  ```bash
  docker exec -it <container-name> cli
  ```
* **SSH**:
  Default credentials for community images: `root` / `Password1!`
