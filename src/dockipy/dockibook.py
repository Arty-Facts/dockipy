
import dockipy.utils as utils
import sys

def dockibook():
    work_dir, project_root, target_root = utils.find_project_root()
    
    command, _remote, clean = utils.argsparse()

    docki_config = utils.get_docki_config(project_root)
    
    token = docki_config.get("notebook_token", "docki")
    password = docki_config.get("notebook_password", "docki")
    notebook_args = docki_config.get("notebook_args", "")
    
    image, client = utils.build_docker_image(target_root, docki_config, clean)

    command = [f"{target_root}/venv/bin/jupyter notebook --no-browser {notebook_args} --ServerApp.allow_origin='*' "+\
    f" --ServerApp.token='{token}'"+\
    f" --ServerApp.password='{password}'"+\
    f" --ServerApp.root_dir='{work_dir}/'"] + command

    try:
        utils.setup_venv(project_root, target_root, client, image, docki_config, clean)
        # Run a container from the image
        container = utils.run_container(client, image, command, docki_config, work_dir, project_root, target_root)

        utils.print_logs(container)
    except KeyboardInterrupt:
        print("Shutting down the container")
    except Exception as e:
        print(e)
    finally:
        container.stop()
        container.remove(force=True)