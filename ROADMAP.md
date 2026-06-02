# OpsPilot Product Roadmap: Phases 4 — 10

This document outlines the master technical roadmap for the future development phases of OpsPilot. It acts as the source of truth for upcoming architectural layers, modules, and platform expansions.

---

## Phase 4 — Realtime Infrastructure & Event System

### Goal
Transform the platform from request/response APIs into a real-time operational system.

### Major Components & Directory Structure
Create: `app/websocket/`
- `manager.py`: Tracks active connections (mapping `business_id` and `user_id` to socket connections).
- `connection.py`: Encapsulates individual `WebSocket` connections and safe frame delivery.
- `broadcaster.py`: Publishes and subscribes to business-scoped events using Redis Pub/Sub for distributed scaling.
- `auth.py`: Extracts and validates JWT authentication tokens from socket session parameters.
- `events.py`: Integrates local system event emitters with the Redis Pub/Sub gateway.
- `routes.py`: Defines the WebSocket connection route (`/api/v1/ws`).

### Key Features
* **Live Dashboard Updates**: Instant orders list additions, real-time payment status indicators, streaming AI assistant chunk replies, and push notifications.
* **Workspace Presence**: Real-time tracking of active staff, online statuses, and tracking who is currently viewing specific orders.
* **Live Activity Feed**: Real-time broadcast of events: `order.created`, `payment.success`, `ai.insight.generated`.

### Suggested Events
* `order.created`, `order.updated`, `payment.success`, `payment.failed`, `notification.created`, `analytics.updated`, `ai.response.chunk`

### Required Infrastructure
* **Redis Pub/Sub**: Serves as the socket fanout layer, cross-instance broadcaster, and global event bus to guarantee effortless horizontal scaling.

---

## Phase 5 — Workflow Automation Engine

### Goal
Allow businesses to automate complex operational flows inside OpsPilot, behaving like a mini Zapier/n8n/business rules engine.

### Core Concepts
1. **Triggers**: Events that kick off a workflow (e.g., `order.created`, `payment.failed`, `customer.inactive`).
2. **Conditions**: Filtering criteria (e.g., `amount > ₦50,000`, `customer.vip == true`).
3. **Actions**: Operational side effects (e.g., send push notification, generate AI message, send WhatsApp, create task).

### Major Components & Directory Structure
Create: `app/modules/workflows/`
- `models.py`: Workflow, Trigger, Condition, Action, and ExecutionLog ORM tables.
- `schemas.py`: Validation schemas for building, activating, and reviewing workflows.
- `repository.py`: CRUD operations for workflows and execution tracking.
- `service.py`: Engine manager service that handles workflow definitions.
- `engine.py`: Core execution loop matching triggered events against conditions and orchestrating actions asynchronously.
- `triggers.py`: Trigger registry and payload matching engines.
- `actions.py`: Extensible actions runner (e.g. WhatsApp, Email, AI task, Database update).
- `routes.py`: Endpoints to create, edit, toggle, and view workflow execution logs.

---

## Phase 6 — Integration Ecosystem

### Goal
Connect OpsPilot to critical external services, especially communications and payments, to make the platform highly useful and sticky.

### 1. WhatsApp Integration (High Value)
* **Provider**: Meta for Developers Cloud API.
* **Features**:
  * AI-driven customer replies and chatbot flows.
  * Automated customer order creation via chat interface.
  * Dispatching Paystack/Flutterwave payment links automatically.

### 2. Payment Gateways
* **Paystack**: Localized, highly reliable payment processing, webhook verifications, and payouts.
* **Flutterwave**: Expanded multi-currency card, bank transfer, and mobile money rails.

### 3. Communications Gateway
* **Email Providers**: Transactional email deliveries (e.g., Resend, Mailgun).
* **SMS Providers**: Fallback customer alerts (e.g., Twilio, Termii).
* **Push Notifications**: Expo/Firebase Cloud Messaging for workspace web/mobile clients.

### 4. Accounting & ERP (Future Target)
* Integrations with QuickBooks, Zoho, and other localized accounting frameworks.

---

## Phase 7 — Observability & Platform Reliability

### Goal
Implement enterprise-grade platform health, structured metrics, and tracking to separate startup-grade code from resilient infrastructure.

### Major Initiatives
1. **Structured Logging**:
   * Migrate to `structlog` for machine-readable JSON logging in production.
   * Inject Correlation IDs and Trace IDs into all logs to trace asynchronous task contexts.
2. **Monitoring & Telemetry**:
   * Integrate Prometheus metrics endpoints.
   * Visualize platform metrics, API latencies, CPU/memory, and active socket connections via Grafana.
3. **Error Tracking**:
   * Integrate Sentry with request contexts, user contexts, and environment tagging.
4. **Queue & Job Monitoring**:
   * Track failed background/AI worker jobs, webhook retries, and transaction verification failures.

---

## Phase 8 — Security Hardening

### Goal
Harden security and ensure compliance for fintech-adjacent, multi-tenant operations.

### Major Initiatives
1. **Granular RBAC (Role-Based Access Control)**:
   * Implement strict user roles (e.g., `owner`, `manager`, `staff`, `viewer`).
   * Scope permissions at the API router and decorator layer: `orders.read`, `orders.write`, `payments.verify`, `analytics.read`.
2. **Enterprise Audit Logs**:
   * Implement a tamper-evident audit ledger capturing exactly *who* changed *what*, *when*, and both previous and new values.
3. **Redis Rate Limiting**:
   * Prevent API abuse using dynamic, IP/User-scoped Redis sliding-window rate limiting.
4. **Third-Party API Keys**:
   * Support secure API key generation and authentication for merchant systems integrating directly with OpsPilot.
5. **Data Encryption at Rest**:
   * Encrypt sensitive credentials, integration provider secrets, and tokens using AES-256 (via `cryptography`).

---

## Phase 9 — AI Orchestration Layer

### Goal
Evolve the AI module from static endpoints into an actual AI infrastructure layer.

### Major Initiatives
1. **Centralized Prompt Registry**:
   * Centralize system prompts, version them, and enable dynamic rendering based on variables.
2. **AI Task Routing**:
   * Dynamically assign tasks to different LLMs depending on complexity (e.g., GPT-4o for complex financial forecasting, cheaper local or minor models for basic classification or summaries).
3. **AI Memory**:
   * Track business-scoped conversational context, remembering merchant choices and recurring instructions.
4. **RAG (Retrieval-Augmented Generation) Layer**:
   * Connect AI execution paths directly to customer history, order logs, and custom business knowledge bases.

---

## Phase 10 — SaaS Maturity

### Goal
Ready the platform for production SaaS operations, subscriptions, and global deployments.

### Major Initiatives
1. **SaaS Billing System**:
   * Seamless subscription management (Paystack billing cycles, billing tiers).
2. **Usage Metering**:
   * Granularly track and charge for consumption: AI tokens consumed, workflow executions run, and emails/WhatsApp messages sent.
3. **Feature Flags**:
   * Integrate dynamic feature flags to allow staged rollouts, beta features, and custom tier restrictions.
4. **Multi-Region & High Availability**:
   * Formulate replication, caching, and horizontal deployment topologies to ensure low-latency high-availability operations.

---

## Phase 11 — Performance & Optimization

### Goal
Scale OpsPilot to handle high throughput with rapid response times and robust background processing capabilities.

### Major Initiatives
1. **Asynchronous Task Queue**:
   * Integrate `arq` to offload heavy blocking operations (AI workflows, Webhooks, Emails) from the main API thread.
2. **Caching Layer**:
   * Implement `fastapi-cache2` to memoize heavy read endpoints (like analytics or dashboard summaries).
3. **Database Query Optimization**:
   * Introduce proper database indexing for hot columns.
   * Update repository models to use `selectinload` or `joinedload` resolving N+1 query performance hits.
