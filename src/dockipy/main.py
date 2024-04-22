from io import BytesIO
import docker
import pathlib
import argparse
import platform
import yaml
import sys
import os
import time
import subprocess

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
    RUN mkdir -p /.local; chmod -R 777 /.local

    # Where pytorch will save parameters from pretrained networks
    ENV XDG_CACHE_HOME={project_root}/tmp
    '''

def docki_examples1():
    return f'''
base_image: nvidia/cuda:11.8.0-devel-ubuntu22.04
shm_size: 16G # shared memory size
tag: docki_image
system_dep:
    - python3
    - python3-pip
    - python3-dev
    - python3-venv
python_dep:
    - jupyter
notebook_token: docki
notebook_password: docki
    '''
def docki_examples2():
    return f'''
base_image: ubuntu:latest
shm_size: 16G # shared memory size
tag: docki_image
system_dep:
    - python3
    - python3-pip
    - python3-dev
    - python3-venv
python_dep:
    file: ./requirements.txt
notebook_token: docki
notebook_password: docki
    '''
def docki_file_yaml(requirements_exists=False):
    examples1 = docki_examples1()
    examples2 = docki_examples2()
    commented_example1 = "\n".join([f"# {line}" for line in examples1.split("\n")])
    commented_example2 = "\n".join([f"# {line}" for line in examples2.split("\n")])
    return f'''# docki.yaml
# This file is used to specify the base image, system dependencies and python dependencies for the Docker container.
# If the file does not exist, a template will be created in the project root using docki init.

# base_image: The base image for the Docker container, you dan find images on Docker Hub.
# system_dep: A list of system dependencies to install in the Docker container. install with apt-get.
# python_dep: A list of python dependencies to install in the Docker container or a path to a requirements.txt file.

# example 1:
{commented_example1}

# example 2:
{commented_example2}
{examples2 if requirements_exists else examples1}
'''

def docki_init(project_root, override=False):
    docki_file = project_root / "docki.yaml"
    requirements = project_root / "requirements.txt"
    if not docki_file.exists():
        docki_file.write_text(docki_file_yaml(requirements.exists()))
        print(f"Created docki.yaml in {project_root}")
    else:
        if override:
            docki_file.write_text(docki_file_yaml(requirements.exists()))
            print(f"Overrided docki.yaml in {project_root}")
        else:
            print(f"docki.yaml already exists in {project_root}")

def docki():
    argparser = argparse.ArgumentParser(
        prog="docki",
        description="Create a docki.yaml file in the project root", 
        epilog="This file is used to specify the base image, system dependencies and python dependencies for the Docker container.",
        )
    argparser.add_argument("--init", action="store_true", help="Create a docki.yaml file in the project root")
    argparser.add_argument("-f", action="store_true", help="Override the docki.yaml file in the project root")
    args = argparser.parse_args()
    project_root = pathlib.Path(".").resolve()
    if args.init:
        docki_init(project_root, args.f)

def find_project_root():
    files_to_find = ["docki.yaml", "requirements.txt", "pyproject.toml", ".git"]
    current_dir = pathlib.Path(".").resolve()
    path = []
    while current_dir != current_dir.parent:
        path.append(current_dir.name)
        for file in files_to_find:
            if (current_dir / file).exists():
                return "/"+"/".join(path), str(current_dir), f"/{current_dir.name}"
        current_dir = current_dir.parent
    return None, None, None

def get_runtime(base_image):
    if "cuda" in base_image:
        return "nvidia"
    if "nvidia" in base_image:
        return "nvidia"
    return None
help =  f"""Replace python with dockipy to run your python script in a Docker container.
Example: dockipy my_script.py, this will run my_script.py in a Docker container.

A docki.yaml file is required in the project root to specify the base image, system dependencies and python dependencies.
If these files do not exist, they will be created in the project root if possible. otherwise, run 'docki --init' to create the docki.yaml file at the project root.
usage: 
    dockipy [OPTIONS] COMMAND

    options:
        -h, --help  Show this message and exit.
        --init      Create a docki.yaml file in the project root.

    commands:
        COMMAND     The command to run in the Docker container.
"""

def argsparse():
    args = sys.argv
    if len(args) == 1:
        print(help)
        exit(1)
    if args[1] == "-h" or args[1] == "--help":
        print(help)
        exit(0)
    if args[1] == "--init":
        docki()
        exit(0)
    command = args[1:]
    return command

def get_docki_config(project_root):
    if project_root is None:
        print("No project root found")
        print("Please run 'docki --init' in your project root to create a docki.yaml file")
        exit(1)
    docki_file = pathlib.Path(project_root) / "docki.yaml"
    if not docki_file.exists() and project_root is not None:
        print(f"No docki.yaml file found in {project_root}")
        docki_init(project_root)
        print("Please verify the docki.yaml file and run the script again.")
        exit(1)
    docki_content = docki_file.read_text()
    docki_config = yaml.safe_load(docki_content)
    missing_values = []
    if "base_image" not in docki_config:
        missing_values.append("base_image")
    if "system_dep" not in docki_config:
        missing_values.append("system_dep")
    if "python_dep" not in docki_config:
        missing_values.append("python_dep")
    if len(missing_values) > 0:
        print(f"Missing values in docki.yaml: {', '.join(missing_values)}")
        print("Please fill in the missing values and run the script again.")
        exit(1)
    return docki_config, docki_content

def build_docker_image(base_image, system_dep, project_root, tag):
    dockerfile = build_dockerfile(base_image, system_dep, project_root)
    client = docker.from_env()
    image, build_log = client.images.build(
        fileobj=BytesIO(dockerfile.encode('utf-8')), 
        tag=tag, 
        rm=True,
    )
    for key, value in list(build_log)[-1].items():
        print(value, end="")
    return image, client

def setup_venv(project_root, target_root, client, image, python_dep, docki_content, runtime, user, volumes):
    if "file" in python_dep:
        requirements = pathlib.Path(project_root) / python_dep.get("file")
        if not requirements.exists():
            print(f"Requirements file {requirements} not found")
            return
        else:
            requirements_cmd = f"-r {requirements}"
    else:
        requirements_cmd = " ".join(python_dep)
    lock_content = ""
    docki_lock_file = pathlib.Path(f"{project_root}/venv/docki.lock")

    if docki_lock_file.exists():
        lock_content = docki_lock_file.read_text()
    if lock_content != docki_content:
        print("Building the virtual environment and installing the requirements...")
        container = client.containers.run(image,
                                            f'bash -c "python3 -m venv {target_root}/venv; {target_root}/venv/bin/pip install {requirements_cmd}"',
                                            stdout=True,
                                            stderr=True,
                                            tty = True,
                                            remove=True,
                                            detach = True,
                                            user=user,
                                            volumes=volumes,
                                            working_dir=target_root,
                                            runtime=runtime,
                                            )
        for line in container.logs(stream=True):
            try:
                print(line.decode('utf-8'), end="") 
            except:
                pass
        docki_lock_file.write_text(docki_content)
    else:
        print("Requirements already installed.")

def dockipy():
    work_dir, project_root, target_root = find_project_root()

    command = argsparse()
    docki_config, docki_content = get_docki_config(project_root)
    
    base_image = docki_config.get("base_image")
    system_dep = docki_config.get("system_dep")
    python_dep = docki_config.get("python_dep")
    shm_size = docki_config.get("shm_size", "16G")
    tag = docki_config.get("tag", "docki_image")
    

    print(f"Building the Docker image based on {base_image}...")
    image, client = build_docker_image(base_image, system_dep, project_root, tag)
            
    try:
        # build venv and install requirements
        if platform.system() == "Linux":
            volumes = {project_root: {"bind": target_root, "mode": "rw"}, "mnt": {"bind": "/mnt", "mode": "rw"}}
            user = f"{os.getuid()}:{os.getgid()}"
        else:
            volumes = {project_root: {"bind": target_root, "mode": "rw"}}
            user = "1000:1000" 


        runtime = get_runtime()
        setup_venv(project_root, target_root, client, image, python_dep, docki_content, runtime, user, volumes)
       
        # Run a container from the image
        command = " ".join(command)
        print(f"Running the command: {command}")
        container = client.containers.run(image, 
                                            f'{target_root}/venv/bin/python3 {command}',
                                            stdout=True,
                                            stderr=True,
                                            tty = True,
                                            # remove=True,
                                            shm_size=shm_size,
                                            network_mode="host",
                                            detach = True,
                                            user=user,
                                            volumes=volumes,
                                            working_dir=work_dir,
                                            runtime=runtime,
                                            )
        container.reload()
        while container.status == "running":
            for line in container.logs(stream=True):
                print(line.decode('utf-8'), end="")
            time.sleep(0.1)
            container.reload()
    except KeyboardInterrupt:
        print("Shutting down the container")
        container.stop()
    except Exception as e:
        print(e)
    finally:
        container.stop()
        container.remove(force=True)

def dockishell():
    work_dir, project_root, target_root = find_project_root()

    command = argsparse()

    docki_config, docki_content = get_docki_config(project_root)
    
    base_image = docki_config.get("base_image")
    system_dep = docki_config.get("system_dep")
    shm_size = docki_config.get("shm_size", "16G")
    tag = docki_config.get("tag", "docki_image")
    
    print(f"Building the Docker image based on {base_image}...")
    image, client = build_docker_image(base_image, system_dep, project_root, tag)

    try:
        if platform.system() == "Linux":
            volumes = {project_root: {"bind": target_root, "mode": "rw"}, "mnt": {"bind": "/mnt", "mode": "rw"}}
            user = f"{os.getuid()}:{os.getgid()}"
        else:
            volumes = {project_root: {"bind": target_root, "mode": "rw"}}
            user = "1000:1000" 

        runtime = get_runtime(base_image)

        # Run a container from the image
        command = " ".join(command)
        container = client.containers.run(image, 
                                            command,
                                            stdout=True,
                                            stderr=True,
                                            tty=True,
                                            remove=True,
                                            shm_size=shm_size,
                                            network_mode="host",
                                            detach = True,
                                            user=user,
                                            volumes=volumes,
                                            working_dir=work_dir,
                                            runtime=runtime,
                                            )
        container.reload()
        while container.status == "running":
            for line in container.logs(stream=True):
                print(line.decode('utf-8'), end="")
            time.sleep(0.1)
            container.reload()
    except KeyboardInterrupt:
        print("Shutting down the container")
        container.stop()
    except Exception as e:
        print(e)

def dockinotebook():
    work_dir, project_root, target_root = find_project_root()

    docki_config, docki_content = get_docki_config(project_root)
    
    base_image = docki_config.get("base_image")
    system_dep = docki_config.get("system_dep")
    python_dep = docki_config.get("python_dep")
    shm_size = docki_config.get("shm_size", "16G")
    tag = docki_config.get("tag", "docki")
    token = docki_config.get("notebook_token", "docki")
    password = docki_config.get("notebook_password", "docki")
    
    print(f"Building the Docker image based on {base_image}...")
    image, client = build_docker_image(base_image, system_dep, project_root, tag)
    command = f"{target_root}/venv/bin/jupyter notebook --no-browser --ServerApp.allow_origin='*' "+\
    f" --ServerApp.token='{token}'"+\
    f" --ServerApp.password='{password}'"+\
    f" --ServerApp.root_dir='{work_dir}/'"+\
    f" --ServerApp.runtime_dir ='{work_dir}/'"

    try:
        if platform.system() == "Linux":
            volumes = {project_root: {"bind": target_root, "mode": "rw"}, "mnt": {"bind": "/mnt", "mode": "rw"}}
            user = f"{os.getuid()}:{os.getgid()}"
        else:
            volumes = {project_root: {"bind": target_root, "mode": "rw"}}
            user = "1000:1000" 

        runtime = get_runtime()
        setup_venv(project_root, target_root, client, image, python_dep, docki_content, runtime, user, volumes)

        # Run a container from the image
        container = client.containers.run(image, 
                                            command,
                                            stdout=True,
                                            stderr=True,
                                            tty=True,
                                            remove=True,
                                            shm_size=shm_size,
                                            network_mode="host",
                                            detach = True,
                                            user=user,
                                            volumes=volumes,
                                            working_dir=work_dir,
                                            runtime=runtime,
                                            )
        container.reload()
        while container.status == "running":
            for line in container.logs(stream=True):
                print(line.decode('utf-8'), end="")
            time.sleep(0.1)
            container.reload()
    except KeyboardInterrupt:
        print("Shutting down the container")
        container.stop()
    except Exception as e:
        print(e)


if __name__ == "__main__":
    dockipy()