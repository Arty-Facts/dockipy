import dockipy.utils as utils
import pathlib, yaml, platform, subprocess, copy


def envibook():
    work_dir, project_root, target_root = utils.find_project_root()

    command, _remote, _clean, _output = utils.argsparse()

        
    docki_config = utils.get_docki_config(project_root)
    if "python_dep" not in docki_config:
        print("python_dep key not found in docki.yaml")
        return
        

    project_root = pathlib.Path(project_root)

    python_dep = docki_config.get("python_dep")
    base_image = docki_config.get("base_image")
    tag = docki_config.get("tag")
    if "file" in python_dep:
        requirements = project_root / python_dep.get("file")
        if not requirements.exists():
            print(f"Requirements file {requirements} not found")
            return
        else:
            requirements_cmd = f"-r {requirements}"
            python_dep = requirements.read_text().split("\n")
    else:
        requirements_cmd = " ".join(python_dep)
    docki_lock_file = project_root / "venv/docki.lock"
    locked_python_dep = []
    if docki_lock_file.exists():
        locked_python_dep = yaml.safe_load(docki_lock_file.read_text()).get("python_dep")
    if set(locked_python_dep) != set(python_dep):
        print("Building the virtual environment and installing the requirements...")
        if platform.system() == "Windows":
            subprocess.run(f'python -m venv {project_root}/venv', shell=True)
            subprocess.run(f'{project_root}/venv/Scripts/pip install {requirements_cmd}', shell=True)
        else:
            subprocess.run(f'python3 -m venv {project_root}/venv', shell=True)
            subprocess.run(f'{project_root}/venv/bin/pip install {requirements_cmd}', shell=True)
        docki_lock_content = copy.deepcopy(docki_config)
        docki_lock_content["python_dep"] = python_dep
        docki_lock_file.write_text(yaml.safe_dump(docki_lock_content))

    token = docki_config.get("notebook_token", "docki")
    password = docki_config.get("notebook_password", "docki")
    notebook_args = docki_config.get("notebook_args", "")

    if platform.system() == "Windows":
        command = f"{project_root.absolute()}/venv/Scripts/jupyter notebook --no-browser {notebook_args} --ServerApp.allow_origin='*' "+\
        f" --ServerApp.token='{token}'"+\
        f" --ServerApp.password='{password}'"+ " ".join(command)
        subprocess.run(command, shell=True)
    else:
        command = f"{project_root.absolute()}/venv/bin/jupyter notebook --no-browser {notebook_args} --ServerApp.allow_origin='*' "+\
        f" --ServerApp.token='{token}'"+\
        f" --ServerApp.password='{password}'" + " ".join(command)
        subprocess.run(command, shell=True)

