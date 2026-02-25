# Flowchart Examples Gallery

This gallery demonstrates the versatility of the ISO 5807 Flowchart Generator across different industries and use cases.

## 💻 Software Development

### CI/CD Pipeline
**File:** `software/cicd_pipeline.txt`

Automate your deployment process visualization.

```bash
flowchart generate examples/gallery/software/cicd_pipeline.txt -o cicd.png
```

### API Request Handling
**File:** `software/api_request_flow.txt`

Document your API architecture and request flow.

### Code Review Process
**File:** `software/code_review.txt`

Standardize your team's review workflow.

---

## 🏢 Business Processes

### Employee Onboarding
**File:** `business/employee_onboarding.txt`

Streamline HR processes with clear visual guides.

### Invoice Processing
**File:** `business/invoice_processing.txt`

Map your accounts payable workflow.

### Customer Support Escalation
**File:** `business/support_escalation.txt`

Define clear escalation paths for support teams.

---

## 🎓 Education & Research

### Scientific Experiment Protocol
**File:** `education/experiment_protocol.txt`

Document laboratory procedures with precision.

### Research Paper Review Process
**File:** `education/paper_review.txt`

Visualize academic review workflows.

### Student Assignment Grading
**File:** `education/grading_workflow.txt`

Standardize grading procedures.

---

## 🏥 Healthcare

### Patient Intake Process
**File:** `healthcare/patient_intake.txt`

Optimize patient registration and triage.

### Medication Administration
**File:** `healthcare/medication_admin.txt`

Ensure safety with clear medication protocols.

### Emergency Response Protocol
**File:** `healthcare/emergency_response.txt`

Critical decision-making workflows for emergencies.

---

## 🛍️ E-commerce

### Order Fulfillment
**File:** `ecommerce/order_fulfillment.txt`

Track orders from purchase to delivery.

### Return Processing
**File:** `ecommerce/returns_workflow.txt`

Handle customer returns efficiently.

### Inventory Management
**File:** `ecommerce/inventory_check.txt`

Automate stock level monitoring.

---

## 🔒 Security & Compliance

### Access Control Request
**File:** `security/access_request.txt`

Manage permissions systematically.

### Incident Response
**File:** `security/incident_response.txt`

Respond to security incidents with clear protocols.

### Data Breach Notification
**File:** `security/breach_notification.txt`

Comply with notification requirements.

---

## 🏭 Manufacturing

### Quality Control Inspection
**File:** `manufacturing/quality_control.txt`

Ensure product quality with standardized checks.

### Equipment Maintenance
**File:** `manufacturing/maintenance_schedule.txt`

Preventive maintenance workflow.

### Production Line Setup
**File:** `manufacturing/production_setup.txt`

Document setup procedures.

---

## 📦 Logistics

### Package Tracking
**File:** `logistics/package_tracking.txt`

Trace shipments through the supply chain.

### Warehouse Receiving
**File:** `logistics/warehouse_receiving.txt`

Optimize receiving operations.

### Route Optimization
**File:** `logistics/route_planning.txt`

Plan efficient delivery routes.

---

## 🌐 DevOps

### Kubernetes Deployment
**File:** `devops/k8s_deployment.txt`

Visualize container orchestration.

### Monitoring Alert Response
**File:** `devops/alert_response.txt`

On-call incident handling.

### Database Migration
**File:** `devops/db_migration.txt`

Safe database update procedures.

---

## 📊 Data Science

### ML Model Training Pipeline
**File:** `datascience/ml_training.txt`

Document your machine learning workflow.

### Data Validation Process
**File:** `datascience/data_validation.txt`

Ensure data quality.

### ETL Pipeline
**File:** `datascience/etl_pipeline.txt`

Extract, transform, load data flows.

---

## Usage Tips

### Batch Generate All Examples
```bash
# Generate all examples as PNG
for file in examples/gallery/*/*.txt; do
    flowchart generate "$file" -o "${file%.txt}.png" --renderer graphviz
done
```

### Generate with Different Themes
```bash
# Dark theme
flowchart generate examples/gallery/software/cicd_pipeline.txt -o cicd_dark.png --theme dark

# Forest theme
flowchart generate examples/gallery/business/employee_onboarding.txt -o onboard_forest.png --theme forest
```

### Compare Renderers
```bash
# Try all renderers
for renderer in graphviz html d2 mermaid; do
    flowchart generate examples/gallery/healthcare/patient_intake.txt \
        -o patient_${renderer}.png --renderer $renderer
done
```

---

## Contributing Examples

Have a great use case? Contribute your workflow!

1. Create your workflow text file
2. Generate the flowchart
3. Test with `flowchart validate your_workflow.txt`
4. Submit a PR with:
   - Workflow text file in appropriate category
   - Brief description
   - Generated image (optional)

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for details.

---

## License

All examples are provided under MIT License - free to use and modify!
