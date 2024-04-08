import docker
from io import BytesIO
import pathlib
import argparse
import platform


def build_dockerfile(
    base_image: str = "ubuntu:latest",
    system_dep: list = "",
    project_root: str = "/",
):
    return f'''
    FROM {base_image}

    SHELL ["/bin/bash", "-c"]

    ENV LANG=C.UTF-8
    ENV LC_ALL=C.UTF-8
    ENV DEBIAN_FRONTEND=noninteractive

    RUN apt-get update && apt-get install -y {' '.join(system_dep)}

    # Where pytorch will save parameters from pretrained networks
    ENV XDG_CACHE_HOME={project_root}/tmp
    '''

def find_project_root():
    files_to_find = ["setup.py", "requirements.txt", "pyproject.toml", ".git"]
    current_dir = pathlib.Path(".").resolve()
    path = []
    while current_dir != current_dir.parent:
        path.append(current_dir.name)
        for file in files_to_find:
            if (current_dir / file).exists():
                return "/"+"/".join(path), str(current_dir), f"/{current_dir.name}"
        current_dir = current_dir.parent
    return "/"+"/".join(path), str(current_dir), f"/{current_dir.name}"

def main():
    work_dir, project_root, target_root = find_project_root()
    help =  f"""Replace python with dockipy to run your python script in a Docker container.
            Example: dockipy my_script.py, this will run my_script.py in a Docker container.
            requirements.txt in the project root will be installed in the python environment.
            system_deps.txt in the project root will be installed in the container.
            If these files do not exist, they will be created in the project root."""
    argparser = argparse.ArgumentParser(
        prog="dockipy",
        description="Python but in a Docker container", 
        epilog=help,
        )

    argparser.add_argument("command", nargs="+", help="The python script to run in the container")

    args = argparser.parse_args()

    # Create a Docker client
    missing = False
    client = docker.from_env()


    system_deps_file = pathlib.Path(project_root) / "system_deps.txt"
    if not system_deps_file.exists():
        print(f"No system_deps.txt file found in {project_root}")
        system_deps_file.write_text("# base image, e.g nvidia/cuda:11.8.0-devel-ubuntu22.04, ubuntu:latest\nnvidia/cuda:11.8.0-devel-ubuntu22.04\n# dependencies\npython3\npython3-pip\npython3-dev\npython3-venv\n")
        print(f"Created an system_deps.txt file in {project_root}")
        missing = True
    else:
        base_image, *system_dep = list(filter(lambda l: not l.strip().startswith("#"),  system_deps_file.read_text().split("\n")))
        if len(system_dep) == 0:
            print(f"system_deps.txt is empty")

    requirements =  pathlib.Path(project_root) / "requirements.txt"
    if not requirements.exists():
        print(f"No requirements.txt file found in {project_root}")
        requirements.touch()
        print(f"Created an empty requirements.txt file in {project_root}")
        missing = True
    else:
        deps = requirements.read_text().split("\n")
        if len(deps) == 0:
            print(f"requirements.txt is empty")
    
    if missing:
        print("Please fill in the missing files and run the script again.")
        return
    # Define the Dockerfile
    dockerfile = build_dockerfile(
        base_image=base_image,
        system_dep=system_dep,
        project_root=project_root
    )

    # Build the Docker image
    print(f"Building the Docker image based on {base_image}...")
    image, build_log = client.images.build(
        fileobj=BytesIO(dockerfile.encode('utf-8')), 
        tag="party_image", 
        rm=True,
    )

    for key, value in list(build_log)[-1].items():
        print(value, end="")
            
    try:
        # build venv and install requirements
        if platform.system() == "Linux":
            volumes = {project_root: {"bind": target_root, "mode": "rw"}, "mnt": {"bind": "/mnt", "mode": "rw"}}
        else:
            volumes = {project_root: {"bind": target_root, "mode": "rw"}}
        container = client.containers.run(image,
                                            f'bash -c "python3 -m venv {target_root}/venv; {target_root}/venv/bin/pip install -r requirements.txt"',
                                            stdout=True,
                                            stderr=True,
                                            tty = True,
                                            remove=True,
                                            detach = True,
                                            volumes=volumes,
                                            working_dir=target_root
                                            )
        for line in container.logs(stream=True):
            try:
                print(line.decode('utf-8'), end="") 
            except:
                pass
            
        # Run a container from the image
        command = " ".join(args.command)
        print(f"Running the command: {command}, target_root: {target_root}, work_dir: {work_dir}")
        container = client.containers.run(image, 
                                            f'{target_root}/venv/bin/python3 {command}',
                                            stdout=True,
                                            stderr=True,
                                            tty = True,
                                            # remove=True,
                                            detach = True,
                                            volumes={project_root: {"bind": target_root, "mode": "rw"}},
                                            working_dir=work_dir
                                            )

        for line in container.logs(stream=True):
            print(line.decode('utf-8'), end="")
    except Exception as e:
        print(e)
    finally:
        container.stop()
        container.remove(force=True)

if __name__ == "__main__":
    main()