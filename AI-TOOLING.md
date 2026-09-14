# AI Tooling
This project was built with peer-programming help from AI tools.
This document describes in broad terms, which tools were used and how.

Quantic's plagiarism policy asks for conscientious citation of work that is not wholly my own and the MSSE Capstone Handbook lists "demonstrate the use of appropriate AI tooling to support software development" as a learning outcome of the project.

## Tools Used
- **AI Coding Assistant (Anthropic Claude, Agentic "Cowork" Mode):** Used as the primary development partner throughout. It helped with architecture decisions, generated much of the application and test code, built the experiment and study scripts, wrote the CI workflow and Docker deployment config, drafted documentation ideas and review and helped debug environment and build issues. Work proceeded phase by phase (config schema -> weather and ET -> soil water and yield -> controllers -> estimators -> economics -> experiment matrix -> API and dashboard -> deployment -> study and write-up), with review and testing at each step.

- **Cross-Entropy Method Policy (NumPy, in-Repo):** The RL comparison policy is an AI technique *inside* the deliverable, trained on the simulation engine and committed as fixed weights for reproducibility (see ADR-012).

## How AI Assistance was Used
- **Design & Architecture:** Weighing the positives and negatives of the stack (own FAO-56/FAO-33 engine, scipy HiGHS for the MPC, EKF and EnKF estimators, precompute and serve with Parquet and DuckDB, FastAPI, React with ECharts, Docker on Render). Trade-offs were weighed before committing and recorded as twelve architecture decision records.

- **Code Generation:** The drafting anbd layout of the following; engine modules, the controller ladder, the estimators, the metrics and economics models, the experiment matrix, the FastAPI service, both React applications, the digital twin viewers and the test suite were largely AI-generated, then reviewed, run and corrected.

- **Testing & CI:** The assistant designed the four test layers (unit against FAO worked examples, integration over whole seasons, contract tests on the API, property tests on invariants that must hold for any input) and wrote the GitHub Actions workflow that runs them across Python 3.10 to 3.12 alongside clean builds of both web applications.

- **Results Interrogation:** It queried the full experiment matrix systematically rather than spot-checking, which surfaced two findings that had been missed and that materially changed the write-up (see below).

- **Documentation & Presentation:** Drafted the documentation layout, formatting and styling then cross-checked with my backlog and the project plan.All was checked against the code and the results store before acceptance.

## What Worked Well
- **Rapid End-to-End Scaffolding:** Going from an empty repo to a validated engine, a deployed web application and a reproducible study was efficient allowing me more time to kick-off other sprint tasks. 

- **Validation Design:** The assistant introduced the cross-model validation against `pyfao56`. Therefore, it gerew my testing the engine and didn't restrict the scope to only against its own expectations. Helped achieve the strongest correctness evidence in the project.

- **Finding Problems I Had Missed:** 
    - A systematic sweep of all 98 matrix cells showed that the perfect-foresight "oracle" is beaten by deployable controllers in 9 of them, so it is not a valid upper bound as ADR-007 originally claimed. 

    - The same review established that the CEM policy is evaluated on the two seasons it was trained on, which is train/test leakage. See section 6.11 of the design document and in the presentation. The findings and documentation is now more honest than it would have been without that check.

- **Debugging Build & Environment Problems:** It diagnosed a stale `tsconfig.tsbuildinfo` that made `tsc -b` skip a file locally while CI compiled it and failed, a stale `.git/index.lock` that had been silently blocking every commit, and an import ordering and `noqa` breakage introduced by a formatter pass.

## What Did Not Work as Well
- **A File Watcher Corrupting Edits:** A sync/editor process intermittently truncated files or injected stray bytes mid-save. One instance left a shell line continuation backslash inside a TypeScript source file, which compiled locally against a stale build cache and only failed in CI. The fix was to write code, re-verify and scan for NUL bytes and stray characters after edits.

- **A Formatter Applied to the Wrong Languages:** A Prettier pass reformatted Python files, inserting blank lines into import blocks and hoisting `# noqa: E402` directives onto their own lines, where they suppress nothing. This broke lint across all three Python versions in CI. Prettier is now scoped away from Python.

- **Confident Framing Ahead of the Evidence:** Documentation drafts described the oracle as an "upper bound" and an "unattainable optimum". That was never checked against the matrix until later in the project. This was wrong and AI-drafted prose is fluent enough to make an unverified claim read as settled, which is precisely why every claim had to be traced back to engine output.

- **Version & API Assumptions:** Pinned library versions and tool behaviour needed checking against current documentation rather than trusting defaults.

## Data & Third-Party Sources
- **SILO / Queensland Government Longpaddock & the Australian Bureau of Meteorology** - real Mildura weather, station 76031 (CC BY 4.0, attributed in the README).

- **FAO Irrigation and Drainage Papers 56 and 33** - published methodology, implemented from the equations rather than adapted from another implementation, which is what makes the `pyfao56` agreement meaningful.

- **`pyfao56`** - used as an independent validation reference only; not vendored into the engine.

- **Three.js (r128)** - vendored at `viz/three.min.js` (MIT).

- Open-source Python and npm dependencies are declared in `pyproject.toml`, `frontend/package.json` and `product/package.json`.

No third-party source code was copied into this project.

## Position
AI tooling made this project faster and in the two cases documented above, more honest than it would otherwise have been. <br>
It did not choose the engineering problem, did not supply the domain model and did not generate a single reported result. Every figure in this repository, the dashboard and the presentation is engine output, traceable to `data/results/matrix.csv` and reproducible with the scripts in `scripts/`.
