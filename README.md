# ConfigCove

Simple scripts for configuration management, version tracking, and centralized backups of selected files for homelab.

## Usage

### Step 1

On the *machine to backup*: Create file with tracked files.

`confcove_client.py` can be used to generate this file.

It can be download manually or using `dest=/usr/local/bin/confcove; wget -qO $dest https://l.antn.in/confcove && chmod +x $dest`.

Here it is downloaded as `confcove`. Accepts 1 or more parameters.

- files: `confcove /etc/nginx/nginx.conf`
- directories: `confcove /etc/nginx/` (ending with "/"). All files from this directory will be downloaded.
- wildcards: `confcove /etc/nginx/**/*.conf`. All files existing at the moment of running this command will be added recursively to the tracked list as files.

*Example:*

``` bash
$ cat ~/tracked_files.txt
/opt/Docker_configs/
/opt/c/mktxp/_mktxp.conf
/opt/c/mktxp/mktxp.confr
```

### Step 2

On the *backup server*: Create file `assets.json` with assets to backup. JSON is choosen to avoid extra modules installation (i.e. yaml).

It has 2 sections:

- defaults
- machines

*Example:*

``` json
{
    "defaults": {
        "username":"ubuntu",
        "key_path":"~/.ssh/id_ed25519"
    },
    "machines": [
        {
            "name": "Prometheus",
            "host": "192.168.1.5"
        },
        {
            "name": "Grafana",
            "host": "192.168.1.6",
            "key_path":"~/.ssh/id_rsa"
        },
        {
            "name": "Frigate",
            "host": "192.168.1.7",
            "username": "admin",
            "password": "bad_practice"
        }
    ]
}
```

As JSON is data-only fromat it doesn't support comments. However, I explicitely strip out lines having `//` at the beginning or after a series of spaces. Therefore, you may comment out lines like this:

``` text
        {
            "name": "Frigate",
            "host": "192.168.1.7",
            // "username": "admin",
            "password": "bad_practice"
        },
```

### Step 3

Execute `confcove_server.py` on the *backup server*.

You'd see something like this:

``` text
Backing up: Docker_Portainer (192.168.x.x)
Processing path: /opt/Docker_configs/
Processing path: /opt/c/mktxp/_mktxp.conf
Processing path: /opt/c/mktxp/mktxp.conf

Backing up: Dashy (192.168.x.x)
Processing path: /opt/dashy/user-data/conf.yml
Processing path: /opt/dashy/user-data/pmxD.yml
Processing path: /opt/dashy/user-data/test.yml

Backing up: Prometheus (192.168.x.x)
Processing path: /etc/prometheus/prometheus.yml
```

## confcove_server.py

### Goal and results

Walks through assets (VM, LXC) and downloads all files mentioned in `tracked_file_path` from a "machine to backup" to a local directory.

Resulting directory structure:

``` text
.
├── Dashy
│   └── opt
│       └── dashy
│           └── user-data
│               ├── conf.yml
│               ├── pmxD.yml
│               └── test.yml
├── Docker_Portainer
│   ├── _containers
│   │   ├── mktxp
│   │   │   ├── container_details.json
│   │   │   └── mktxp.sh
│   │   ├── openspeedtest
│   │   │   ├── container_details.json
│   │   │   └── openspeedtest.sh
│   │   └── portainer
│   │       ├── container_details.json
│   │       └── portainer.sh
│   ├── _stacks
│   │   ├── authentik
│   │   │   └── docker-compose.yml
│   │   └── nginx-pm
│   │       └── docker-compose.yml
│   └── opt
│       └── c
│           └── mktxp
│               ├── _mktxp.conf
│               └── mktxp.conf
├── Grafana
│   └── etc
│       └── grafana
│           └── grafana.ini
├── Prometheus
│   └── etc
│       └── prometheus
│           └── prometheus.yml
└── Traefik
    └── etc
        └── traefik
            ├── conf.d
            │   └── config.yaml
            └── traefik.yaml
```

This directory can be initialized as a git repository and used to backup/track changes in configuration files.

## confcove_client.py

Simplifies populating tracked_file specified in the script:

``` bash
TRACKED_FILE = os.path.join(os.path.expanduser("~"), "tracked_files.txt")
```

This file can be modified to point to a different location if required but must be aligned with `assets.json` on the backup server.

Alternatively, this file can be populated manually, without this script.

## export_docker_compose.sh

VMs and LXC contains configuration files on the machine to which we connect with ssh. Docker volumes also can be refered in the tracked_file. Ensure enough permissions for the user used to establish ssh session.

At the same time, if `docker run` and `docker compose` are not exist as files, some additional steps required to backup them. Manually executed docker-compose.yaml files can be backed up by mentioning them in the tracked_file. But  those which were run via Portainer web interface must be retrieved from the Portainer using its API.

`export_docker_compose.sh` script uses `docker inspect` command to retrieve configuration of all running containers except labeled with "com.docker.compose.project", saves JSON and generates a shell script with `docker run` comand. `docker-compose.yaml` files are retrieved from Portainer. These files are saved in a directory named after the app name.

Directory with this exported information should be refered in the tracked_file, for instance:

``` text
/opt/Docker_configs/
```