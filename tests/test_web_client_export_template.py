"""Regression tests for client-side polished export settings in the web template."""

import re
from pathlib import Path


TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "web" / "templates" / "index.html"


def test_template_contains_print_ready_export_profile_copy():
    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "Print-Ready Export" in html
    assert "Current-view PDF preserves manual layout." in html


def test_template_contains_high_resolution_client_export_settings():
    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "const EXPORT_PROFILE_SETTINGS = {" in html
    assert "targetLongEdge: 6800" in html
    assert "scaleMax: 2.6" in html
    assert "client-layout-polished" in html


def test_template_gates_secondary_actions_until_diagram_exists():
    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert 'id="primaryExportActions"' in html
    assert 'id="secondaryExportActions"' in html
    assert 'id="layoutActions"' in html
    assert 'id="zoomActions"' in html
    assert "function syncActionAvailability()" in html
    assert 'setElementHidden("primaryExportActions", !hasCode);' in html
    assert 'setElementHidden("secondaryExportActions", !hasCode);' in html
    assert 'setElementHidden("layoutActions", !hasDiagramData);' in html
    assert 'setElementDisabled("sharePdfBtn", !hasCode);' in html
    assert "Review is recommended before sharing this PDF." in html
    assert "async function assertZipBlob(blob)" in html
    assert "Batch export returned a file that is not a valid ZIP archive." in html
    assert "await assertZipBlob(blob);" in html


def test_template_event_bindings_reference_existing_controls():
    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    declared_ids = set(re.findall(r'id="([^"]+)"', html))
    direct_bound_ids = set(re.findall(r'\$\("([^"]+)"\)\.addEventListener', html))
    helper_bound_ids = set(re.findall(r'bindClick\("([^"]+)"', html))
    missing = sorted((direct_bound_ids | helper_bound_ids) - declared_ids)

    assert missing == []
    assert "selectAllWorkflowsBtn" not in direct_bound_ids
    assert "selectSingleWorkflowBtn" not in direct_bound_ids
    assert {"bulkPickAll", "bulkPickNone", "bulkExportAll"} <= helper_bound_ids


def test_template_groups_workflows_by_module():
    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "state.modules" in html
    assert "getWorkflowIdsForModule" in html
    assert "data-role=\"pick-module\"" in html
    assert "workflow-group-header" in html
