import os
import argparse
import requests
import zipfile
import tempfile
import pathlib

# add or remove auth header
def add_authorization_header(headers):
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

def remove_authorization_header(headers):
    headers.pop("Authorization", "") # pop's default value -> no throw if no authorization header

# known mime types for Accept headers
ACCEPT_HEADERS = {
    "json":  "application/vnd.github+json",
    "zip":   "application/zip",
    "octet": "application/octet-stream",
}

# create request headers: doing only basic header content for now
def make_headers(mime_types, add_token=False):
    if isinstance(mime_types, str):
        mime_types = [mime_types]

    headers = {}
    if mime_types:
        headers["Accept"] = ", ".join(ACCEPT_HEADERS[m] for m in mime_types)

    if add_token:
        add_authorization_header(headers)

    return headers


# utility to check str content
def is_none_or_empty(s):
    return s is None or (isinstance(s, str) and s.strip() == "")


# writer response payload to the specified output file or temp file
# returns a triple: function status [fail/success], file path, is_temp_file [true/false]
# caller needs to delete any temp file created and left remaining when function returns 
# - temp file is deleted in case of download error: filename is returned if deletion fails
def write_file_from_response(resp, output_file_path = ""):
    temp_output_file = is_none_or_empty(output_file_path)

    # create temp file if needed; establish output dir if not temp file
    if temp_output_file:
        try:
            print(f"Creating temp download file")
            tf = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            output_file_path = tf.name
            tf.close()
        except Exception as e:
            print("Error creating temp download file", e)
            return False, "", True # function failed, no temp file path, temp file situation
    else:
        try:
            output_dir = os.path.dirname(output_file_path) or "."
            print(f"Establishing output directory {output_file_path}")
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            print(f"Error establishing output directory {output_dir}", e)
            return False, output_file_path, False # function failed, given file path, not temp file situation

    # actual download
    print(f"Writing to output file {output_file_path}")
    try:
        with open(output_file_path, "wb") as f:
            for chunk in resp.iter_content(8192):
                if chunk:
                    f.write(chunk)
        return True, output_file_path, temp_output_file # success, given/temp file path, yes/no temp file situation
    
    except Exception as e:
        print("Error writing to file", e)
        if temp_output_file:
            print("Deleting temp download file")
            try:
                os.remove(output_file_path)
                return False, "", True # function failed, temp file removed, temp file situation
            except Exception as e:
                print(f"Error deleting temp download file; file needs deleting", e)
                return False, output_file_path, True # function failed, temp file path, temp file situation
        
        return False, output_file_path, False # function failed, given file path, not temp file situation


# print response summary for diags
def print_response_summary(heading, resp):
    print(f"{heading} headers:", 
            {k:v for k,v in resp.headers.items() if k.lower() in ("location","www-authenticate","content-type","content-length")}
        )
    content_type = resp.headers.get("Content-Type")
    if "json" in content_type:
        print(f"{heading} JSON body:", resp.json())
    elif "text" in content_type:
        print(f"{heading} Text body:", resp.text[:1000])


# download the artifact file at given url: download to temp file if no output path provided
# - possibilities: expired artifact; url redirect;...
# returns a triple along the lines of function write_file_from_response
def download_artifact(source_url, output_file_path = "", timeout=15):
    temp_output_file = is_none_or_empty(output_file_path)

    # download the artifact file: response could be zip, json, or redirect depending on artifact status
    # https://docs.github.com/en/rest/actions/artifacts?apiVersion=2022-11-28#download-an-artifact
    headers = make_headers(["json", "zip", "octet"], True)
    
    try:
        initial_resp = requests.get(source_url, headers=headers, allow_redirects=False, timeout=timeout)
        print_response_summary("Intial", initial_resp)

        if initial_resp.status_code == 200:
            return write_file_from_response(initial_resp)
        
        if initial_resp.status_code == 302:
            redirect_url = initial_resp.headers.get("Location")
            if not redirect_url:
                print(f"Download redirected but no new location provided")
                return False, "", temp_output_file

            # if redirection, don't send GH auth; don't allow another redirect
            print(f"Download redirected to {redirect_url}")
            remove_authorization_header(headers)
            try:
                redirect_resp = requests.get(redirect_url, allow_redirects=False, stream=True, timeout=timeout)
                print_response_summary("Redirect", redirect_resp)

                if redirect_resp.status_code == 200:
                    return write_file_from_response(redirect_resp)
                
                if redirect_resp.status_code == 302:
                    print(f"Redirected again to {redirect_resp.headers.get("Location", "missing url")}; ignoring it")
                else:
                    print(f"Redirected artifact download failed with status {redirect_resp.status_code}")
                return False, "", temp_output_file
            
            except Exception as re:
                print(f"Error downloading from redirected url {redirect_url}", re)
                return False, "", temp_output_file

        # initial status other than 200 or 302
        print(f"Artifact download failed with status {initial_resp.status_code}")
        return False, "", temp_output_file

    except Exception as e:
        print(f"Error downloading from url {source_url}", e)
        return False, "", temp_output_file
    

# extract the complete content of a zip file to the specified o/p dir
# performs basic ZipSlip check: quite possible it is insufficient
# ZipSlip: https://research.jfrog.com/model-threats/zipslip/
def unzip_all(zip_file_path, output_dir, exist_ok=True):
    if os.path.isdir(output_dir):
        if exist_ok:
            print(f"Info: output dir {output_dir} exists")
        else:
            print(f"Error: output dir {output_dir} already exists")
            return False
        
    try:
        os.makedirs(output_dir, exist_ok=exist_ok)
    except Exception as e:
        print(f"Error establishing output dir {output_dir}", e)
        return False
    
    try:
        with zipfile.ZipFile(zip_file_path, "r") as z:
            # possibly barebones check for ZipSlip: ignore empty names and dir names
            # is the continue of endswith("/") problematic if the name is just "/"?
            base_dir = pathlib.Path(output_dir).resolve()
            for member in z.namelist():
                if not member or member.endswith("/"):
                    continue
                member_path = (base_dir / member).resolve()
                if base_dir not in member_path.parents and member_path != base_dir:
                    print(f"Unsafe path in zip member {member}")
                    return False
            
            # no ZipSlip, we think
            z.extractall(output_dir)
    except zipfile.BadZipFile:
        print(f"Invalid ZIP file {zip_file_path}")
        return False
    except Exception as e:
        print(f"Error extracting ZIP file {zip_file_path}; some files may have been extracted to output directory {output_dir}", e)
        return False
    
    print(f"Extracted ZIP file {zip_file_path} to {output_dir}")
    return True


def extract_tarball(tar_path, extract_dir):
    import tarfile
    
    try:
        with tarfile.open(tar_path, "r:*") as t:
            # Basic ZipSlip‑style safety: ensure members stay inside extract_dir
            base_dir = pathlib.Path(extract_dir).resolve()
            for member in t.getmembers():
                member_path = (base_dir / member.name).resolve()
                if base_dir not in member_path.parents and member_path != base_dir:
                    print(f"Unsafe path in tar member {member.name}")
                    return False
            t.extractall(extract_dir)
        return True
    except Exception as e:
        print(f"Error extracting tarball {tar_path}", e)
        return False


# get url of the first artifact for the most recent successful run
# return "" if url could not be obtained (for any reason) or if no artifact exists
# GH workflow runs REST API doc: https://docs.github.com/en/rest/actions/workflow-runs
def get_latest_artifact_url(repo_owner, repo, timeout=15):
    import traceback
    from requests.exceptions import RequestException
    from requests import Request, Session

    # return parsed JSON dict on success, or None on failure (prints diagnostics)
    def _resp_json_with_403(resp):
        try:
            if resp.status_code == 403:
                print("GitHub API returned 403. Check GITHUB_TOKEN, token scopes, or rate limits.")
                rl_rem = resp.headers.get("X-RateLimit-Remaining")
                rl_reset = resp.headers.get("X-RateLimit-Reset")
                if rl_rem is not None or rl_reset is not None:
                    print(f"Rate limit remaining: {rl_rem}; reset: {rl_reset}")
                try:
                    print("Response body:", resp.json())
                except Exception:
                    print("Response body (non-JSON):", resp.text[:1000])
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception:
            print("Failed to get/parse JSON response")
            print(traceback.format_exc())
            return None
   

    # list runs
    print(f"Finding successful workflow runs for repo {repo_owner}/{repo}...")
    base = f"https://api.github.com/repos/{repo_owner}/{repo}"
    actions_runs_url = f"{base}/actions/runs"
    headers= make_headers("json")
    try:
        r = requests.get(
            actions_runs_url,
            headers=headers,
            params={"per_page": 1, "status": "completed", "conclusion": "success"},
            timeout=timeout
        )
    except RequestException:
        print("Error getting runs info")
        print(traceback.format_exc())
        return ""

    payload = _resp_json_with_403(r)
    if payload is None:
        print(f"Missing JSON response to request for runs info")
        return ""

    runs = payload.get("workflow_runs") or []
    if not runs:
        print(f"No successful runs found")
        return ""

    print(f"Found {len(runs)} successful run(s)")

    run = runs[0]
    run_id = run.get("id") if isinstance(run, dict) else None
    if not run_id:
        print("Latest run missing field 'id' in API response")
        return ""

    print(f"Most recent run: id {run_id}; completed at {run.get("updated_at", "unknown date and time")}")

    # list artifacts for the run
    try:
        a_resp = requests.get(
            f"{base}/actions/runs/{run_id}/artifacts",
            params={"per_page": 1},
            timeout=timeout,
            headers=headers,
        )
    except RequestException:
        print(f"Error getting artifacts info for run_id {run_id}")
        print(traceback.format_exc())
        return ""

    a_payload = _resp_json_with_403(a_resp)
    if a_payload is None:
        print(f"Missing JSON response to request for artifacts info")
        return ""

    artifacts = a_payload.get("artifacts") or []
    if not artifacts:
        print(f"No artifacts for run_id {run_id}")
        return ""
    
    print(f"Found {len(artifacts)} artifact(s) for run_id {run_id}")

    # get the first artifact
    artifact = artifacts[0]
    if isinstance(artifact, dict):
        artifact_id = artifact.get("id")
        if not artifact_id:
            print(f"The first artifact for run_id {run_id} has no id")
            return ""
        
        if artifact.get("expired", False): # missing expired field means not expired
            print(f"Artifact {artifact.get("id")} for run_id {run_id} expired at {artifact.get("expires_at", "unknown date and time")}")
            return ""

        url = artifact.get("archive_download_url")
        if not url:
            print(f"Artifact {artifact.get("id")} for run_id {run_id} is missing field 'archive_download_url'")
            return ""

    print(f"URL for the first artifact is {url}")
    return url

# Recursively expand any .zip files found under root_dir.
# Each nested zip is extracted into a directory named after the zip file.
def unzip_recursive(root_dir):

    def handle_zip(zip_path, dirpath, name):
        extract_dir = os.path.join(dirpath, name[:-4])  # strip .zip

        print(f"Expanding nested zip: {zip_path} -> {extract_dir}")
        if not unzip_all(zip_path, extract_dir, exist_ok=True):
            print(f"Failed to expand nested zip {zip_path}")
            return

        try:
            os.remove(zip_path)
        except Exception as e:
            print(f"Warning: could not remove nested zip {zip_path}", e)

        unzip_recursive(extract_dir)


    def handle_tar(tar_path, dirpath, name):
        lower = name.lower()
        for suffix in [".tar.gz", ".tgz", ".tar.bz2", ".tar"]:
            if lower.endswith(suffix):
                extract_dir = os.path.join(dirpath, name[:-len(suffix)])
                break

        print(f"Expanding nested tarball: {tar_path} -> {extract_dir}")
        if not extract_tarball(tar_path, extract_dir):
            print(f"Failed to expand nested tarball {tar_path}")
            return

        try:
            os.remove(tar_path)
        except Exception as e:
            print(f"Warning: could not remove nested tarball {tar_path}", e)

        unzip_recursive(extract_dir)

    for dirpath, _, filenames in os.walk(root_dir):
        for name in filenames:
            lower = name.lower()
            if lower.endswith(".zip"):
                zip_path = os.path.join(dirpath, name)
                handle_zip(zip_path, dirpath, name)
            elif lower.endswith(".tar") or lower.endswith(".tar.gz") or lower.endswith(".tgz") or lower.endswith(".tar.bz2"):
                tar_path = os.path.join(dirpath, name)
                handle_tar(tar_path, dirpath, name)


# download the most recent artifact for the specified repo to the specified o/p dir
# if artifact_file_path is None or empty, downloads to a temp file and removes temp file before returning
# param remove_temp_artifact_file determines if temp artifact file is to be removed before returning
# returns dest file path: useful if artifact downloaded to temp file and temp file is not removed
def get_latest_artifact(repo_owner, repo, output_dir, artifact_file_path="", remove_temp_artifact_file=True):
    artifact_url = get_latest_artifact_url(repo_owner, repo)
    if artifact_url == "":
        print(f"No downloadable artifact")
        return

    # download artifact file from url: no exception possible
    download_done, artifact_file_path, temp_artifact_file = download_artifact(artifact_url, artifact_file_path)
    
    if not download_done:
        if artifact_file_path != "":    # remove artifact file whether or not it was temp file
            try:
                os.remove(artifact_file_path)
            except Exception as e:
                if temp_artifact_file:
                    print(f"Error removing temp artifact file {artifact_file_path}", e)
                else:
                    print(f"Error removing artifact file {artifact_file_path}", e)
        
        return # download failed

    # extract artifact: no exception possible
    print(f"Extracting artifact content to {output_dir}")
    if unzip_all(artifact_file_path, output_dir):
        print(f"Recursively extracting contained archive files")
        unzip_recursive(output_dir)
    else:
        print(f"Failed to download site artifact")

    # if temp_artifact_file, remove it if asked to: do this regardless of site download status
    if temp_artifact_file and remove_temp_artifact_file and artifact_file_path != "":
        try:
            os.remove(artifact_file_path)
        except Exception as e:
            print(f"Error removing temp artifact file {artifact_file_path}", e)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download and extract the first artifact from the most recent run of GH Actions"
    )
    parser.add_argument("repo_owner", help="GitHub name of user or org")
    parser.add_argument("repo", help="Name of repo")
    parser.add_argument("output_dir", help="Path to output directory (created if missing)")
    return parser.parse_args()


def main():
    args = parse_args()
    get_latest_artifact(args.repo_owner, args.repo, args.output_dir)


if __name__ == "__main__":
    main()
