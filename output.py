import csv
import json
import os
from sys import stdout


def resolve_output_path(path, out_format):
    if path is not None:
        return path
    return f"results.{out_format}"


class Output:
    supported_formats = ["csv", "json"]

    def __init__(self, format, path):
        if format not in self.supported_formats:
            raise Exception("Unsupported output format")
        self.path = path
        if path == "stdout":
            self.path = stdout
        self.format = format
        self.writer = None
        self.first = True

    def __enter__(self):
        if self.path == stdout:
            self.fd = stdout
        else:
            self.fd = open(self.path, "w", 1, encoding="utf-8", newline="")
        if self.format == "json":
            self.fd.write("[")
        return self

    def __exit__(self, *args, **kwargs):
        if self.format == "json":
            self.fd.write(f"{os.linesep}]")
        if self.path == stdout:
            return
        self.fd.close()

    def write(self, finding):
        if self.format == "csv":
            self.write_csv(finding)
        if self.format == "json":
            self.write_json(finding)

    def write_csv(self, finding):
        if self.writer == None:
            self.writer = csv.DictWriter(
                self.fd, fieldnames=finding.__dict__.keys(), dialect="excel"
            )
            self.writer.writeheader()
        row = finding.__dict__
        for k in row.keys():
            if type(row[k]) == list:
                row[k] = ",".join(row[k])
        self.writer.writerow(row)

    def write_json(self, finding):
        sep = "" if self.first else ","
        self.first = False
        json_payload = json.dumps(finding.__dict__)
        self.fd.write(f"{sep}{os.linesep}{json_payload}")
        self.fd.flush()
