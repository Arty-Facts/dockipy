import sys, pathlib, argparse, time, docker, yaml, platform, os, copy, subprocess, atexit, readline
from io import BytesIO
from dockipy.__about__ import __version__ as dockipy_version
import libtmux

class HostManager:
    def __init__(self, tmux_session, host, id):
        """
        Initialize a HostManager for a specific host.

        Args:
            server (libtmux.Server): The tmux server instance.
            tmux_session (str): The tmux session name.
            host (str): The hostname or IP of the target machine.
        """
        self.host = host
        self.id = id
        self.session = tmux_session
        self.pane = self._get_or_create_pane()

    def _get_or_create_pane(self):

        # Create a new pane for the host
        if len(self.session.windows) == 0:
            window = self.session.new_window(attach=False)
        else:
            window = self.session.active_window
        
        if self.id == 0:
            pane = window.panes[self.id]
        else:
            pane = window.split()

        window.select_layout("tiled")
        pane.send_keys(f"ssh {self.host}")
        return pane

    def send_command(self, command):
        self.pane.send_keys(command)

    def close(self):
        self.pane.kill()



def build_dockerfile(
    base_image: str = "ubuntu:latest",
    system_dep: list = [],
    project_root: str = "/",
    user_id: int = 1000,
    group_id: int = 1000,
):
    return f'''FROM {base_image}

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8 LC_ALL=C.UTF-8

RUN apt-get update && \
    apt-get install -y --no-install-recommends software-properties-common && \
    add-apt-repository -y universe && \
    add-apt-repository -y ppa:deadsnakes/ppa 

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    sudo {' '.join(system_dep)} && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
# if needed to add user and group
# RUN sed -i 's/^\(passwd:\).*/\1 files/' /etc/nsswitch.conf && \
#     sed -i 's/^\(group:\).*/\1 files/' /etc/nsswitch.conf && \
#     sed -i 's/^\(shadow:\).*/\1 files/' /etc/nsswitch.conf

# # lets make sure the user id and group id can be set to a high value
# RUN sed -i 's/^UID_MAX.*/UID_MAX 4294967295/' /etc/login.defs && \
#     sed -i 's/^GID_MAX.*/GID_MAX 4294967295/' /etc/login.defs


# # Create group and user non-interactively
# RUN groupadd --gid {group_id} --force docki
# RUN adduser --uid {user_id} --gid {group_id} --no-create-home --shell /bin/bash --disabled-password --gecos "" docki 
# RUN usermod -aG sudo docki 
# RUN echo "docki ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers


RUN mkdir -p /.local; chmod -R 777 /.local
ENV HOME={project_root}/tmp
# Where pytorch will save parameters from pretrained networks
ENV XDG_CACHE_HOME={project_root}/tmp

CMD ["/bin/bash"]
'''


def docki_examples1():
    return f'''
base_image: nvidia/cuda:11.8.0-devel-ubuntu22.04
shm_size: 16G # shared memory size
tag: docki
system_dep:
  - python3
  - python3-pip
  - python3-dev
  - python3-venv
python_dep:
  file: ./requirements.txt
init_commands:
    - export ENV_VAR=VALUE
notebook_token: docki
notebook_password: docki
remote:
  hosts:
    - name: username@host1
    - name: username@host2
      workspace: /path/to/workspace
'''
def docki_file_yaml(requirements_exists=False):
    examples1 = docki_examples1()
    commented_example1 = "\n".join([f"# {line}" for line in examples1.split("\n")])
    return f'''# docki.yaml
# This file is used to specify the base image, system dependencies and python dependencies for the Docker container.
# If the file does not exist, a template will be created in the project root using docki init.

# base_image: The base image for the Docker container, you dan find images on Docker Hub.
# system_dep: A list of system dependencies to install in the Docker container. install with apt-get.
# python_dep: A list of python dependencies to install in the Docker container or a path to a requirements.txt file.

# example:
{commented_example1}

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
    argparser.add_argument("--remote", action="store_true", help="Opens a one to many remote connection on hosts specified in the docki.yaml file")
    args = argparser.parse_args()
    project_root = pathlib.Path(".").resolve()
    if args.init:
        docki_init(project_root)
    if args.remote:
        work_dir, project_root, target_root = find_project_root()
        docki_config = get_docki_config(project_root, remote=True)
        docki_remote(docki_config)

def launch_terminal_with_tmux(session_name):
    """
    Launch a new terminal window and attach to a tmux session.

    Args:
        session_name (str): The name of the tmux session to attach to.
    """

    # Determine the terminal command based on the OS
    if platform.system() == "Linux":
        # Enable mouse support in the tmux session
        subprocess.run(["tmux", "set-option", "-t", session_name, "-g", "mouse", "on"], check=True)
        # For Linux (adjust for your terminal emulator)
        subprocess.Popen(["gnome-terminal", "--", "tmux", "attach-session", "-t", session_name])
    elif platform.system() == "Darwin":  # macOS
        subprocess.Popen(["open", "-a", "Terminal.app", f"tmux attach-session -t {session_name}"])
    elif platform.system() == "Windows":
        print("Tmux is not natively supported on Windows. Use WSL or an alternative setup.")
    else:
        raise ValueError("Unsupported platform.")

HISTORY_FILE = os.path.expanduser("~/.docki_remote_history")

def setup_readline():
    """
    Set up readline for command history and advanced input support.
    """
    # Load command history if available
    if os.path.exists(HISTORY_FILE):
        readline.read_history_file(HISTORY_FILE)

    # Ensure command history is saved at exit
    atexit.register(lambda: readline.write_history_file(HISTORY_FILE))

    # Enable tab completion (optional)
    readline.parse_and_bind("tab: complete")

def create_session(tmux_session):
    server = libtmux.Server()
    session_name = tmux_session
    found = 1
    for session in server.sessions:
        if session.session_name == session_name:
            session_name = f"{tmux_session}_{found}"
            found += 1
    return server.new_session(session_name=session_name), session_name


def docki_remote(docki_config):
    
    setup_readline()

    
    tmux_session, session_name = create_session(docki_config["tag"])
    host_managers = []
    for id, host in enumerate(docki_config["remote"]["hosts"]):
        host_manager = HostManager(tmux_session, host["name"], id)
        if "workspace" in host:
            host_manager.send_command(f"cd {host['workspace']}")
        host_managers.append(host_manager)
    print("Connected to remote hosts.")
    launch_terminal_with_tmux(session_name)
    while True:
        try:
            command = input(f"(remote) {session_name}> ")
            if command == "exit":
                break
            for manager in host_managers:
                manager.send_command(command)
        except KeyboardInterrupt:
            # send ctrl+c to all panes
            for manager in host_managers:
                manager.send_command("C-c")
    for manager in host_managers:
        manager.close()
    print("Disconnected from remote hosts.")


def find_project_root():
    files_to_find = ["docki.yaml", "requirements.txt", "pyproject.toml", ".git"]
    current_dir = pathlib.Path(".").resolve()
    path = []
    while current_dir != current_dir.parent:
        path.insert(0, current_dir.name)
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

def print_logs(container):
    first = True
    while container.status == "running" or first:
        first = False
        for line in container.logs(stream=True):
            try:
                print(line.decode('utf-8'), end="") 
            except KeyboardInterrupt:
                return
            except:
                pass
        time.sleep(0.1)
        try:
            container.reload()
        except:
            return

def get_docki_config(project_root, remote=False):
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
    if remote:
        if "remote" not in docki_config:
            missing_values.append("remote")
    if len(missing_values) > 0:
        print(f"Missing values in docki.yaml: {', '.join(missing_values)}")
        print("Please fill in the missing values and run the script again.")
        exit(1)
    return docki_config

def get_volumes(project_root, target_root):
    if platform.system() == "Linux":
       return {project_root: {"bind": target_root, "mode": "rw"}, "/mnt": {"bind": "/mnt", "mode": "rw"}}
    else:
       return {project_root: {"bind": target_root, "mode": "rw"}}
    
def get_user():
    if platform.system() == "Linux":
        return  f"{os.getuid()}:{os.getgid()}"
    else:
        return "1000:1000" 


def build_docker_image(project_root, config, clean=False, output=False):
    base_image = config.get("base_image")
    system_dep = config.get("system_dep")
    tag = config.get("tag", "docki_image")
    uid, gid = get_user().split(":")
    if ":latest" not in tag:
        tag += ":latest"
    dockerfile = build_dockerfile(base_image, system_dep, project_root, uid, gid)
    if output:
        with open("Dockerfile", "w") as f:
            f.write(dockerfile)
        with open("build.sh", "w") as f:
            if clean:
                f.write(f"docker bulder build --no-cache -t {tag} - < Dockerfile")
            else:
                f.write(f"docker bulder build -t {tag} - < Dockerfile")
        return None, None
    print(f"Building the Docker image based on {base_image}...")
    # pathlib.Path("/tmp/docki").mkdir(parents=True, exist_ok=True)
    cmd = ["docker", "builder", "build", "-t", tag, "-"]
    if clean:
        cmd.insert(3, "--no-cache")
    print(f"Running the command: {' '.join(cmd)}")
    result = subprocess.run(
      cmd,
      input=dockerfile,
      text=True,          # Treat input and output as text.
      capture_output=True,  # Capture the output.
      )
    if result.returncode != 0:
        print("An error occurred while building the image:")
        print(result.stdout)
        print("Error message:")
        print(result.stderr)
        exit(1)
    print(f"Image {tag} has been built.")

    return tag

def run_container(tag, command, config, work_dir, project_root, target_root, output=False):
    shm_size = config.get("shm_size", "16G")
    base_image = config["base_image"]
    tag = config.get("tag")
    init_commands = config.get("init_commands", [])

    volumes = get_volumes(project_root, target_root)
    user = get_user()
    runtime = get_runtime(base_image)
    if len(init_commands) > 0:
        init_commands_str = "&& ".join(init_commands) + "&& " 
    else:
        init_commands_str = ""
    # add venv/bin to PATH
    command = ' '.join(command)
    env = ""
    if "python_dep" in config:
        env = f'export PATH={target_root}/venv/bin:$PATH &&'
    command = f'{env} {init_commands_str} {command}'
    command = f'bash -c "{command}"'
    if output:
        with open("run.sh", "w") as f:
            work_dir = f"cd {work_dir}"
            f.write(f"{work_dir}; {command}")
        volume_str = " ".join([f"-v {key}:{value['bind']}" for key, value in volumes.items()])
        if volume_str != "":
            volume_str += "-v "
        start_docker = f"docker run -it --rm --shm-size={shm_size} --network=host --user {user} {volume_str} -w {target_root} --runtime={runtime} {tag} /bin/bash"
        with open("start.sh", "w") as f:
            f.write(start_docker)

        return None
    # Run a container from the image
    client = docker.from_env()

    container = client.containers.run(tag, 
                                        command,
                                        stdin_open=True,
                                        stdout=True,
                                        stderr=True,
                                        tty=True,
                                        # remove=True,
                                        shm_size=shm_size,
                                        network_mode="host",
                                        detach = True,
                                        user=user,
                                        volumes=volumes,
                                        working_dir=work_dir,
                                        runtime=runtime,
                                        name=tag,
                                        )
    return container

def setup_venv(project_root, target_root, tag, config, clean=False, output=False):
    python_dep = config.get("python_dep")
    base_image = config.get("base_image")
    tag = config.get("tag")
    if "file" in python_dep:
        requirements = pathlib.Path(project_root) / python_dep.get("file")
        if not requirements.exists():
            print(f"Requirements file {requirements} not found")
            return
        else:
            requirements_cmd = f'-r {target_root}/{python_dep.get("file")}'
            python_dep = requirements.read_text().split("\n")
    else:
        requirements_cmd = " ".join(python_dep)
    docki_lock_file = pathlib.Path(f"{project_root}/venv/docki.lock")
    locked_python_dep = []
    if docki_lock_file.exists():
        locked_python_dep = yaml.safe_load(docki_lock_file.read_text()).get("python_dep")
    if set(locked_python_dep) != set(python_dep) or output:
        volumes = get_volumes(project_root, target_root)
        user = get_user()
        runtime = get_runtime(base_image)
        if output:
            with open("seup_venv.sh", "w") as f:
                f.write(f'python3 -m venv {target_root}/venv; {target_root}/venv/bin/pip install {requirements_cmd}')
            return
        print("Building the virtual environment and installing the requirements...")
        client = docker.from_env()

        container = client.containers.run(tag,
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
                                            name=tag,
                                            )
        print_logs(container)
        docki_lock_content = copy.deepcopy(config)
        docki_lock_content["python_dep"] = python_dep
        docki_lock_file.write_text(yaml.safe_dump(docki_lock_content))
    else:
        print("Requirements already installed.")

help = f"""dockipy version {dockipy_version} 
Replace python with dockipy to run your python script in a Docker container.
Example: dockipy my_script.py, this will run my_script.py in a Docker container.

A docki.yaml file is required in the project root to specify the base image, system dependencies and python dependencies.
If these files do not exist, they will be created in the project root if possible. otherwise, run 'docki --init' to create the docki.yaml file at the project root.
usage: 
    docki[py, shell, book] [OPTIONS] COMMAND

    options:
        -h, --help  Show this message and exit.
        --init      Create a docki.yaml file in the project root.

    commands:
        COMMAND     The command to run in the Docker container.
"""
def argsparse():
    remote = False
    clean = False
    output = False
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
    if args[1] == "--remote":
        remote = True
        args = args[1:]
    if args[1] == "--clean":
        clean = True
        args = args[1:]
    if args[1] == "--output":
        output = True
        args = args[1:]
    command = args[1:]
    return command, remote, clean, output

def dockikill():
    work_dir, project_root, target_root = find_project_root()

    docki_config = get_docki_config(project_root)
    tag = docki_config["tag"]

    client = docker.from_env()

     # Try to get the container by its name
    try:
        container = client.containers.get(tag)
        print(f"Found container {tag} with ID: {container.id}")
        container.kill()
        container.remove()
        print(f"Container {tag} has been removed.")
    except docker.errors.NotFound:
        print(f"No container with the name {tag} found.")
    except docker.errors.APIError as e:
        print(f"An error occurred: {str(e)}")


def dockistop():
    work_dir, project_root, target_root = find_project_root()

    docki_config = get_docki_config(project_root)
    tag = docki_config["tag"]

    client = docker.from_env()

    # Try to get the container by its name
    try:
        container = client.containers.get(tag)
        print(f"Found container {tag} with ID: {container.id}")
        container.stop()
        container.remove()
        print(f"Container {tag} has been removed.")
    except docker.errors.NotFound:
        print(f"No container with the name {tag} found.")
    except docker.errors.APIError as e:
        print(f"An error occurred: {str(e)}")


def dockiprune():
    # Prune the Docker system images, volumes, networks, and containers
    freed_space = 0
    client = docker.from_env()
    # Prune the containers
    to_gb = 1024**3
    containers = client.containers.prune()
    freed_space_containers = containers.get("SpaceReclaimed", 0) / to_gb
    print(f"Containers: Freed {freed_space_containers:.2f} GB of disk space.")
    freed_space += freed_space_containers

    # Prune the images
    images = client.images.prune()
    freed_space_images = images.get("SpaceReclaimed", 0) / to_gb
    print(f"Images: Freed {freed_space_images:.2f} GB of disk space.")
    freed_space += freed_space_images

    # Prune the volumes
    volumes = client.volumes.prune()
    freed_space_volumes = volumes.get("SpaceReclaimed", 0)  / to_gb
    print(f"Volumes: Freed {freed_space_volumes:.2f} GB of disk space.")
    freed_space += freed_space_volumes

    # Prune the networks
    networks = client.networks.prune()
    freed_space_networks = networks.get("SpaceReclaimed", 0) / to_gb
    print(f"Networks: Freed {freed_space_networks:.2f} GB of disk space.")
    freed_space += freed_space_networks

    # Prune the build cache
    build_cache = client.api.prune_builds()
    freed_space_build_cache = build_cache.get("SpaceReclaimed", 0) / to_gb
    print(f"Build cache: Freed {freed_space_build_cache:.2f} GB of disk space.")
    freed_space += freed_space_build_cache

    print(f"Total: Freed {freed_space:.2f} GB of disk space. (hopefully nobody was using it!)")