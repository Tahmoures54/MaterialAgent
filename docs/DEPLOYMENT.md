# iMat Deployment Guide

## 1. Single-user (SQLite) — site laptop

1. Install Python 3.9+ and dependencies:
   ```bash
   pip install -r requirements.txt
   python main.py
   ```
2. Keep `database.engine` = `sqlite` in `app_config.json`.
3. Enable auto-backup under Tools → Auto Backup.
4. Copy the whole folder (including `aimat.db` and `backups/`) when moving machines.

## 2. Multi-user (SQL Server) — office / network

### Prerequisites
- Microsoft SQL Server 2016+ (or Azure SQL)
- ODBC Driver 17 or 18 for SQL Server on every client PC
- `pip install pyodbc`

### Server setup
1. Create database `iMat` (or your name).
2. Create a SQL login with rights: `db_datareader`, `db_datawriter`, `db_ddladmin` (first run creates tables).
3. Open firewall TCP 1433 (or your instance port).
4. Prefer Windows Authentication on domain networks; otherwise use a strong SQL password.

### Client config (`app_config.json`)
```json
"database": {
  "engine": "sqlserver",
  "sqlserver": {
    "enabled": true,
    "driver": "ODBC Driver 17 for SQL Server",
    "server": "SQLSERVER01",
    "port": 1433,
    "database": "iMat",
    "username": "imat_user",
    "password": "********",
    "trusted_connection": false,
    "encrypt": true,
    "trust_server_certificate": true
  }
}
```

Or use UI: **Settings → Database** (when available).

### Checklist before go-live
- [ ] Test connection from one client
- [ ] Run app once as admin to create tables
- [ ] Create users and roles
- [ ] Import Material Master + locations
- [ ] Trial MRR → QC → MIV flow
- [ ] Configure server-side backups (not file copy)
- [ ] Document rollback plan

### What does NOT work on SQL Server
- File-based `backups/*.db` copy (use SQL Server Backup / Maintenance Plan)
- Moving a single `.db` file between PCs

## 3. Security notes
- Do not commit real passwords into git
- Prefer environment variable `DATABASE_URL` for production secrets
- Limit SQL login to the `iMat` database only
