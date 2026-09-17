"""Validate audited runtime dependencies and generate a release SPDX inventory."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import re
import subprocess
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from archivelens import __version__

_NAME_NORMALIZER = re.compile(r"[-_.]+")
_REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9_.-]*)")


def normalize_name(name: str) -> str:
    return _NAME_NORMALIZER.sub("-", name).lower()


def load_policy(root: Path) -> dict:
    policy = json.loads((root / "license-policy.json").read_text(encoding="utf-8"))
    if policy.get("schema_version") != 1:
        raise RuntimeError("Unsupported license-policy.json schema")
    return policy


def project_runtime_roots(root: Path) -> list[str]:
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    roots = []
    for requirement in project.get("dependencies", []):
        match = _REQUIREMENT_NAME.match(requirement)
        if not match:
            raise RuntimeError(f"Cannot parse runtime dependency: {requirement}")
        roots.append(match.group(1))
    return roots


def _installed_distribution(name: str):
    try:
        return importlib.metadata.distribution(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def runtime_dependency_closure(root: Path) -> dict[str, dict[str, str]]:
    """Return installed runtime distributions reachable from project dependencies."""
    pending = list(project_runtime_roots(root))
    resolved: dict[str, dict[str, str]] = {}
    while pending:
        requested = pending.pop()
        distribution = _installed_distribution(requested)
        if distribution is None:
            raise RuntimeError(f"Runtime dependency is not installed: {requested}")
        actual_name = distribution.metadata.get("Name") or requested
        key = normalize_name(actual_name)
        if key in resolved:
            continue
        resolved[key] = {"name": actual_name, "version": distribution.version}
        for requirement in distribution.requires or []:
            # Optional extras are not part of ArchiveLens's default runtime closure.
            if re.search(r"\bextra\s*(?:==|!=)", requirement):
                continue
            match = _REQUIREMENT_NAME.match(requirement)
            if not match:
                continue
            dependency = match.group(1)
            if _installed_distribution(dependency) is not None:
                pending.append(dependency)
    return resolved


def _python_policy(policy: dict) -> dict[str, tuple[str, dict]]:
    return {
        normalize_name(name): (name, record)
        for name, record in policy.get("python_packages", {}).items()
    }


def validate_runtime_package_names(package_names: list[str], policy: dict) -> None:
    audited = _python_policy(policy)
    unknown = sorted(name for name in package_names if normalize_name(name) not in audited)
    if unknown:
        raise RuntimeError(
            "Unreviewed runtime dependencies: "
            + ", ".join(unknown)
            + ". Review licensing and add explicit policy entries before release."
        )
    rejected = []
    for name in package_names:
        _display, record = audited[normalize_name(name)]
        if record.get("scope") != "runtime" or not record.get("approved_for_distribution"):
            rejected.append(name)
    if rejected:
        message = "Runtime dependencies are not approved for distribution: "
        raise RuntimeError(message + ", ".join(rejected))


def audited_runtime_packages(root: Path, policy: dict) -> list[dict]:
    closure = runtime_dependency_closure(root)
    validate_runtime_package_names([record["name"] for record in closure.values()], policy)
    audited = _python_policy(policy)
    result = []
    for key, installed in sorted(closure.items()):
        policy_name, record = audited[key]
        result.append(
            {
                "name": policy_name,
                "installed_name": installed["name"],
                "version": installed["version"],
                **record,
            }
        )
    return result


def _manual_version(record: dict) -> str | None:
    source = record.get("version_source")
    if source == "python":
        return platform.python_version()
    if source:
        try:
            return importlib.metadata.version(source)
        except importlib.metadata.PackageNotFoundError as exc:
            raise RuntimeError(f"Version source is not installed: {source}") from exc
    return record.get("version")


def _spdx_id(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9.-]+", "-", name).strip("-")
    return f"SPDXRef-Package-{slug or 'component'}"


def _package_record(name: str, version: str | None, record: dict) -> dict:
    package = {
        "SPDXID": _spdx_id(name),
        "name": name,
        "downloadLocation": "NOASSERTION",
        "filesAnalyzed": False,
        "licenseConcluded": record.get("license_expression", "NOASSERTION"),
        "licenseDeclared": record.get("license_expression", "NOASSERTION"),
        "copyrightText": "NOASSERTION",
        "primaryPackagePurpose": "LIBRARY",
        "comment": (
            f"ArchiveLens classification={record.get('classification', 'unclassified')}; "
            f"scope={record.get('scope', 'unknown')}; "
            f"license label={record.get('license_label', 'not recorded')}"
        ),
    }
    if version:
        package["versionInfo"] = version
    return package


def build_spdx_document(root: Path, source_commit: str) -> dict:
    policy = load_policy(root)
    runtime = audited_runtime_packages(root, policy)
    application_id = "SPDXRef-Package-ArchiveLens"
    packages = [
        {
            "SPDXID": application_id,
            "name": "ArchiveLens",
            "versionInfo": __version__,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "MIT",
            "licenseDeclared": "MIT",
            "copyrightText": "NOASSERTION",
            "primaryPackagePurpose": "APPLICATION",
            "comment": (
                "ArchiveLens application source; third-party components retain "
                "their own licenses."
            ),
        }
    ]
    relationships = []
    used_ids = {application_id}

    for record in runtime:
        package = _package_record(record["name"], record["version"], record)
        if package["SPDXID"] in used_ids:
            raise RuntimeError(f"Duplicate SPDX component identifier: {package['SPDXID']}")
        used_ids.add(package["SPDXID"])
        packages.append(package)
        relationships.append(
            {
                "spdxElementId": application_id,
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": package["SPDXID"],
            }
        )

    for record in policy.get("manual_components", []):
        if not record.get("approved_for_distribution"):
            name = record.get("name", "<unnamed>")
            raise RuntimeError(f"Manual component is not approved: {name}")
        package = _package_record(record["name"], _manual_version(record), record)
        if package["SPDXID"] in used_ids:
            raise RuntimeError(f"Duplicate SPDX component identifier: {package['SPDXID']}")
        used_ids.add(package["SPDXID"])
        packages.append(package)
        if record.get("scope", "").startswith("runtime"):
            relationships.append(
                {
                    "spdxElementId": application_id,
                    "relationshipType": "DEPENDS_ON",
                    "relatedSpdxElement": package["SPDXID"],
                }
            )

    created = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"ArchiveLens-{__version__}-release-sbom",
        "documentNamespace": (
            "https://github.com/cam11505/ArchiveLens/sbom/"
            f"{__version__}/{source_commit or 'unknown'}"
        ),
        "creationInfo": {
            "created": created,
            "creators": ["Tool: ArchiveLens scripts/license_audit.py"],
        },
        "documentDescribes": [application_id],
        "packages": packages,
        "relationships": relationships,
    }


def write_spdx_sbom(root: Path, destination: Path, source_commit: str) -> dict:
    document = build_spdx_document(root, source_commit)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return document


def git_commit(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true", help="Validate audited runtime dependencies"
    )
    parser.add_argument("--output", type=Path, help="Write an SPDX 2.3 JSON inventory")
    parser.add_argument("--source-commit", help="Source commit recorded in the SPDX namespace")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    policy = load_policy(root)
    runtime = audited_runtime_packages(root, policy)
    if args.check or not args.output:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "runtime_packages": [
                        {"name": item["name"], "version": item["version"]} for item in runtime
                    ],
                },
                indent=2,
            )
        )
    if args.output:
        commit = args.source_commit or git_commit(root)
        write_spdx_sbom(root, args.output, commit)
        print(f"Wrote SPDX SBOM: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
