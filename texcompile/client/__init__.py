import base64
import logging
import os
import os.path
import posixpath
import tarfile
from dataclasses import dataclass
from io import BytesIO
from sys import platform
from typing import Dict, List
import time

import requests
from typing_extensions import Literal

logger = logging.getLogger("texcompile-client")

if platform == "linux" or platform == "linux2":
    try:
        from memory_tempfile import MemoryTempfile
        tempfile = MemoryTempfile()
    except:
        import tempfile
else:
    import tempfile

Path = str


class ServerConnectionException(Exception):
    pass


class CompilationException(Exception):
    pass


@dataclass
class OutputFile:
    type_: Literal["pdf", "ps"]
    name: str


@dataclass
class Result:
    success: bool
    main_tex_files: List[str]
    log: str
    output_files: List[OutputFile]

    def __repr__(self) -> str:
        return (
            f"Result: {'success' if self.success else 'failure'}. "
            + f"Compiled TeX [{', '.join(self.main_tex_files)}] "
            + f"into [{', '.join([f.name for f in self.output_files])}]. "
            + "Log: "
            + self.log[:100]
            + ("..." if len(self.log) > 100 else "")
        )


def send_request(sources_dir, host, port, autotex_or_latexml, main_tex=' ') -> dict:
    with tempfile.TemporaryDirectory() as temp_dir:
        # Prepare a gzipped tarball file containing the sources.
        archive_filename = os.path.join(temp_dir, "archive.tgz")
        with tarfile.open(archive_filename, "w:gz") as archive:
            archive.add(sources_dir, arcname=os.path.sep)

        # Prepare query parameters.
        with open(archive_filename, "rb") as archive_file:
            files = {"sources": ("archive.tgz", archive_file, "multipart/form-data")}
            data = {"autotex_or_latexml": autotex_or_latexml, "main_tex_file": main_tex}
            if autotex_or_latexml == "latexml":
                assert main_tex, "No main .tex file specified."
            # Make request to service.
            endpoint = f"{host}:{port}/"
            try:
                response = requests.post(endpoint, files=files, data=data)
                while response.status_code == 104:
                    response = requests.post(endpoint, files=files, data=data)
            except requests.exceptions.RequestException as e:
                raise ServerConnectionException(
                    f"Request to server {endpoint} failed.", e
                )

    # Get result
    return response.json()


def compile_pdf(
    sources_dir: Path,
    output_dir: Path,
    host: str = "http://127.0.0.1",
    port: int = 8000,
) -> Result:

    data = send_request(sources_dir, host, port, "autotex")

    # Check success.
    if not (data["success"] or data["has_output"]):
        raise CompilationException(data["log"])

    output_files: List[OutputFile] = []
    result = Result(
        success=data["success"],
        main_tex_files=data["main_tex_files"],
        log=data["log"],
        output_files=output_files,
    )

    # Save outputs to output directory, and create manifest of output files.
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for i, output in enumerate(data["output"]):
        type_ = output["type"]
        # Use posixpath to get the base name, with the assumption that the TeX server will be
        # returning paths to compiled files in POSIX style (rather than, say, Windows).
        basename = posixpath.basename(output["path"])
        output_files.append(OutputFile(type_, basename))

        # Save output file to the filesystem.
        save_path = os.path.join(output_dir, basename)
        if os.path.exists(save_path):
            logger.warning(
                "File already exists at %s. The old file will be overwritten.",
                save_path,
            )
        base64_contents = output["contents"]
        contents = base64.b64decode(base64_contents)
        with open(save_path, "wb") as file_:
            file_.write(contents)

    return result


def compile_pdf_return_bytes(
    sources_dir: Path,
    host: str = "http://127.0.0.1",
    port: int = 8000,
) -> Result:
    
    data = send_request(sources_dir, host, port, "autotex")

    # Check success.
    if not (data["success"] or data["has_output"]):
        raise CompilationException(data["log"])

    for i, output in enumerate(data["output"]):
        type_ = output["type"]
        if type_ == 'pdf':
            basename = posixpath.basename(output["path"])
            base64_contents = output["contents"]
            contents = base64.b64decode(base64_contents)
            return basename, BytesIO(contents)

    raise CompilationException('No pdf output.')
    
def compile_html_return_text(
    main_tex: str,
    sources_dir: Path,
    host: str = "http://127.0.0.1",
    port: int = 8000,
) -> str:
    data = send_request(sources_dir, host, port, "latexml", main_tex)

    # Check success.
    if not (data["success"] or data["has_output"]):
        raise CompilationException(data["log"])

    for i, output in enumerate(data["output"]):
        type_ = output["type"]
        if type_ == 'html':
            base64_contents = output["contents"]
            contents = base64.b64decode(base64_contents).decode("utf-8")
            return contents

    raise CompilationException('No pdf output.')

from .local import compile_pdf_locally

__all__ = [
    "compile_pdf_locally",
]