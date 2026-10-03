"""Choose an official release number; never use the Actions run counter."""
import json, os, re
from pathlib import Path

def validate(value):
    if not isinstance(value,str) or not re.fullmatch(r"V[0-9]+\.[0-9]+",value) or len(value)>40:
        raise ValueError("Invalid application version")
    return value

def next_version(value, minor=False):
    major,number=validate(value)[1:].split(".")
    if len(number)>=3:
        feature,patch=int(number[:-2]),int(number[-2:])
    else:
        feature,patch=int(number),0
    if minor:return f"V{major}.{feature+1}"
    if patch==99:raise ValueError("99 corrections reached; select a minor release")
    return f"V{major}.{feature}{patch+1:02d}"

def choose(message,official=False,override=""):
    pinned=re.match(r"^Release (V[0-9]+\.[0-9]+)(?:\s|$)",message)
    if not official and not pinned and not message.startswith(("[release]", "[release minor]")):
        return ""
    if override:return validate(override)
    if pinned:return validate(pinned.group(1))
    current=validate((Path(__file__).resolve().parent.parent/"VERSION").read_text().strip())
    return next_version(current, minor=message.startswith("[release minor]"))

if __name__=="__main__":
    value=choose(os.environ.get("RELEASE_MESSAGE",""),os.environ.get("OFFICIAL_RELEASE")=="true",os.environ.get("RELEASE_OVERRIDE",""))
    with open(os.environ["GITHUB_OUTPUT"],"a") as output:
        output.write("version="+value+"\ntag="+value.lower()+"\n")
