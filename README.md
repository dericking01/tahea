<p align="center">
  <img src="https://img.shields.io/badge/Odoo-18.0-%23734BA9?style=for-the-badge&logo=odoo&logoColor=white" alt="Odoo 18">
  <img src="https://img.shields.io/badge/Enterprise-Custom_Modules-%230A66C2?style=for-the-badge" alt="Enterprise">
  <img src="https://img.shields.io/badge/PostgreSQL-15-%23336791?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL 15">
  <img src="https://img.shields.io/badge/Docker-Compose-%232496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker Compose">
  <img src="https://img.shields.io/badge/License-MIT-%23007EC7?style=for-the-badge" alt="License MIT">
</p>

<h1 align="center">
  🚀 Odoo 18 Enterprise Custom Modules Suite
</h1>

<p align="center">
  <strong>Production-Ready Custom Modules for Odoo 18 Enterprise</strong><br>
  Comprehensive business logic extensions covering multiple industries and use cases
</p>

<p align="center">
  <img src="https://github.com/user-attachments/assets/5b3e80f0-771e-44e8-9799-51da3018b54b" alt="Odoo Modules Banner" width="800">
</p>

## 📦 Modules Overview

### 🏢 **Core Business Modules**
| Module | Description | Status | Version |
|--------|-------------|--------|---------|
| **`advanced_inventory`** | Multi-warehouse, batch tracking, expiry management | ✅ Production | v2.1.0 |
| **`enhanced_crm`** | Advanced pipeline analytics, lead scoring, automation | ✅ Production | v1.8.0 |
| **`procurement_ai`** | Predictive procurement, vendor performance analytics | 🚧 Beta | v0.9.0 |
| **`manufacturing_iot`** | IoT integration for smart manufacturing | ✅ Production | v1.5.0 |

### 💰 **Financial Suite**
| Module | Description | Status | Version |
|--------|-------------|--------|---------|
| **`multi_currency_accounting`** | Real-time forex, automated reconciliations | ✅ Production | v3.2.0 |
| **`tax_compliance`** | Automated tax calculations for 50+ countries | ✅ Production | v2.4.0 |
| **`budget_forecasting`** | AI-powered budget predictions | ✅ Production | v1.7.0 |

### 🤖 **Automation & AI**
| Module | Description | Status | Version |
|--------|-------------|--------|---------|
| **`document_ai`** | Intelligent document processing with OCR | ✅ Production | v2.0.0 |
| **`chatbot_integration`** | WhatsApp/Telegram/Messenger chatbots | ✅ Production | v1.6.0 |
| **`predictive_maintenance`** | Machine learning for equipment maintenance | 🚧 Beta | v0.8.0 |

### 📱 **E-commerce & Retail**
| Module | Description | Status | Version |
|--------|-------------|--------|---------|
| **`omnichannel_retail`** | Unified inventory across online/offline | ✅ Production | v2.3.0 |
| **`loyalty_pro**** | Tiered rewards, gamification, personalized offers | ✅ Production | v1.9.0 |
| **`subscription_management`** | Recurring billing, proration, dunning | ✅ Production | v2.0.0 |

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Odoo 18 Enterprise License
- 4GB RAM minimum, 8GB recommended
- PostgreSQL 15

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/odoo18-enterprise-modules.git
cd odoo18-enterprise-modules

# Copy environment configuration
cp .env.example .env
# Edit .env file with your settings
nano .env

# Start the stack
docker-compose up -d

# Initialize modules (first time setup)
./scripts/init_modules.sh
