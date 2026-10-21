# 🚀 RevenueApp v3 (Logistics Revenue Engine)

High-performance logistics revenue calculation engine built on Flask + Pandas with pre-warmed in-memory rate caching.

## ⚡ Performance Highlights
- **Speed:** Evaluates 500+ waybills in **< 150 milliseconds** (down from ~60s in v2).
- **Parity:** 100% mathematical parity against historical billing data.
- **Defensive:** Safe handling of variable manifest columns (`shipper_city` vs `return_city`).

## 🛠️ Local Development
```bash
# Run locally
python app.py
```
Open [http://localhost:5000](http://localhost:5000)

## 🧪 Tests
```bash
python tests/test_parity.py
```

## 🌐 Continuous Deployment & Auto-Extend
This repository automatically deploys and keeps your PythonAnywhere web app active via GitHub Actions.
Requires the following GitHub Repository Secrets:
- `PA_USERNAME`: Your PythonAnywhere username
- `PA_DOMAIN`: Your web app domain (e.g. `username.pythonanywhere.com`)
- `PA_API_TOKEN`: Your PythonAnywhere API Token (from Account > API Token)
