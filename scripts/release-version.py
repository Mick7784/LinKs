"""Choose an official release number; never use the Actions run counter."""
import json, os, re
from pathlib import Path

def validate(value):
    if not isinstance(value,str) or not re.fullmatch(r"V[0-9]+\.[0-9]+",value) or len(value)>40:
        raise ValueError("Invalid application version")
    return value

def next_version(value):
    major,build=validate(value)[1:].split(".")
    return "V"+major+"."+str(int(build)+1).zfill(3)

def choose(message,official=False,override=""):
    pinned=re.match(r"^Release (V[0-9]+\.[0-9]+)(?:\s|$)",message)
    if not official and not pinned and not message.startswith("[release]"):
        return ""
    if override:return validate(override)
    if pinned:return validate(pinned.group(1))
    current=validate((Path(__file__).resolve().parent.parent/"VERSION").read_text().strip())
    return next_version(current)

if __name__=="__main__":
    value=choose(os.environ.get("RELEASE_MESSAGE",""),os.environ.get("OFFICIAL_RELEASE")=="true",os.environ.get("RELEASE_OVERRIDE",""))
    with open(os.environ["GITHUB_OUTPUT"],"a") as output:
        output.write("version="+value+"\ntag="+value.lower()+"\n")
