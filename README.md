# Influencer Outreach Agent

An AI-assisted influencer and business outreach automation system that discovers relevant business contacts, qualifies leads, generates outreach messages, routes them through human approval, and sends approved emails.

## Current Status

The core outreach pipeline is working end-to-end:

Contact Discovery -> Lead Qualification -> Outreach Drafting -> Human Approval -> Email Sending

### Implemented

- Hunter.io contact discovery
- Decision-maker filtering
- Email confidence filtering
- Supabase/PostgreSQL data storage
- Contact deduplication using unique email protection
- Contact upsert logic
- Database-driven lead scoring configuration
- Explainable lead scoring with JSONB rationale
- Human approval workflow
- Approval audit trail
- Email dry-run mode
- Real email sending
- Multi-company contact discovery
- Stripe lead qualification
- HubSpot contact discovery

## Architecture

```text
Company / Brand
      |
      v
Contact Discovery (Hunter.io)
      |
      v
Contacts (Supabase PostgreSQL)
      |
      v
Lead Qualification (0-100)
      |
      v
Outreach Drafting
      |
      v
Human Approval
      |
      v
Send Agent
      |
      v
Real Email'''




## Tech Stack

- Python
- PostgreSQL
- Supabase
- Hunter.io API
- SMTP / Email
- psycopg2
- python-dotenv

## Project Structure

influencer-agent/
├── contact_discovery.py
├── save_contacts.py
├── lead_qualification.py
├── outreach_agent.py
├── approval_agent.py
├── send_agent.py
├── db.py
├── test_connection.py
├── requirements.txt
├── .gitignore
└── README.md

## Lead Qualification

Lead qualification uses configurable weights stored in the database.

| Signal | Weight |
|---|---:|
| Senior decision makers | 30 |
| Role relevance | 25 |
| Verified email coverage | 15 |
| LinkedIn coverage | 10 |
| Contact depth | 20 |
| Total | 100 |

The scoring engine uses diminishing returns for contact-count based signals so that a large number of contacts does not automatically produce a perfect score.

The scoring rationale is stored as JSONB for explainability and auditing.

## Database

The system uses Supabase PostgreSQL.

Core tables include:

- brands
- contacts
- leads
- outreach
- approvals
- conversations
- followups
- messages
- research
- scoring_config
- social_profiles
- campaigns
- agent_runs

## Setup

Clone the repository:

git clone https://github.com/Div-484/influencer-agent.git
cd influencer-agent

Create a virtual environment:

python -m venv .venv

Install dependencies:

pip install -r requirements.txt

Create a local .env file for credentials and configuration.

Do not commit .env or API credentials to GitHub.

## Running

Test the database connection:

python test_connection.py

Discover and save contacts:

python save_contacts.py example.com "Example Company"

Score a lead:

python lead_qualification.py <brand_id>

Review drafted outreach:

python approval_agent.py

Preview approved emails without sending:

python send_agent.py --dry-run

Send approved emails:

python send_agent.py --send

## Safety and Controls

The outreach workflow includes human approval before sending.

The Send Agent supports dry-run mode so approved messages can be verified before real delivery.

Credentials and environment files are excluded from Git tracking.

## Current Development Roadmap

Planned next stages include:

- Reply and conversation processing
- Follow-up automation
- Lead status automation
- Improved brand-fit scoring
- Campaign-level orchestration
- Reporting and analytics
- Additional outreach channels

## Project Goal

The goal is to build a modular outreach agent system where discovery, qualification, drafting, approval, sending, reply handling, and follow-up operate as separate auditable stages instead of one uncontrolled automation process.
