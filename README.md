# 🏭 iMat Warehouse - Material Control System (EPC Edition)

<div align="center">

![iMat Logo](resources/images/logo_large.png)

**Where Inventory Meets Artificial Intelligence**

*Intelligent Material Control System for Oil, Gas & Petrochemical EPC Projects*

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://www.imat.io)
[![Python](https://img.shields.io/badge/python-3.9+-green.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt-6.5+-teal.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](https://www.imat.io/license)
[![WhatsApp](https://img.shields.io/badge/WhatsApp-%2B989160684552-25D366.svg)](https://wa.me/989160684552)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [System Requirements](#-system-requirements)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [User Roles](#-user-roles)
- [Module Overview](#-module-overview)
- [Database Schema](#-database-schema)
- [Configuration](#-configuration)
- [Development](#-development)
- [Testing](#-testing)
- [Deployment](#-deployment)
- [Support](#-support)
- [License](#-license)

---

## 🌟 Overview

**iMat Warehouse** is a comprehensive desktop application designed specifically for material and inventory management in complex **EPC (Engineering, Procurement, and Construction)** projects. Built robustly with **SQLite** and **PyQt6**, it combines heavy-duty inventory control with modern **AI forecasting** capabilities.

### Key Benefits

- ✅ **100% Offline Operation** - No internet required for core functionality
- 🔒 **Role-Based Security** - 5 user roles with granular permissions
- 🤖 **AI-Powered** - Demand prediction, ABC analysis, EOQ optimization
- 📊 **Professional Reports** - Excel, PDF, HTML export with formatting
- 📷 **Barcode Integration** - Quick scanning for item lookup
- 💬 **WhatsApp Integration** - Share reports and alerts instantly
- 🔄 **Auto Backup** - Scheduled database backups
- 📦 **Complete EPC Support** - MRR, MIV, MSR, OS&D, MTR document types

---

## ✨ Features

### 📦 Material Control
- Comprehensive item coding system (Material Master)
- Multi-warehouse & location mapping (Warehouse → Rack → Bin)
- Document management: MRR, MIV, MSR, OS&D, MTR, RTV, MRV
- Transaction management with history
- Real-time inventory tracking
- Heat/batch number tracking
- Expiry date monitoring with alerts
- Reorder point & safety stock calculator

### 📐 Technical Office
- Material Requests (MR) with multi-currency support
- Material Store Requisitions (MSR)
- ISO drawing reference tracking
- WBS code integration
- Request status workflow (Pending → Approved → Converted)
- Excel import/export for bulk requests

### ✅ Quality Control
- QC Release (Quarantine → Accepted/Rejected)
- Inspection type recording
- Certificate/document linking
- Preservation schedule dashboard
- Automatic next-due date calculation
- Preservation type categorization
- Batch & heat number tracking

### 📊 Reports & Export
- Unified Report Manager (12+ report types)
- Inventory Summary & Live Stock Dashboard
- Transaction History & Document History
- Material Traceability (by heat number)
- ABC Analysis & Reorder Reports
- Expiry Date & Preservation Reports
- Export to Excel, PDF, HTML, CSV
- Professional formatting with company branding

### 🤖 AI-Powered Tools
- Demand Prediction (7/14/30 days)
- Multiple forecasting methods (MA, WMA, Exponential, Regression, Holt-Winters)
- Automatic best-method selection
- ABC Classification (Pareto Analysis)
- Economic Order Quantity (EOQ) Calculator
- Safety Stock optimization
- Inventory turnover analysis

### 👥 Teamwork & Security
- 5 User Roles: Admin, Operator, Technical Office, QC Inspector, Viewer
- Password hashing (PBKDF2-SHA256)
- Login attempt limiting with cooldown
- Account lock/unlock
- Activity audit logging
- License activation & management
- Trial period with usage limits

### ⚙️ System & Maintenance
- SQLite database (zero configuration)
- Automatic backup scheduling
- Database change/restore
- Theme support (Light/Dark/High Contrast)
- Multi-language ready (English/فارسی)
- Application logging
- Crash reporting

---

## 💻 System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **OS** | Windows 10 / Linux / macOS 10.14+ | Windows 11 / Ubuntu 22.04+ |
| **Python** | 3.9+ | 3.11+ |
| **RAM** | 4 GB | 8 GB+ |
| **Disk Space** | 500 MB | 2 GB+ |
| **Display** | 1366×768 | 1920×1080+ |
| **Database** | SQLite 3 | SQLite 3.35+ |

---

## 📥 Installation

### Method 1: From Source

```bash
# 1. Clone the repository
git clone https://github.com/imat/imat-warehouse.git
cd imat-warehouse

# 2. Create virtual environment
python -m venv venv

# 3. Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run the application
python main.py