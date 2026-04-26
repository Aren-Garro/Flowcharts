"""Tests for document import cleanup and workflow splitting."""

from src.importers.content_extractor import ContentExtractor
from src.importers.workflow_detector import WorkflowDetector
from src.parser.nlp_parser import NLPParser
from web.app import SAMPLE_WORKFLOWS


def test_preprocess_for_parser_drops_reference_text_and_keeps_actions():
    text = """
    # Table of Contents
    Phase 1.......................... 2
    Phase 2.......................... 3

    # Purpose
    This manual describes the full process in detail.

    ## Phase 1: Intake
    Procedure:
    1) Receive the device from the customer
    2) Verify the serial number
    Next Step:
    If approved, move to Repair

    ## Phase 2: Repair
    - Replace the failed component
    - Test the repaired unit
    """

    extractor = ContentExtractor()

    processed = extractor.preprocess_for_parser(text)

    assert "Table of Contents" not in processed
    assert "Purpose" not in processed
    assert "Procedure:" not in processed
    assert "Next Step:" not in processed
    assert "# Phase 1: Intake" in processed
    assert "# Phase 2: Repair" in processed
    assert "1. Receive the device from the customer" in processed
    assert "2. Verify the serial number" in processed
    assert "If approved, move to Repair" in processed
    assert "- Replace the failed component" in processed


def test_content_extractor_keeps_user_login_sample_as_single_workflow():
    sample = SAMPLE_WORKFLOWS["user-login"]["text"]
    extractor = ContentExtractor()

    workflows = extractor.extract_workflows(sample)
    processed = extractor.preprocess_for_parser(workflows[0]["content"])
    summary = extractor.get_workflow_summary(processed)

    assert len(workflows) == 1
    assert "1. User opens login page" in processed
    assert "5. If 2FA enabled, send verification code" in processed
    assert "9. End" in processed
    assert summary["step_count"] == 9


def test_enabled_does_not_make_action_line_a_header():
    extractor = ContentExtractor()

    assert extractor._is_header("If 2FA enabled, send verification code") is False
    assert extractor._is_header("5. If 2FA enabled, send verification code") is False


def test_auto_detect_keeps_manual_sections_separate():
    text = """
    # 1. Product Knowledge
    1. Review product lineup
    2. Confirm supported models
    3. Document key differences

    # 2. Intake Review
    1. Open the service request
    2. Validate the serial number
    3. Record the failure notes

    # 3. Fulfillment
    1. Pack the repaired unit
    2. Send the shipment notification
    3. Close the request
    """

    detector = WorkflowDetector(split_mode="auto")

    workflows = detector.detect_workflows(text)

    assert len(workflows) == 3
    assert [workflow.title for workflow in workflows] == [
        "1. Product Knowledge",
        "2. Intake Review",
        "3. Fulfillment",
    ]


def test_auto_detect_merges_phased_stage_sections():
    text = """
    # Stage 1: New Request
    1. Receive the request
    2. Validate required fields
    3. Move the ticket to "Queued"

    # Stage 2: Triage
    1. Review the request details
    2. Assign the owner
    3. Move the ticket to "Repair"

    # Stage 3: Repair
    1. Repair the device
    2. Test the output
    3. Move the ticket to "Ready to Ship"

    # Stage 4: Closeout
    1. Confirm payment
    2. Ship the device
    3. Update ticket to "Closed"
    """

    detector = WorkflowDetector(split_mode="auto")

    workflows = detector.detect_workflows(text)

    assert len(workflows) == 1
    assert workflows[0].title == "Pipeline: Stage 1: New Request to Stage 4: Closeout"
    assert "## Stage 1: New Request" in workflows[0].content
    assert "## Stage 4: Closeout" in workflows[0].content


def test_auto_detect_keeps_short_stage_sections():
    text = """
    # Stage 1: Intake
    Once the order is received, create the intake record

    # Stage 2: Ready
    Move the ticket to "Ready"
    """

    detector = WorkflowDetector(split_mode="auto")

    workflows = detector.detect_workflows(text)

    assert len(workflows) == 2
    assert [workflow.title for workflow in workflows] == [
        "Stage 1: Intake",
        "Stage 2: Ready",
    ]


def test_section_filter_skips_prerequisites_heading():
    text = """
    # Prerequisites
    1. Confirm admin access
    2. Download the support image

    # Device Setup
    1. Boot the device
    2. Install the image
    3. Verify connectivity
    """

    detector = WorkflowDetector(split_mode="section")

    workflows = detector.detect_workflows(text)

    assert len(workflows) == 1
    assert workflows[0].title == "Device Setup"


def test_merged_pipeline_text_keeps_phase_groups_for_export():
    text = """
    # 1. Intake
    1. Open the repair request
    If all required information is present:
    - Move the ticket to 'Label Sent to Customer'

    # 2. Label Sent to Customer
    - Monitor the tracking ID
    If tracking shows the package has shipped:
    - Move the ticket to 'Shipped'

    # 3. Shipped
    - Confirm delivery
    """

    detector = WorkflowDetector(split_mode="auto")
    sections = detector._try_header_detection(text.strip().splitlines())
    workflow = detector._merge_sections(detector._analyze_and_filter(sections))

    steps = NLPParser(use_spacy=False).parse(workflow.content)

    assert steps
    assert all(not step.text.startswith("##") for step in steps)
    assert [step.group for step in steps[:4]] == [
        "1. Intake",
        "1. Intake",
        "2. Label Sent to Customer",
        "2. Label Sent to Customer",
    ]
