from docker_client import DockerClient

def main():
    """Test DockerClient functionality."""
    try:
        client = DockerClient()
        print("Connected to Docker successfully!")

        # Test containers
        print("\n=== Containers ===")
        containers = client.get_containers(all=True)
        if not containers:
            print("No containers found.")
        for c in containers:
            print(f"Name: {c['name']}, Status: {c['status']}, CPU: {c['cpu']}%, "
                  f"Mem: {c['memory']}MB, Ports: {c['ports']}, Created: {c['created']}")

        # Test logs (if containers exist)
        if containers:
            print(f"\n=== Logs for {containers[0]['name']} ===")
            print(client.get_container_logs(containers[0]['id'], tail=5))

        # Test images
        print("\n=== Images ===")
        images = client.get_images()
        if not images:
            print("No images found.")
        for img in images:
            print(f"ID: {img['id']}, Tags: {img['tags']}, Size: {img['size']}MB, Created: {img['created']}")

        # Test volumes
        print("\n=== Volumes ===")
        volumes = client.get_volumes()
        if not volumes:
            print("No volumes found.")
        for vol in volumes:
            print(f"Name: {vol['name']}, Driver: {vol['driver']}, Created: {vol['created']}")

        # Test networks
        print("\n=== Networks ===")
        networks = client.get_networks()
        if not networks:
            print("No networks found.")
        for net in networks:
            print(f"Name: {net['name']}, Driver: {net['driver']}, Created: {net['created']}")

        # Test container actions (if containers exist)
        if containers:
            container_id = containers[0]['id']
            print(f"\n=== Testing actions on container {container_id} ===")
            try:
                print("Stopping container...")
                client.stop_container(container_id)
                print("Container stopped.")
                print("Starting container...")
                client.start_container(container_id)
                print("Container started.")
            except Exception as e:
                print(f"Action failed: {e}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()