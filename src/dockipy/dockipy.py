import dockipy.utils as utils

def dockipy():
    work_dir, project_root, target_root = utils.find_project_root()

    command, remote, clean, output = utils.argsparse()

    docki_config = utils.get_docki_config(project_root, remote)

    image, client = utils.build_docker_image(target_root, docki_config, clean, output)
    
    command = [f"{target_root}/venv/bin/python3"] + command
    try:
        utils.setup_venv(project_root, target_root, client, image, docki_config, clean, output)
        # Run a container from the image
        container = utils.run_container(client, image, command, docki_config, work_dir, project_root, target_root, output)
        if output:
            exit(0)
        utils.print_logs(container)
    except KeyboardInterrupt:
        print("Shutting down the container")
    except Exception as e:
        print(e)
    finally:
        container.stop()
        container.remove(force=True)