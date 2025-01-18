#!/bin/bash

# jq is required
# Configuration: Change these variables to match your environment
PORTAINER_URL="https://d.pmx.antn.in:9443"  # add -k in 3 curl to ignore ceritifactes if needed
PORTAINER_API="/api"
DOCKER_MACHINE_NAME="Docker_Portainer"  # Only required if you're using Docker Machine.
# Uncomment to override env variables:
# PORTAINER_USERNAME="<your-username>"
# PORTAINER_PASSWORD="<your-password>"

# Directory to store exported configurations
EXPORT_DIR="/opt/Docker_configs"
# Directory where container details are stored
CONTAINER_DIR="/opt/Docker_configs/containers"


# Create a directory for storing all configurations if it doesn't exist
mkdir -p "$EXPORT_DIR"

# Authenticate with Portainer API and get JWT token
# printf to overcome issues with special characters like hash mark in the password
AUTH_TOKEN=$(curl -s -X POST "$PORTAINER_URL$PORTAINER_API/auth" \
  -H "Content-Type: application/json" \
  --data-raw "$(printf '{"Username": "%s", "Password": "%s"}' "$PORTAINER_USERNAME" "$PORTAINER_PASSWORD")" | jq -r '.jwt')

if [ "$AUTH_TOKEN" == "null" ] || [ -z "$AUTH_TOKEN" ]; then
  echo "Failed to authenticate with Portainer. Check your credentials."
  exit 1
fi

echo "Authenticated with Portainer API."

# 1. Export Container Configuration
echo "Exporting container configurations..."

# Get all container IDs and loop through them
docker ps -q | while read container_id; do
  # Check if the container has a Docker Compose label
  is_compose=$(docker inspect --format '{{ index .Config.Labels "com.docker.compose.project" }}' "$container_id")

  if [ -z "$is_compose" ]; then
    container_name=$(docker inspect --format '{{.Name}}' "$container_id" | sed 's/^\///')
    container_dir="$EXPORT_DIR/containers/$container_name"

    mkdir -p "$container_dir"

    # Export container details
    docker inspect "$container_id" > "$container_dir/container_details.json"
    echo "Exported configuration for container: $container_name"
  else
    echo "Skipping Docker Compose container: $(docker inspect --format '{{.Name}}' "$container_id" | sed 's/^\///')"
  fi
done

# 2. Export Docker Compose Files from Portainer Stacks
echo "Exporting Docker Compose files from Portainer..."

# Get a list of all stacks from Portainer
stacks=$(curl -s -X GET "$PORTAINER_URL$PORTAINER_API/stacks" \
  -H "Authorization: Bearer $AUTH_TOKEN")

# Loop through all stacks to fetch their Compose files
echo "$stacks" | jq -r '.[].Id' | while read stack_id; do
  stack_name=$(echo "$stacks" | jq -r ".[] | select(.Id == $stack_id) | .Name")
  stack_dir="$EXPORT_DIR/stacks/$stack_name"

  mkdir -p "$stack_dir"

  # Get the Compose file for the stack
  compose_file=$(curl -s -X GET "$PORTAINER_URL$PORTAINER_API/stacks/$stack_id/file" \
    -H "Authorization: Bearer $AUTH_TOKEN")

  # Save the Compose file
  printf "$compose_file" > "$stack_dir/docker-compose.yml"
  echo "Exported Docker Compose for stack: $stack_name"
done


# Convert `docker inspect` (json) to `docker run`

# Loop over all container directories
for container_dir in "$CONTAINER_DIR"/*; do
  if [ -d "$container_dir" ]; then
    container_name=$(basename "$container_dir")
    container_json="$container_dir/container_details.json"

    # Check if the JSON file exists
    if [ ! -f "$container_json" ]; then
      echo "No container details found for $container_name"
      continue
    fi

    echo "Generating docker run command for container: $container_name"

    # Extract necessary information from the container's JSON details
    image=$(jq -r '.[0].Config.Image' "$container_json")
    # cmd=$(jq -r '.[0].Config.Cmd | join(" ")' "$container_json")
    # env_vars=$(jq -r '.[0].Config.Env[]' "$container_json" | sed 's/^/ -e /')
    env_vars=$(jq -r '.[0].Config.Env[]' "$container_json" | sed 's/^/  -e /' | sed '$!s/$/ \\/')
    ports=$(jq -r '.[0].NetworkSettings.Ports | to_entries[] | "  -p \(.key):\(.value[0].HostPort)"' "$container_json" | sed '$!s/$/ \\/')
    volumes=$(jq -r '.[0].Mounts[] | "  -v \(.Source):\(.Destination)"' "$container_json" | sed '$!s/$/ \\/')
    network_mode=$(jq -r '.[0].HostConfig.NetworkMode' "$container_json")
    restart_policy=$(jq -r '.[0].HostConfig.RestartPolicy.Name' "$container_json")

    # Build the docker run command
    run_cmd="docker run --name $container_name \\ \n"

    # Add environment variables
    if [ ! -z "$env_vars" ]; then
      run_cmd="$run_cmd$env_vars \\ \n"
    fi

    # Add ports
    if [ ! -z "$ports" ]; then
      run_cmd="$run_cmd$ports \\ \n"
    fi

    # Add volumes
    if [ ! -z "$volumes" ]; then
      run_cmd="$run_cmd$volumes \\ \n"
    fi

    # Add network mode
    if [ "$network_mode" != "default" ]; then
      run_cmd="$run_cmd  --network $network_mode \\ \n"
    fi

    # Add restart policy
    if [ "$restart_policy" != "no" ]; then
      run_cmd="$run_cmd  --restart $restart_policy \\ \n"
    fi

    # # Add the command to run (if applicable)
    # if [ ! -z "$cmd" ]; then
    #   run_cmd="$run_cmd  $cmd"
    # fi

    # Add image
    run_cmd="$run_cmd  $image"

    # Output the docker run command
    printf "$run_cmd" > ${container_dir}/${container_name}.sh
  fi
done

echo "Export complete."
