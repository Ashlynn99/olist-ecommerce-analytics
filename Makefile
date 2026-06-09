PYTHON ?= python3
VENV ?= .venv
PYTHON_BIN := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
CHECK_PYTHON := $(if $(wildcard $(PYTHON_BIN)),$(PYTHON_BIN),$(PYTHON))

.PHONY: setup data analysis sql purchase-model cohort seller-monitor intervention-value dashboard format check report all clean

setup:
	$(PYTHON) -m venv $(VENV)
	$(PYTHON_BIN) -m pip install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt

data:
	$(PYTHON_BIN) scripts/check_data.py

analysis:
	$(PYTHON_BIN) scripts/run_pipeline.py

sql:
	$(PYTHON_BIN) sql/00_create_database.py

purchase-model:
	$(PYTHON_BIN) src/purchase_time_risk_model.py

cohort:
	$(PYTHON_BIN) src/cohort_repeat_analysis.py

seller-monitor:
	$(PYTHON_BIN) src/seller_monthly_risk_monitor.py

intervention-value:
	$(PYTHON_BIN) src/intervention_value_simulation.py

dashboard:
	$(PYTHON_BIN) -m streamlit run dashboard/app.py

format:
	$(CHECK_PYTHON) -m black dashboard scripts sql src
	$(CHECK_PYTHON) scripts/format_markdown.py

check:
	$(CHECK_PYTHON) -m black --check dashboard scripts sql src
	$(CHECK_PYTHON) scripts/format_markdown.py --check
	$(CHECK_PYTHON) scripts/quality_check.py

report:
	@printf "Main report: reports/final_report.md\n"
	@printf "EDA findings: reports/eda_key_findings.md\n"
	@printf "Model summary: reports/modeling_low_review_summary.md\n"
	@printf "Purchase-time model: reports/purchase_time_model_summary.md\n"
	@printf "Cohort analysis: reports/cohort_repeat_analysis_summary.md\n"
	@printf "Seller monthly monitoring: reports/seller_monthly_monitoring_summary.md\n"
	@printf "Intervention value simulation: reports/intervention_value_summary.md\n"
	@printf "Additional analysis: reports/additional_analysis_summary.md\n"

all: data analysis report

clean:
	@printf "Generated data and report outputs are intentionally kept.\n"
	@printf "Remove data/processed/, data/database/, or reports/figures/ manually only if you want a fresh rebuild.\n"
