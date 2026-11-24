from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent


def test_azure_pipeline_stage_order_and_approvals():
    doc = yaml.safe_load((ROOT / "pipelines" / "azure-pipelines.yml").read_text())
    stages = {s["stage"]: s for s in doc["stages"]}
    assert list(stages) == ["Validate", "Package", "DeployTest", "DeployProd"]
    assert stages["Package"]["dependsOn"] == "Validate"
    assert stages["DeployTest"]["dependsOn"] == "Package"
    assert stages["DeployProd"]["dependsOn"] == "DeployTest"
    envs = {s["stage"]: s["jobs"][0]["environment"] for s in doc["stages"] if s["stage"].startswith("Deploy")}
    assert envs == {"DeployTest": "apigee-test", "DeployProd": "apigee-prod"}


def test_every_proxy_directory_is_linted_and_deployed_in_the_pipeline():
    text = (ROOT / "pipelines" / "azure-pipelines.yml").read_text()
    for proxy in sorted(p.name for p in (ROOT / "proxies").iterdir() if p.is_dir()):
        assert proxy in text, f"{proxy} is missing from the pipeline"


def test_github_workflows_parse():
    for f in (ROOT / ".github" / "workflows").glob("*.yml"):
        assert "jobs" in yaml.safe_load(f.read_text()), f.name
