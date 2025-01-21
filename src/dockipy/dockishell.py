import dockipy.utils as utils
import pathlib, platform, subprocess

def dockishell():
    work_dir, project_root, target_root = utils.find_project_root()

    command, remote, clean = utils.argsparse()

    if clean:
        utils.remove_venv(project_root)

    docki_config = utils.get_docki_config(project_root, remote)

    image, client = utils.build_docker_image(target_root, docki_config, clean)

    try:
        utils.setup_venv(project_root, target_root, client, image, docki_config, clean)
        container = utils.run_container(client, image, command, docki_config, work_dir, project_root, target_root)
        utils.print_logs(container)
    except KeyboardInterrupt:
        print("Shutting down the container")
    except Exception as e:
        print(e)
    finally:
        container.stop()
        container.remove(force=True)