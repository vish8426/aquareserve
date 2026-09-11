# AquaReserve - Product Roadmap
From validated simulation to a sellable product. This roadmap turns the AquaReserve project (a validated optimization engine plus a quantified ROI proof) into a commercial offer that farmers and farming enterprises will buy. It is organised as epics with candidate user stories written for a sprint board.

> Note: The pricing, grant and legal or ownership items are prompts to validate with an accountant and a lawyer familiar with Australian agriculture and water law. They are not financial or legal advice.

## Guiding Principles
- The optimization engine and the ROI evidence already exist. Most of this roadmap is delivery, hardware and commercial wrapping around that core, not new science. 
- **Keep Farmer's Upfront Cost Small:** Buy anything commoditized, build only genuine IP and offer pricing that defers or shrinks capex (subscription, equipment-as-a-service, grants). 
- **Safety-Critical Control never Depends on the Subscription:** The edge node must keep the crop safe when comms, cloud or billing are unavailable. 
- **Reuse the ROI Model as the Sales Tool:** The same engine that proved the case becomes the quoting and site-design configurator.

## Phase A - Prove it on a Real Farm
Goal: One real season of evidence that converts "simulation" into "product".

> **Scope Note (Future Work):** This phase is deliberately **outside the scope of the simulation-only project**. It cannot be completed in software: It needs a physical pilot farm, installed hardware, a full growing season of real data and an independent agronomist. It is documented here as the first real-world step a commercial follow-on would take. 
>
> The system instead de-risks it by delivering the validated engine (checked against pyfao56 and AquaCrop-OSPy), the calibration tooling and the sensitivity study that a pilot would confirm.

- **A1:** As a prospective customer, I want a validated case study from a real farm so that I trust the yield-protection and payback claims.
- **A2:** As the team, we want 1-3 signed pilot agreements (low or no cost) so that we can instrument real sites for a season.
- **A3:** As an engineer, I want the engine calibrated to each pilot site (soil PAWC, crop
  varieties, real reserve volume, local weather) so that predictions match the ground truth.
- **A4:** As an engineer, I want a season of logged sensor data compared against predicted yield and water use so that we can quantify model accuracy in the field.
- **A5:** As marketing, I want an agronomy partner to co-sign the agronomic claims so that the case study carries independent credibility.

## Phase B - Hardware Productization (Catalogue + Make vs Buy)
Goal: A defined, certifiable system where the custom surface is kept to firmware, the optimizer and integration. See the companion `AquaReserve-Hardware-BOM.xlsx` for the itemised catalogue.

- **B1:** As a product owner, I want a full Bill of Materials with indicative unit costs and a per-farm sizing rule (small, medium, large) so that we can quote and cost a system.
- **B2:** As a product owner, I want a formal make-vs-buy decision per component so that we only build what is genuine IP (firmware, optimizer, integration) and buy the rest.
- **B3:** As an engineer, I want an "AquaReserve Node" built from a COTS enclosure running our firmware (so that we ship without custom PCB tooling until volume justifies).
- **B4:** As an engineer, I want a certification plan (electrical safety, IP rating, Australian RCM mark, EMC, AS923 LoRaWAN band) so that the product is legal to sell and install.
- **B5:** As a safety owner, I want valves and pump to default to a safe state with a local fallback irrigation policy so that a comms or cloud outage never risks the crop.
- **B6:** As operations, I want a standardized install kit (mounts, cabling, solar, battery) so that installs are repeatable and cheap.

## Phase C - Software: Demo to Live Control & Monitoring Product
Goal: Evolve the precompute and serve demo into a live, per-customer, two-way system. This is where a proper database (PostgreSQL/TimescaleDB) is warranted over the demo's Parquet/DuckDB.

> **Product vs Dashboard (Design Decision):** The current single React app serves two purposes that should split. The **results dashboard** (yield protection, economics, reserve sizing, the twins) is a presentation deliverable.
>
> The **customer product** (the configurator today, plus live control and monitoring later) should become its **own deployable app** with its own routing, auth and a distinct product theme.

- **C0:** As the team, we want the product web-app split from the results dashboard into its own app (own build, routing and theme) so that the customer product and the system dashboard evolve independently. 

  The customer app lives in `product/` with a marketing home page, the login gate, the configurator, a downloadable proposal, a save-a-quote form and a live monitor demo. 
  
  The results dashboard in `frontend/` stays green and results-only. The whole product app is login-gated. The backend serves the dashboard at `/` and the product app at `/product` from one service; splitting `product/` to its own deployable Render service (and promoting the copied shared files into a shared package) is the remaining step.

  - **Live Monitor Demo (Preview of C3/C4):** The monitor page is an in-browser soil emulator drives the sense-decide-actuate loop against a stateless `POST /api/demo/decide` (`backend/app/demo.py`) that runs the same threshold, critical stage and finite reserve logic family as the deployable controllers, so the loop runs live with no hardware. The full live control and monitoring product (real telemetry, two-way control) remains C2-C4 future work.

- **C1:** As a customer org, I want multi-tenant accounts with farms, zones and roles so that my operation is isolated and access is controlled.
- **C2:** As the platform, I want a telemetry ingest pipeline (MQTT or LoRaWAN into TimescaleDB) so that live sensor and reserve data flow into the system.
- **C3:** As a grower, I want the optimizer to run live on my real data and issue valve and pump setpoints, with manual override and an audit log, so that the system acts safely on my behalf.
- **C4:** As a grower, I want a monitoring app (dashboard plus live status, alerts and a phone-friendly paddock view) so that I can see and steer the system from anywhere.
- **C5:** As a grower, I want the edge node to keep irrigating on a sensible local policy when offline and sync when reconnected so that reliability does not depend on the network.
- **C6:** As support, I want over-the-air firmware updates and remote diagnostics so that we catch faults early.

## Phase D - Commercial Model (Shrink the Upfront Number)
Goal: An offer whose entry cost is small enough that farmers say yes.

> The configurator that powers has a full design spec in [`docs/CONFIGURATOR_SPEC.md`](CONFIGURATOR_SPEC.md).

- **D1:** As a prospect, I want a self serve configurator that sizes hardware and shows my payback from a few farm inputs so that I can see the value before a sales call (reuses the ROI engine).
- **D2:** As a buyer, I want pricing options (outright capex, an equipment-as-a-service lease or an outcome share on water saved) so that I can pick a model that fits my cash flow.
- **D3:** As a buyer, I want a free or low monitoring tier and a paid optimization and control tier so that I can start cheap and upgrade. Safety control is never gated.
- **D4:** As a buyer, I want help identifying grants and rebates that offset capex (drought resilience and water-efficiency programs) so that my out-of-pocket cost drops.
- **D5:** As the business, I want a unit-economics model (BOM plus install cost, gross margin, and the farmer's payback) so that pricing is grounded and sustainable.

## Phase E - Installation & Operations Pipeline
Goal: AquaReserve delivers the whole system.

- **E1:** As a salesperson, I want a site assessment and design tool that generates a system design and quote from farm inputs so that proposals are fast and consistent.
- **E2:** As operations, I want a certified installer network (partnering with irrigation dealers) so that we scale installs without hiring crews everywhere.
- **E3:** As an installer, I want a commissioning checklist and customer handover pack so that every install is calibrated and documented.
- **E4:** As a customer, I want support with an SLA, spare parts logistics and remote monitoring so that faults are fixed fast, ideally before I notice them.
- **E5:** As the business, I want warranty and service contract terms so that liability and revenue
  are both defined.

## Phase F - Company, IP & Brand
Goal: The legal and brand foundation that lets the product scale and be defended.

> **Scope Note (Future Work):** This phase is **outside the scope of the simulation-only project**.
>
> Incorporation, trademarks, patent filings, data and liability terms and insurance are commercial and legal actions that require a founder, an accountant and a lawyer, not code. They are recorded here so the path is visible. The project establishes only the starting IP posture (a proprietary licence) and keeps the engine, firmware and data proprietary so the moat is protectable later.

- **F1:** As a founder, I want AquaReserve incorporated with the trademark and brand assets secured.
- **F2:** As a founder, I want the IP protected (optimizer as trade secret or patent if novel; firmware and data proprietary) so that competitors cannot copy the moat. 
- **F3:** As a customer and as the business, I want clear data ownership, privacy and liability terms plus appropriate insurance so that influencing water decisions is contractually sound.
- **F4:** As an enterprise buyer, I want interoperability with existing farm data standards (AgGateway ADAPT, ISOBUS) so that AquaReserve fits my current tools.

## Suggested Sequencing
Run the pilot:

    a. first, in parallel with a lean BOM.
    b. the configurator plus pricing.
    c. together those three make a sellable offer.
    d. the live SaaS and control build.
    e. the install and operations pipeline.
    f. the company, IP and brand track runs continuously in the background.

## How this Builds on What Already Exists
- The engine and ROI model become the **configurator** and the pilot calibration tool.
- The precompute and serve backend and React dashboard become the **monitoring app**, extended with live telemetry and control.
- The 2D and 3D twins become the **customer-facing visualisation** of a live farm.
- The documented modeled edge system (sensors, valves, gateway, edge controller) becomes the real **BOM and node**.
