# Dockipy

[![PyPI - Version](https://img.shields.io/pypi/v/dockipy.svg)](https://pypi.org/project/dockipy)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/dockipy.svg)](https://pypi.org/project/dockipy)

**Table of Contents**

- [Installation](#installation)
- [What is `dockipy`?](#what-is-dockipy)
- [Configure environment](#configure-environment)
- [License](#license)
-----


## Installation

```bash
pip install dockipy
```

## What is `dockipy`?

`dockipy` is your ticket to productivity paradise, a simple yet mighty wrapper around the Docker command line interface. It's the friend who says, "Don't worry about the nitty-gritty, I got you!" Just lean back and let dockipy work its magic, it will mount you project in a container seamlessly. If it doesn't break then everything should be fine.

And here's the cherry on top: with `dockipy`, you can dive into a Python virtual environment inside your container. It's like a containerception—codeception—whatever you want to call it! Run your code with the ease, all thanks to dockipy.

But wait, there's a catch! Before you sail into the `dockipy`, make sure you have Docker installed. And if you're planning to use NVIDIA GPUs, brace yourself! Docker GPU driver installation is a mess, `dockipy` won't hold your hand through that chaos—consider yourself warned!

#### How to Use dockipy
Ready to embark on your container adventure? Here's how dockipy can make your coding dreams come true:

Run Your Code: Use dockipy to run your code in a container inside a Python virtual environment within another container. It's like Inception, but for coding!
```bash
dockipy my_script.py
```

#### How to Use dockishell

Need to run an arbitrary command in a container? No problem! Just fire up dockishell and let the container magic begin.

```bash
dockishell nvidia-smi
```

#### How to Use dockibook
Want to unleash the power of Jupyter Notebooks in a container? Say no more! Use dockibook and open the link in your browser, colab or visual studio code.

```bash
dockibook .
```

#### Don't want to use Docker but still would like to use the configuration? No problem! Use envipy and envibook to run your code and notebooks in a virtual environment.
Since Windows is such a messy work with rawdogging your environment is totally okay.
```bash
envipy my_script.py
```
    
```bash
envibook .
```


## Configure environment
Tired of Docker feeling like a high-maintenance diva? Set up your environment like a pro with docki.yaml. No more Docker dramas, just smooth sailing.

```bash
docki --init
```

### docki.yaml

This file is used to specify the base image, system dependencies, and python dependencies for the Docker container.
If the file does not exist, a template will be created in the project root using docki --init.

base_image: The base image for the Docker container. You can find images on [Docker Hub](https://hub.docker.com/).

system_dep: A list of system dependencies to install in the Docker container. Install with apt-get.

python_dep: A list of python dependencies to install in the Docker container or a path to a requirements.txt file.

```yaml
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
```

or 

```yaml
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
```

## Is something went wrong? 

You can stop or kill the container with the following commands. It will use the tag from the docki.yaml file to stop or kill the container.

```bash
dockikill
```

```bash
dockistop
```
But this is not happening often, right? 🤞

## TODO
- [ ] Add support Windows Notebooks
- [ ] Add support for Docker GPU driver installation on WLS2
- [ ] Add support for Mac. I don't have a Mac! Pls send donations to my [onlyfans](https://onlyfans.com/arty-facts) so that i can afford one!

## License

`dockipy` is like that cool friend who always lets you borrow their stuff without any fuss. It's distributed under the terms of the [apache-2.0](https://choosealicense.com/licenses/apache-2.0/) license. So go ahead, have some fun with it! 🎉
