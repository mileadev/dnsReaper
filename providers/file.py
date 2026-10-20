import logging
from domain import Domain
from os import listdir
from os.path import isdir, isfile, join

description = "Read domains from a file (or folder of files), one per line"


def parse_domains(lines):
    domains = []
    for line in lines:
        name = line.strip()
        if not name or name.startswith("#"):
            continue
        domains.append(Domain(name))
    return domains


def fetch_domains(filename, **args):
    if isfile(filename):
        with open(filename) as file:
            try:
                domains = parse_domains(file.readlines())
                logging.warning(
                    f"Ingested {len(domains)} domains from file '{filename}'"
                )
            except Exception as e:
                logging.error(f"Could not read any domains from file {filename} -- {e}")
                exit(-1)
    elif isdir(filename):
        domains = []
        files = fetch_nested_files(filename)
        for f in files:
            try:
                with open(f) as file:
                    domains += parse_domains(file.readlines())
                logging.debug(f"Ingested domains from file '{f}'")
            except Exception:
                logging.debug(f"Could not read file '{f}'")
        logging.warning(f"Ingested {len(domains)} domains from folder '{filename}'")
    else:
        logging.error(f"Path does not exist: {filename}")
        domains = []
    return domains


def fetch_nested_files(dir):
    files = []
    for item in listdir(dir):
        path = join(dir, item)
        if isfile(path):
            files.append(path)
        else:
            files = [*files, *fetch_nested_files(path)]
    return files
