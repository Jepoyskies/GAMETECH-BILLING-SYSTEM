---
name: Project Architecture and Optimization Patterns
description: Comprehensive rules for developing, maintaining, and scaling the Gametech Billing System. Covers UI, Database, Caching, and Template best practices established during the Operation Cleanup phases.
---

# Gametech Billing System: Codebase Patterns & Rules

This document outlines the architectural patterns and optimization rules established during the multi-phase "Operation Cleanup" of the Gametech Billing System. All Antigravity agents MUST adhere to these rules to maintain enterprise-grade stability and performance.

## 1. UI & Styling Framework
- **Core Framework:** We strictly use **Vanilla CSS** combined with **Bootstrap 5**.
- **Rule - NO Tailwind:** Do not introduce TailwindCSS utility classes or libraries unless explicitly approved by the user. Previous tailwind artifacts caused inconsistencies and were systematically removed.
- **Aesthetics:** Prioritize dynamic, premium user interfaces. Use glassmorphism, subtle gradients, and micro-animations for hover states and transitions.
- **Consistency:** Use predefined CSS variables from the global stylesheet.

## 2. Database Optimization (Indexing)
- **High-Traffic Models:** The `Customer` and `Payment` models process the most read/write operations.
- **Rule:** Any new field added to `Customer` or `Payment` that is frequently used in `.filter()` or `.order_by()` MUST be indexed by setting `db_index=True`.
  - Current indexes include: `Customer.status`, `Customer.created_at`, `Payment.payment_method`, and `Payment.created_at`.
- **Foreign Keys:** Django automatically indexes `ForeignKey` fields, so no explicit indexing is required for those.

## 3. Analytics & Dashboard Caching
- **The Problem:** Aggregating metrics across thousands of rows causes severe TTFB (Time to First Byte) latency.
- **Rule:** Never perform heavy aggregations (`Sum()`, `Count()`, etc.) directly inside the main request response cycle without caching.
- **Implementation:** The system uses Redis via `django.core.cache`. Dashboard components (like Total Sales, Active Customers) are bundled into a `stats` dictionary and cached using `cache.get_or_set(cache_key, stats, timeout=300)`.
- **Note:** Do NOT cache user-specific queries (like personal notifications) using global cache keys.

## 4. Django Template Partials
- **The Problem:** Using `{% block %}` inside partial templates that are injected via `{% include %}` does not work in Django.
- **Rule:** Partial templates (e.g., `_sidebar.html`, `_topbar.html`, `_scripts.html`) must **not** contain `{% block %}` tags. They must be self-contained snippets.
- **Rule - Tag Loading:** The `{% include %}` tag does NOT inherit `{% load %}` tags from the parent template. Every individual partial template MUST explicitly include its own `{% load static %}`, `{% load humanize %}`, etc., if it uses those features.

## 5. Automated Code Formatting
- **Rule:** The entire codebase is formatted using **`black`**.
- Any new python files generated, or extensive refactors made, must adhere to Black's formatting rules (e.g., double quotes for strings, standard indentation). 
- To format, run: `python -m black billing/ gametech_core/`

## 6. Authentication Workflows
- **Rule:** Session termination logic is handled by a custom `custom_logout_view` in `auth.py`. Do not rely solely on default Django class-based logout views if they conflict with the system's strict redirect rules (always redirect to `login` on logout).

---
*Follow these rules closely to prevent regressions and maintain the system's performance.*
