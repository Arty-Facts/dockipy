import dockipy.utils as utils

def dockishell():
    work_dir, project_root, target_root = utils.find_project_root()

    command = utils.argsparse()

    docki_config = utils.get_docki_config(project_root)

    image, client = utils.build_docker_image(target_root, docki_config)

    try:
        utils.setup_venv(project_root, target_root, client, image, docki_config)
        container = utils.run_container(client, image, command, docki_config, work_dir, project_root, target_root)
        utils.print_logs(container)
    except KeyboardInterrupt:
        print("Shutting down the container")
    except Exception as e:
        print(e)
    finally:
        container.stop()
        container.remove(force=True)